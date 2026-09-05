"""The Week Room engine: deterministic weekly roster advice for one Sleeper
league. Pure functions over plain dicts; no network, no ORM, so every piece
is unit-testable and the whole thing can be replayed against history.

Validated against the user's 2025 league (see PLAN-WEEK-ROOM.md):
  * scoring(): exact match with Sleeper's own players_points for every
    QB/RB/WR/TE/K/DEF row (n=2225), so projections scored this way are
    league-exact.
  * weekly projection = Sleeper's stat-level weekly projection under league
    scoring, blended with the ML season prior (weight 0.30 early, fading
    toward 0.16 by mid-season). Lineups set by it beat the human lineups by
    +4.5 pts/week (t=3.4) and capture ~19% of the human-to-hindsight gap;
    the weekly projection alone gave +3.5, the season prior alone -13.
  * rest-of-season (ROS) value = 0.5 x this-week projection + 0.5 x the
    mean of (ML prior, trailing-3 actual ppg): best rank correlation with
    the next four weeks' points among rostered players (0.52) and within
    noise of the best free-agent ranker.
"""
import math
from collections import Counter

SLOT_ELIG = {
    'QB': ('QB',), 'RB': ('RB',), 'WR': ('WR',), 'TE': ('TE',),
    'K': ('K',), 'DEF': ('DEF',),
    'FLEX': ('RB', 'WR', 'TE'), 'WRRB_FLEX': ('WR', 'RB'), 'REC_FLEX': ('WR', 'TE'),
    'SUPER_FLEX': ('QB', 'RB', 'WR', 'TE'),
}
NON_SLOTS = ('BN', 'IR', 'TAXI')
CORE = ('QB', 'RB', 'WR', 'TE')
BENCH_W = 0.15            # flat bench weight for QB/RB/WR/TE (optimizer.py convention)
PRIOR_W_CAP = 0.30        # season-prior weight at week 1
PRIOR_K = 3.0             # prior weight = min(cap, K / (K + weeks played))
OUT_STATUSES = {'Out', 'IR', 'PUP', 'Sus', 'NA', 'COV', 'DNR'}
DOUBTFUL_MULT = 0.25
NOISE_FLOOR = 0.05        # any real projected gain prints as roster moves; pure ties do not
WAIVER_FLOOR = 0.5        # smallest ROS lineup-value gain worth a waiver line
TRADE_FLOOR = 1.0
PPR = {'pass_yd': 0.04, 'pass_td': 4.0, 'pass_int': -2.0, 'pass_2pt': 2.0,
       'rush_yd': 0.1, 'rush_td': 6.0, 'rush_2pt': 2.0,
       'rec': 1.0, 'rec_yd': 0.1, 'rec_td': 6.0, 'rec_2pt': 2.0, 'fum_lost': -2.0}


def score(stats, settings):
    """League points for one stat line: sum of setting weight x stat value,
    exactly the arithmetic Sleeper applies."""
    if not stats:
        return 0.0
    total = 0.0
    for key, w in settings.items():
        v = stats.get(key)
        if v and w:
            total += float(w) * float(v)
    return total


def starting_slots(roster_positions):
    return [s for s in (roster_positions or []) if s not in NON_SLOTS]


def _components(slots, cands=()):
    """Group slot indexes that can trade players: slots whose eligible
    positions overlap, plus slots linked by a multi-position candidate (an
    RB/WR ties the RB slots to the WR slots). K and DEF usually stand alone;
    QB/RB/WR/TE/flex slots chain together via the flexes. Each group is
    solved by its own small DP."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)
    elig = [set(SLOT_ELIG.get(s, ())) for s in slots]
    for e in elig:
        for pos in e:
            union(next(iter(e)), pos)
    for _pid, pos, _val in cands:
        pos = list(pos)
        for p in pos[1:]:
            union(pos[0], p)
    groups = {}
    for i, e in enumerate(elig):
        if e:
            groups.setdefault(find(next(iter(e))), []).append(i)
    return list(groups.values())


def optimal_lineup(slots, cands, fixed=None):
    """Best legal lineup by value.

    slots: starting slot names in roster order; cands: iterable of
    (player_id, positions, value); fixed: {slot_index: (player_id, value)}
    pre-filled slots (locked starters, unmodeled slot types). Returns
    (total, {slot_index: player_id}). Bitmask DP per slot component."""
    fixed = dict(fixed or {})
    assignment = {i: pid for i, (pid, _v) in fixed.items()}
    total = sum(v for _pid, v in fixed.values())
    used = {pid for pid, _v in fixed.values()}
    cands = [(pid, tuple(pos or ()), float(val or 0.0)) for pid, pos, val in cands
             if pid not in used]
    for group in _components(slots, cands):
        free = [i for i in group if i not in fixed]
        if not free:
            continue
        elig = [set(SLOT_ELIG.get(slots[i], ())) for i in free]
        group_pos = set().union(*elig)
        pool = [(pid, set(pos), val) for pid, pos, val in cands if set(pos) & group_pos]
        pool.sort(key=lambda c: -c[2])
        # cap the pool: no slot component needs more than (slots + a few) candidates
        pool = pool[: len(free) * 3 + 4]
        n = len(free)
        dp = {0: (0.0, ())}
        for pid, pos, val in pool:
            nxt = dict(dp)
            for mask, (tot, asg) in dp.items():
                for j in range(n):
                    if mask & (1 << j) or not (elig[j] & pos):
                        continue
                    m2 = mask | (1 << j)
                    t2 = tot + val
                    cur = nxt.get(m2)
                    if cur is None or cur[0] < t2 + 1e-9:
                        nxt[m2] = (t2, asg + ((j, pid),))
            dp = nxt
        best_tot, best_asg = max(dp.values(), key=lambda x: x[0])
        total += best_tot
        for j, pid in best_asg:
            assignment[free[j]] = pid
    return total, assignment


def lineup_value(slots, cands, bench_w=BENCH_W):
    """Roster value: best legal lineup + bench_w x benched QB/RB/WR/TE value
    (a benched K/DEF is worth nothing: you stream them, you do not stash)."""
    total, asg = optimal_lineup(slots, cands)
    started = set(asg.values())
    for pid, pos, val in cands:
        if pid in started:
            continue
        if set(pos or ()) & set(CORE):
            total += bench_w * float(val or 0.0)
    return total


def prior_weight(week):
    weeks_played = max(0, int(week or 1) - 1)
    return min(PRIOR_W_CAP, PRIOR_K / (PRIOR_K + weeks_played))


def injury_multiplier(status):
    if not status:
        return 1.0
    if status in OUT_STATUSES:
        return 0.0
    if status == 'Doubtful':
        return DOUBTFUL_MULT
    return 1.0


def player_values(pids, ctx, settings, week):
    """Per-player weekly projection and ROS value under this league's scoring.

    ctx supplies: players (slim index), proj (weekly projections), prior
    (season prior by sleeper id), factor(pid) (league/PPR scoring ratio),
    trailing(pid) (trailing-3 league ppg or None), season_ppg(pid), and
    team_game(team) -> {'has_game', 'started', 'final', 'kickoff'} or None.
    """
    w_p = prior_weight(week)
    out = {}
    for pid in pids:
        pid = str(pid)
        meta = ctx['players'].get(pid) or {}
        row = ctx['proj'].get(pid)
        pos = meta.get('pos') or (row or {}).get('pos')
        positions = meta.get('positions') or ([pos] if pos else [])
        team = meta.get('team') or (row or {}).get('team')
        injury = meta.get('injury') or (row or {}).get('injury')
        game = ctx['team_game'](team) if team else None
        has_game = bool(game and game.get('has_game')) if game is not None else (row is not None)
        slp = score(row['stats'], settings) if row else None
        prior_row = ctx['prior'].get(pid)
        prior_ppg = None
        if prior_row and prior_row.get('ppg') is not None:
            prior_ppg = float(prior_row['ppg']) * ctx['factor'](pid, pos)
        trail = ctx['trailing'](pid)
        flags = []
        if not team:
            flags.append('free agent')
        if injury:
            flags.append(injury.lower())
        if team and game is not None and not has_game:
            flags.append('bye')
        # this week
        if slp is not None and prior_ppg is not None:
            raw = (1 - w_p) * slp + w_p * prior_ppg
        elif slp is not None:
            raw = slp
        else:
            raw = 0.0
            if has_game and team:
                flags.append('no projection')
        proj = raw * injury_multiplier(injury) if has_game else 0.0
        # rest of season
        longrun_parts = [x for x in (prior_ppg, trail) if x is not None]
        longrun = sum(longrun_parts) / len(longrun_parts) if longrun_parts else None
        if longrun is None:
            longrun = ctx['season_ppg'](pid, settings)
        nxt = slp if (slp is not None and has_game and slp > 0) else longrun
        if nxt is None:
            nxt = slp or 0.0
        if longrun is None:
            longrun = nxt
        ros = 0.5 * nxt + 0.5 * longrun
        if injury in OUT_STATUSES:
            ros *= 0.5
        out[pid] = {
            'player_id': pid, 'name': meta.get('name') or pid, 'pos': pos,
            'positions': list(positions), 'team': team,
            'proj': round(proj, 2), 'proj_raw': round(raw, 2), 'ros': round(ros, 2),
            'injury': injury, 'has_game': has_game,
            'locked': bool(game and (game.get('started') or game.get('final'))),
            'opp': (row or {}).get('opp') or (game or {}).get('opp'),
            'flags': flags,
        }
    return out


def _brief(v):
    return {k: v.get(k) for k in ('player_id', 'name', 'pos', 'team', 'proj', 'ros', 'injury', 'opp', 'flags')}


def _stabilize(free_idx, slots, chosen, positions, current_slot):
    """Re-seat the chosen starters so as many as possible keep the slot they
    already hold (every legal seating of the same players scores the same,
    so the report should not print pointless RB-for-FLEX shuffles).
    Returns {slot_index: pid} or None when no full seating exists."""
    n = len(chosen)
    best = {0: (0, {})}
    for i in free_idx:
        elig = set(SLOT_ELIG.get(slots[i], ()))
        nxt = dict(best)  # leaving the slot empty is always allowed
        for mask, (kept, asg) in best.items():
            for j, pid in enumerate(chosen):
                if mask & (1 << j) or not (set(positions.get(pid, ())) & elig):
                    continue
                k2 = kept + (1 if current_slot.get(pid) == i else 0)
                m2 = mask | (1 << j)
                cur = nxt.get(m2)
                if cur is None or cur[0] < k2:
                    a2 = dict(asg); a2[i] = pid
                    nxt[m2] = (k2, a2)
        best = nxt
    full = (1 << n) - 1
    return best[full][1] if full in best else None


def lineup_report(slots, roster_pids, starters, values, reserve=None):
    """Optimal lineup vs the current one. starters aligns with slots (Sleeper
    order); '0'/None marks an empty slot. Locked starters (game under way or
    final) stay put, locked bench players cannot enter, IR/taxi players
    (reserve) cannot start, and unmodeled slot types (IDP etc.) keep their
    occupant untouched."""
    reserve = set(str(p) for p in (reserve or []))
    starters = [str(s) if s not in (None, '0', '') else None for s in (starters or [])]
    starters += [None] * (len(slots) - len(starters))
    fixed = {}
    for i, slot in enumerate(slots):
        cur = starters[i]
        if slot not in SLOT_ELIG:
            if cur:
                fixed[i] = (cur, 0.0)
        elif cur and cur in values and values[cur]['locked']:
            fixed[i] = (cur, values[cur]['proj'])
    cands = [(pid, values[pid]['positions'], values[pid]['proj']) for pid in roster_pids
             if pid in values and not values[pid]['locked'] and pid not in reserve]
    opt_total, asg = optimal_lineup(slots, cands, fixed)
    current_slot = {s: i for i, s in enumerate(starters[:len(slots)]) if s}
    free_idx = [i for i in range(len(slots)) if slots[i] in SLOT_ELIG and i not in fixed]
    chosen = [asg[i] for i in free_idx if i in asg]
    seating = _stabilize(free_idx, slots, chosen, {p: values[p]['positions'] for p in chosen}, current_slot)
    if seating is not None:
        asg = {i: p for i, p in asg.items() if i not in free_idx}
        asg.update(seating)
    current_total = sum(values[s]['proj'] for i, s in enumerate(starters[:len(slots)])
                        if s and s in values and slots[i] in SLOT_ELIG)
    cur_set = {s for i, s in enumerate(starters[:len(slots)]) if s and slots[i] in SLOT_ELIG}
    opt_set = {pid for i, pid in asg.items() if slots[i] in SLOT_ELIG}
    ins = sorted(opt_set - cur_set, key=lambda p: -values[p]['proj'])
    outs = sorted(cur_set - opt_set, key=lambda p: values[p]['proj'] if p in values else 0.0)
    changes = []
    slot_of = {pid: slots[i] for i, pid in asg.items()}
    remaining_outs = list(outs)
    for pid in ins:
        v = values[pid]
        # pair with the benched player this one most directly replaces:
        # same position first, then any
        pick = next((o for o in remaining_outs if o in values and values[o]['pos'] == v['pos']), None)
        if pick is None and remaining_outs:
            pick = remaining_outs[0]
        if pick is not None:
            remaining_outs.remove(pick)
        sit = values.get(pick) if pick else None
        delta = v['proj'] - (sit['proj'] if sit else 0.0)
        reason = []
        if sit:
            reason.extend(f"{sit['name']} {f}" for f in sit['flags'] if f in ('bye', 'out', 'ir', 'doubtful', 'no projection'))
        if v.get('opp'):
            reason.append(f"vs {v['opp']}")
        changes.append({
            'slot': slot_of.get(pid), 'start': _brief(v), 'sit': _brief(sit) if sit else None,
            'delta': round(delta, 2), 'reason': ', '.join(reason),
        })
    changes.sort(key=lambda c: -c['delta'])
    for pid in remaining_outs:  # benched with nobody added (empty slot filled elsewhere)
        if pid in values:
            changes.append({'slot': None, 'start': None, 'sit': _brief(values[pid]),
                            'delta': round(-values[pid]['proj'], 2), 'reason': 'no replacement needed'})
    gain = opt_total - current_total
    material = gain >= NOISE_FLOOR
    # the explicit path from the lineup as set to the optimal one: every
    # player whose slot changes, bench included, in slot order
    moves = []
    if material:
        opt_slot = {pid: i for i, pid in asg.items() if slots[i] in SLOT_ELIG}
        cur_mod = {pid: i for pid, i in current_slot.items() if slots[i] in SLOT_ELIG}
        for pid in set(cur_mod) | set(opt_slot):
            frm, to = cur_mod.get(pid), opt_slot.get(pid)
            if frm == to:
                continue
            v = values.get(pid) or {'player_id': pid, 'name': pid, 'pos': None, 'team': None, 'proj': 0.0}
            moves.append({
                'player_id': pid, 'name': v.get('name'), 'pos': v.get('pos'), 'team': v.get('team'),
                'proj': v.get('proj'), 'from': slots[frm] if frm is not None else 'BN',
                'to': slots[to] if to is not None else 'BN',
                '_k': (0, to) if to is not None else (1, frm),
            })
        moves.sort(key=lambda m: m.pop('_k'))
    else:
        # a tie or a rounding-sized gain: the lineup as set stands
        changes = []
        asg = {i: s for i, s in enumerate(starters[:len(slots)]) if s}
    lineup = [{'slot': slots[i], **(_brief(values[pid]) if pid in values else {'player_id': pid, 'name': pid})}
              for i, pid in sorted(asg.items())]
    empty = [slots[i] for i in range(len(slots)) if i not in asg and slots[i] in SLOT_ELIG]
    return {
        'current_total': round(current_total, 2), 'optimal_total': round(opt_total, 2),
        'gain': round(gain, 2), 'material': material, 'changes': changes, 'moves': moves, 'lineup': lineup,
        'starting': sorted(opt_set if material else cur_set),
        'empty_slots': empty,
        'locked': [pid for pid in roster_pids if pid in values and values[pid]['locked']],
    }


def matchup_projection(slots, roster_pids, starters, values, reserve=None):
    """Projected total for a roster as it stands (current starters, empty
    slots filled optimally from the bench only when the manager left them
    empty)."""
    rep = lineup_report(slots, roster_pids, starters, values, reserve)
    return rep['current_total'], rep['optimal_total']


def roster_ros_value(slots, pids, values, reserve=None):
    reserve = set(reserve or [])
    return lineup_value(slots, [(p, values[p]['positions'], values[p]['ros'])
                                for p in pids if p in values and p not in reserve])


def waiver_report(slots, my_pids, values, free_agents, fa_values, reserve=None,
                  trending=None, max_lines=5, per_pos=6, protected=None):
    """Free agents worth a claim, each paired with the drop that costs
    least: value = ROS lineup value of (roster + add - drop) minus today's.

    A benched QB/RB/WR/TE costs BENCH_W x ROS to drop and a benched K/DEF
    costs nothing, so the cheapest drop is exact: the lowest-ROS player left
    on the bench once the newcomer is slotted (IR/taxi players excluded)."""
    reserve = set(str(p) for p in (reserve or []))
    protected = set(str(p) for p in (protected or []))  # this week's starters: never the drop
    trending = trending or {}
    my = [p for p in my_pids if p in values and p not in reserve]
    base = roster_ros_value(slots, my, values)
    base_week = optimal_lineup(slots, [(p, values[p]['positions'], values[p]['proj']) for p in my])[0]
    by_pos = {}
    for pid in free_agents:
        v = fa_values.get(pid)
        if not v or not v['team'] or v['ros'] <= 0:
            continue
        by_pos.setdefault(v['pos'], []).append(v)
    lines = []
    for pos, rows in by_pos.items():
        rows.sort(key=lambda v: -v['ros'])
        for fa in rows[:per_pos]:
            merged = dict(values); merged[fa['player_id']] = fa
            pids = my + [fa['player_id']]
            cands = [(p, merged[p]['positions'], merged[p]['ros']) for p in pids]
            tot, asg = optimal_lineup(slots, cands)
            started = set(asg.values())
            bench = [p for p in pids if p not in started]
            droppable = [p for p in bench if p not in protected]
            if not droppable:
                continue
            # cheapest drop: lowest bench cost (K/DEF cost 0, core cost BENCH_W x ROS)
            def cost(p):
                v = merged[p]
                return BENCH_W * v['ros'] if set(v['positions']) & set(CORE) else 0.0
            drop = min(droppable, key=lambda p: (cost(p), merged[p]['ros']))
            if drop == fa['player_id']:
                continue  # newcomer would be the first cut: not worth a claim
            new_val = tot + sum(cost(p) for p in bench if p != drop)
            gain = new_val - base
            if gain < WAIVER_FLOOR:
                continue
            starts = fa['player_id'] in started
            after = [p for p in pids if p != drop]
            week_after = optimal_lineup(slots, [(p, merged[p]['positions'], merged[p]['proj']) for p in after])[0]
            week_gain = week_after - base_week
            reason = 'starts right away' if starts else 'depth over the current bench'
            if fa.get('opp'):
                reason += f", {fa['opp']} this week"
            lines.append({
                'add': _brief(fa), 'drop': _brief(merged[drop]), 'gain': round(gain, 2),
                'week_gain': round(week_gain, 2),
                'starts': starts, 'trending': trending.get(fa['player_id']), 'reason': reason,
            })
    lines.sort(key=lambda l: (-l['gain'], -(l['trending'] or 0)))
    # one line per add, one per drop: the top pairing wins
    seen_add, seen_drop, out = set(), set(), []
    for l in lines:
        a, d = l['add']['player_id'], l['drop']['player_id']
        if a in seen_add or d in seen_drop:
            continue
        seen_add.add(a); seen_drop.add(d); out.append(l)
        if len(out) >= max_lines:
            break
    return out


def drop_candidates(slots, my_pids, values, reserve=None, n=3, protected=None):
    """Bench players with the least rest-of-season worth (never the optimal
    ROS lineup, never this week's starters, never IR/taxi)."""
    reserve = set(str(p) for p in (reserve or []))
    protected = set(str(p) for p in (protected or []))
    my = [p for p in my_pids if p in values and p not in reserve]
    _t, asg = optimal_lineup(slots, [(p, values[p]['positions'], values[p]['ros']) for p in my])
    started = set(asg.values()) | protected
    bench = [values[p] for p in my if p not in started]
    bench.sort(key=lambda v: (v['ros'], v['proj']))
    return [_brief(v) for v in bench[:n]]


def _slot_medians(slots, rosters_values):
    """League-median ROS value of the player started at each slot type in
    every roster's optimal ROS lineup: the bar for 'starter quality'."""
    per_slot = {}
    for pids, values in rosters_values:
        cands = [(p, values[p]['positions'], values[p]['ros']) for p in pids if p in values]
        _t, asg = optimal_lineup(slots, cands)
        for i, pid in asg.items():
            per_slot.setdefault(slots[i], []).append(values[pid]['ros'])
    med = {}
    for slot, vals in per_slot.items():
        vals.sort()
        med[slot] = vals[len(vals) // 2]
    return med


def trade_report(slots, my_pids, values, partners, max_lines=3):
    """One-for-one trade ideas. partners: [{name, pids, values}].

    Surplus = my benched QB/RB/WR/TE whose ROS clears the league-median
    starter at some slot they fit; deficit = slots where my starter sits
    below that median. A package sends surplus for a partner's player at a
    deficit position; it prints only when my ROS lineup value rises by
    TRADE_FLOOR and the partner's does not fall (both deltas printed).
    """
    my = [p for p in my_pids if p in values]
    medians = _slot_medians(slots, [(my, values)] + [(p['pids'], p['values']) for p in partners])
    if not medians:
        return []
    base_me = roster_ros_value(slots, my, values)
    _t, my_asg = optimal_lineup(slots, [(p, values[p]['positions'], values[p]['ros']) for p in my])
    my_started = set(my_asg.values())
    deficits = {slots[i] for i, pid in my_asg.items()
                if slots[i] in SLOT_ELIG and values[pid]['ros'] < medians.get(slots[i], 0) - 0.5}
    deficit_pos = set()
    for s in deficits:
        deficit_pos.update(SLOT_ELIG[s])
    deficit_pos -= {'K', 'DEF'}
    surplus = [p for p in my if p not in my_started and set(values[p]['positions']) & set(CORE)
               and any(values[p]['ros'] >= medians.get(s, 1e9) for s in slots if set(SLOT_ELIG.get(s, ())) & set(values[p]['positions']))]
    surplus.sort(key=lambda p: -values[p]['ros'])
    if not surplus or not deficit_pos:
        return []
    ideas = []
    for partner in partners:
        pv = partner['values']
        their = [p for p in partner['pids'] if p in pv]
        base_them = roster_ros_value(slots, their, pv)
        targets = [p for p in their if pv[p]['pos'] in deficit_pos]
        targets.sort(key=lambda p: -pv[p]['ros'])
        for send in surplus[:3]:
            for recv in targets[:4]:
                if pv[recv]['ros'] <= values[send]['ros'] - 6:
                    continue
                me_after = [p for p in my if p != send] + [recv]
                them_after = [p for p in their if p != recv] + [send]
                merged_me = dict(values); merged_me[recv] = pv[recv]
                merged_them = dict(pv); merged_them[send] = values[send]
                d_me = roster_ros_value(slots, me_after, merged_me) - base_me
                d_them = roster_ros_value(slots, them_after, merged_them) - base_them
                if d_me < TRADE_FLOOR or d_them < -0.25:
                    continue
                ideas.append({
                    'partner': partner['name'], 'send': [_brief(values[send])],
                    'receive': [_brief(pv[recv])],
                    'my_delta': round(d_me, 2), 'their_delta': round(d_them, 2),
                    'reason': f"you are thin at {'/'.join(sorted(deficit_pos))}; they gain at {values[send]['pos']}",
                })
    ideas.sort(key=lambda t: -(t['my_delta'] + 0.5 * max(t['their_delta'], 0)))
    out, seen = [], set()
    for t in ideas:
        key = (t['partner'], t['receive'][0]['player_id'])
        if key in seen:
            continue
        seen.add(key); out.append(t)
        if len(out) >= max_lines:
            break
    return out


def _fmt(v):
    return f'{v:.1f}'


def template_narrative(p):
    """Deterministic prose for the payload; the fallback when no LLM key is
    configured or the call fails. Plain sentences, no em dashes."""
    week = p.get('week')
    m = p.get('matchup') or {}
    lu = p.get('lineup') or {}
    parts = []
    if p.get('status') in ('pre_draft', 'drafting'):
        return (f"{p.get('name')} has not drafted yet. The Week Room prints lineup, waiver and "
                f"trade notes here once rosters exist; the Live Advisor covers draft night.")
    if m.get('opp_name'):
        parts.append(f"Week {week} against {m['opp_name']}: you project {_fmt(m.get('my_total') or 0)} "
                     f"to their {_fmt(m.get('opp_total') or 0)}.")
    moves = lu.get('moves') or []
    if lu.get('material') and moves:
        steps = ', '.join(f"{m['name']} from {m['from']} to {m['to']}" for m in moves)
        parts.append(f"To reach the optimal lineup, move {steps}: {_fmt(lu['gain'])} more projected points.")
    else:
        parts.append("Your lineup is already the projected optimum; nothing to change today.")
    flagged = [f"{x['name']} ({', '.join(x['flags'])})" for x in (p.get('flags') or [])[:3]]
    if flagged:
        parts.append("Watch: " + '; '.join(flagged) + '.')
    w = p.get('waivers') or []
    if w:
        a, d = w[0]['add'], w[0]['drop']
        wk = w[0].get('week_gain') or 0.0
        parts.append(f"Waivers: claim {a['name']} ({a['pos']}, {a['team']}) and drop {d['name']}: "
                     f"about {_fmt(w[0]['gain'])} rest-of-season lineup points a week"
                     + (f" and {_fmt(wk)} this week" if wk >= 0.5 else '')
                     + (f"; {len(w) - 1} more claim{'s' if len(w) > 2 else ''} in the table." if len(w) > 1 else '.'))
    else:
        parts.append("No free agent clears your bench by enough to claim.")
    t = p.get('trades') or []
    if t:
        parts.append(f"Trade idea: send {t[0]['send'][0]['name']} to {t[0]['partner']} for "
                     f"{t[0]['receive'][0]['name']} ({_fmt(t[0]['my_delta'])} for you, "
                     f"{_fmt(t[0]['their_delta'])} for them).")
    return ' '.join(parts)
