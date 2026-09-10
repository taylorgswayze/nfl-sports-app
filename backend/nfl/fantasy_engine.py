"""The Week Room engine: deterministic weekly roster advice for one Sleeper
league. Pure functions over plain dicts; no network, no ORM, so every piece
is unit-testable and the whole thing can be replayed against history.

Inputs are Sleeper's own stat-level projections, scored under each league's
rules (scoring() matched Sleeper's players_points exactly, n=2225, in the
2025 backtest, see PLAN-WEEK-ROOM.md):
  * this week = Sleeper's weekly projection for the player, zero on a bye
    or when he is out. Lineups set by it beat the 2025 human lineups by
    +3.5 pts/week.
  * rest of season = week by week: every remaining week's optimal lineup
    on that week's Sleeper projections (byes as zero weeks), averaged
    over the window. Depth is worth exactly the weeks it starts; there
    is no flat bench weight. Waiver claims, releases and trades are
    scored on the change in that season value (points per week).
The 2026-09-09 switch from the earlier blend (Sleeper x Desk season model,
+4.5 pts/week in the backtest) was the owner's call: one source of truth.
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
OUT_STATUSES = {'Out', 'IR', 'PUP', 'Sus', 'NA', 'COV', 'DNR'}
DOUBTFUL_MULT = 0.25
NOISE_FLOOR = 0.05        # any real projected gain prints as roster moves; pure ties do not
WAIVER_FLOOR = 0.5        # smallest ROS lineup-value gain worth a waiver line
WAIVER_LINES = 3          # the wire prints at most this many claims
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


def injury_multiplier(status):
    if not status:
        return 1.0
    if status in OUT_STATUSES:
        return 0.0
    if status == 'Doubtful':
        return DOUBTFUL_MULT
    return 1.0


def player_values(pids, ctx, settings, week):
    """Per-player values under this league's scoring, all from Sleeper's
    stat-level projections: proj (this week, zero on a bye or when out),
    weekly ({week: points} for every remaining week, this week first) and
    ros (the average of weekly, for display and screening).

    ctx supplies: players (slim index), proj (this week's projections),
    weekly(pid) -> {week: points} for the weeks after this one or None,
    weeks (the remaining window, this week included), ros_ppw(pid, settings)
    and season_ppg(pid, settings) as flat fallbacks, and team_game(team) ->
    {'has_game', 'started', 'final', 'kickoff'} or None.
    """
    window = [int(w) for w in (ctx.get('weeks') or [int(week)])]
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
        flags = []
        if not team:
            flags.append('free agent')
        if injury:
            flags.append(injury.lower())
        if team and game is not None and not has_game:
            flags.append('bye')
        # this week: Sleeper's number, zero on a bye or when he is out
        raw = slp if slp is not None else 0.0
        if slp is None and has_game and team:
            flags.append('no projection')
        proj = raw * injury_multiplier(injury) if has_game else 0.0
        # the weeks after this one: Sleeper's per-week numbers, else flat
        future = ctx['weekly'](pid) if ctx.get('weekly') else None
        if future is None:
            flat = ctx['ros_ppw'](pid, settings)
            if flat is None:
                flat = ctx['season_ppg'](pid, settings)
            if flat is None:
                flat = proj
            future = {w: flat for w in window[1:]}
        mult = 0.5 if injury in OUT_STATUSES else 1.0
        weekly = {window[0]: round(proj, 2)}
        for w in window[1:]:
            weekly[w] = round(float(future.get(w, future.get(str(w), 0.0)) or 0.0) * mult, 2)
        ros = sum(weekly.values()) / len(weekly)
        out[pid] = {
            'player_id': pid, 'name': meta.get('name') or pid, 'pos': pos,
            'positions': list(positions), 'team': team,
            'proj': round(proj, 2), 'proj_raw': round(raw, 2), 'ros': round(ros, 2), 'weekly': weekly,
            'injury': injury, 'has_game': has_game,
            'locked': bool(game and (game.get('started') or game.get('final'))),
            'opp': (row or {}).get('opp') or (game or {}).get('opp'),
            'flags': flags,
        }
    return out


def _brief(v):
    return {k: v.get(k) for k in ('player_id', 'name', 'pos', 'positions', 'team', 'proj', 'ros', 'injury', 'opp', 'flags')}


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


def season_value(slots, pids, values, reserve=None):
    """Rest-of-season lineup value in points per week: the optimal lineup
    total of every remaining week, each on its own projections (a bye is a
    zero week), averaged over the window. A bench player is worth exactly
    the weeks he starts."""
    reserve = set(reserve or [])
    pool = [p for p in pids if p in values and p not in reserve]
    if not pool:
        return 0.0
    weeks = set()
    for p in pool:
        weeks.update(int(w) for w in (values[p].get('weekly') or {}))
    if not weeks:
        return optimal_lineup(slots, [(p, values[p]['positions'], values[p]['ros']) for p in pool])[0]
    total = 0.0
    for w in weeks:
        total += optimal_lineup(slots, [(p, values[p]['positions'], _wk(values[p], w)) for p in pool])[0]
    return total / len(weeks)


def _wk(v, w):
    wk = v.get('weekly') or {}
    return float(wk.get(w, wk.get(str(w), v.get('ros', 0.0))) or 0.0)


def roster_ros_value(slots, pids, values, reserve=None):
    return season_value(slots, pids, values, reserve)


def keep_costs(slots, my, values, droppable):
    """Season value lost by releasing each candidate: the price of the drop."""
    base = season_value(slots, my, values)
    return base, {p: round(base - season_value(slots, [q for q in my if q != p], values), 3) for p in droppable}


def waiver_report(slots, my_pids, values, free_agents, fa_values, reserve=None,
                  trending=None, max_lines=WAIVER_LINES, per_pos=5, protected=None):
    """Free agents worth a claim, each paired with the release that costs
    least: gain = season value of (roster + add - drop) minus today's, in
    points per week, with every week's lineup re-solved. The release is
    picked from the cheapest players to keep (a backup K/DEF before a core
    player at the same price) plus the cheapest at the newcomer's position;
    this week's starters and IR/taxi are never released. At most max_lines
    lines ordered by season gain, the best claim for this week guaranteed a
    line, and a release already spoken for re-paired with the next."""
    reserve = set(str(p) for p in (reserve or []))
    protected = set(str(p) for p in (protected or []))
    trending = trending or {}
    my = [p for p in my_pids if p in values and p not in reserve]
    droppable = [p for p in my if p not in protected]
    base, cost = keep_costs(slots, my, values, droppable)
    base_week = optimal_lineup(slots, [(p, values[p]['positions'], values[p]['proj']) for p in my])[0]

    def is_core(p):
        return bool(set(values[p]['positions']) & set(CORE))

    def release_order(exclude=()):
        return sorted([p for p in droppable if p not in exclude],
                      key=lambda p: (round(cost[p], 2), is_core(p), values[p]['ros']))

    def line_for(fa, exclude=()):
        order = release_order(exclude)
        if not order:
            return None
        merged = dict(values); merged[fa['player_id']] = fa
        tries = order[:2]
        same = next((p for p in order if values[p]['pos'] == fa['pos']), None)
        if same and same not in tries:
            tries.append(same)
        best = None
        for drop in tries:
            after = [p for p in my if p != drop] + [fa['player_id']]
            gain = season_value(slots, after, merged) - base
            if best is None or gain > best[1] + 1e-9:
                best = (drop, gain)
        drop, gain = best
        if gain < WAIVER_FLOOR:
            return None
        after = [p for p in my if p != drop] + [fa['player_id']]
        week_after, asg = optimal_lineup(slots, [(p, merged[p]['positions'], merged[p]['proj']) for p in after])
        starts = fa['player_id'] in asg.values()
        reason = 'starts right away' if starts else 'depth over the current bench'
        if fa.get('opp'):
            reason += f", {fa['opp']} this week"
        return {'add': _brief(fa), 'drop': _brief(merged[drop]), 'gain': round(gain, 2),
                'week_gain': round(week_after - base_week, 2), 'starts': starts,
                'trending': trending.get(fa['player_id']), 'reason': reason}

    by_pos = {}
    for pid in free_agents:
        v = fa_values.get(pid)
        if not v or not v['team'] or v['ros'] <= 0:
            continue
        by_pos.setdefault(v['pos'], []).append(v)
    cands = []
    for pos, rows in by_pos.items():
        rows.sort(key=lambda v: -v['ros'])
        for fa in rows[:per_pos]:
            line = line_for(fa)
            if line:
                cands.append((fa, line))
    cands.sort(key=lambda t: (-t[1]['gain'], -(t[1]['trending'] or 0)))

    out, used_adds, used_drops = [], set(), set()

    def take(fa, line):
        if fa['player_id'] in used_adds:
            return
        if line['drop']['player_id'] in used_drops:
            line = line_for(fa, exclude=used_drops)
            if not line:
                return
        used_adds.add(fa['player_id']); used_drops.add(line['drop']['player_id']); out.append(line)

    for fa, line in cands:
        if len(out) >= max_lines:
            break
        take(fa, line)
    # the best claim for this week always makes the card
    best_week = max(cands, key=lambda t: t[1]['week_gain'], default=None)
    if best_week and best_week[1]['week_gain'] > 0 and best_week[0]['player_id'] not in used_adds \
            and best_week[1]['week_gain'] > max((l['week_gain'] for l in out), default=0.0):
        if len(out) >= max_lines:
            gone = out.pop()
            used_adds.discard(gone['add']['player_id']); used_drops.discard(gone['drop']['player_id'])
        take(*best_week)
    out.sort(key=lambda l: (-l['gain'], -(l['trending'] or 0)))
    if out:
        max(out, key=lambda l: l['gain'])['best_season'] = True
        bw = max(out, key=lambda l: l['week_gain'])
        if bw['week_gain'] > 0:
            bw['best_week'] = True
    return out


def drop_candidates(slots, my_pids, values, reserve=None, n=3, protected=None):
    """The players cheapest to release: least season value lost (never this
    week's starters, never IR/taxi)."""
    reserve = set(str(p) for p in (reserve or []))
    protected = set(str(p) for p in (protected or []))
    my = [p for p in my_pids if p in values and p not in reserve]
    droppable = [p for p in my if p not in protected]
    _base, cost = keep_costs(slots, my, values, droppable)
    droppable.sort(key=lambda p: (round(cost[p], 2), values[p]['ros'], values[p]['proj']))
    return [dict(_brief(values[p]), keep_cost=cost[p]) for p in droppable[:n]]


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


def trade_report(slots, my_pids, values, partners, max_lines=3, exact=8):
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
    # screen every pairing on the cheap average-based value, then score the
    # best few week by week
    def quick(pids, vals):
        return lineup_value(slots, [(p, vals[p]['positions'], vals[p]['ros']) for p in pids if p in vals])
    quick_me = quick(my, values)
    screened = []
    for partner in partners:
        pv = partner['values']
        their = [p for p in partner['pids'] if p in pv]
        quick_them = quick(their, pv)
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
                q_me = quick(me_after, merged_me) - quick_me
                q_them = quick(them_after, merged_them) - quick_them
                if q_me < TRADE_FLOOR / 2 or q_them < -1.0:
                    continue
                screened.append((q_me + 0.5 * max(q_them, 0), partner, their, send, recv, me_after, them_after, merged_me, merged_them))
    screened.sort(key=lambda t: -t[0])
    ideas = []
    base_them_cache = {}
    for _q, partner, their, send, recv, me_after, them_after, merged_me, merged_them in screened[:exact]:
        pv = partner['values']
        if partner['name'] not in base_them_cache:
            base_them_cache[partner['name']] = season_value(slots, their, pv)
        d_me = season_value(slots, me_after, merged_me) - base_me
        d_them = season_value(slots, them_after, merged_them) - base_them_cache[partner['name']]
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


def _week_total(slots, pids, values, reserve=None):
    reserve = set(reserve or [])
    return optimal_lineup(slots, [(p, values[p]['positions'], values[p]['proj'])
                                  for p in pids if p in values and p not in reserve])[0]


def _fit(slots, pids, values, roster_max):
    """Trim a roster to roster_max by cutting the lowest-ROS players outside
    its optimal ROS lineup: the release a lopsided trade would force."""
    pids = [p for p in pids if p in values]
    if not roster_max or len(pids) <= roster_max:
        return pids, []
    _t, asg = optimal_lineup(slots, [(p, values[p]['positions'], values[p]['ros']) for p in pids])
    started = set(asg.values())
    bench = sorted([p for p in pids if p not in started], key=lambda p: values[p]['ros'])
    cut = bench[:len(pids) - roster_max]
    return [p for p in pids if p not in cut], cut


def trade_verdict(week_delta, ros_delta):
    if ros_delta >= TRADE_FLOOR and week_delta >= -0.5:
        return 'accept'
    if ros_delta >= 0.25:
        return 'lean accept'
    if ros_delta > -0.25:
        return 'coin flip'
    return 'decline'


def _signed(v):
    return f'{v:+.1f}'


def evaluate_trade(slots, my_pids, their_pids, send, get, values, my_reserve=None,
                   their_reserve=None, roster_max=None):
    """Score a proposed trade for both sides: the change in this week's
    optimal lineup total and in ROS lineup value (starters plus BENCH_W x
    bench for QB/RB/WR/TE) when I send `send` and get `get`. A side that
    ends up over roster_max releases its cheapest bench players first. values
    must cover every player on both rosters."""
    my_pids = [str(p) for p in my_pids]
    their_pids = [str(p) for p in their_pids]
    send = [str(p) for p in send if str(p) in my_pids]
    get = [str(p) for p in get if str(p) in their_pids]
    me_after = [p for p in my_pids if p not in send] + get
    them_after = [p for p in their_pids if p not in get] + send
    me_after, my_cuts = _fit(slots, me_after, values, roster_max)
    them_after, their_cuts = _fit(slots, them_after, values, roster_max)
    my_reserve = [p for p in (my_reserve or []) if p not in send]
    their_reserve = [p for p in (their_reserve or []) if p not in get]
    r = {
        'send': [_brief(values[p]) for p in send if p in values],
        'get': [_brief(values[p]) for p in get if p in values],
        'my_week_before': round(_week_total(slots, my_pids, values, my_reserve), 2),
        'my_week_after': round(_week_total(slots, me_after, values, my_reserve), 2),
        'my_ros_before': round(roster_ros_value(slots, my_pids, values, my_reserve), 2),
        'my_ros_after': round(roster_ros_value(slots, me_after, values, my_reserve), 2),
        'their_week_before': round(_week_total(slots, their_pids, values, their_reserve), 2),
        'their_week_after': round(_week_total(slots, them_after, values, their_reserve), 2),
        'their_ros_before': round(roster_ros_value(slots, their_pids, values, their_reserve), 2),
        'their_ros_after': round(roster_ros_value(slots, them_after, values, their_reserve), 2),
        'my_cuts': [_brief(values[p]) for p in my_cuts],
        'their_cuts': [_brief(values[p]) for p in their_cuts],
    }
    r['my_week_delta'] = round(r['my_week_after'] - r['my_week_before'], 2)
    r['my_ros_delta'] = round(r['my_ros_after'] - r['my_ros_before'], 2)
    r['their_week_delta'] = round(r['their_week_after'] - r['their_week_before'], 2)
    r['their_ros_delta'] = round(r['their_ros_after'] - r['their_ros_before'], 2)
    r['verdict'] = trade_verdict(r['my_week_delta'], r['my_ros_delta'])
    r['summary'] = (f"{r['verdict']}: rest of season {_signed(r['my_ros_delta'])} lineup points a week for you, "
                    f"this week {_signed(r['my_week_delta'])}; for them {_signed(r['their_ros_delta'])} a week "
                    f"and {_signed(r['their_week_delta'])} this week")
    if my_cuts:
        r['summary'] += f"; you would have to release {', '.join(c['name'] for c in r['my_cuts'])}"
    return r


def _fmt(v):
    return f'{v:.1f}'


def template_narrative(p):
    """The GM's note in deterministic prose; the fallback when no LLM key is
    configured or the call fails. Front-office voice, plain sentences, no em
    dashes."""
    week = p.get('week')
    m = p.get('matchup') or {}
    lu = p.get('lineup') or {}
    parts = []
    if p.get('status') in ('pre_draft', 'drafting'):
        return (f"GM's note: {p.get('name')} has not drafted yet, so there is no lineup card to "
                f"write. The Live Advisor works draft night; the first note prints once the roster exists.")
    if m.get('opp_name'):
        parts.append(f"GM's note, week {week} against {m['opp_name']}: we project {_fmt(m.get('my_total') or 0)} "
                     f"to their {_fmt(m.get('opp_total') or 0)}.")
    moves = lu.get('moves') or []
    if lu.get('material') and moves:
        steps = ', '.join(f"{mv['name']} from {mv['from']} to {mv['to']}" for mv in moves)
        parts.append(f"Lineup card: I am moving {steps}, worth {_fmt(lu['gain'])} more projected points.")
    else:
        parts.append("Lineup card: the card stands as written; it is already the projected optimum.")
    flagged = [f"{x['name']} ({', '.join(x['flags'])})" for x in (p.get('flags') or [])[:3]]
    if flagged:
        parts.append("On watch: " + '; '.join(flagged) + '.')
    w = p.get('waivers') or []
    if w:
        a, d = w[0]['add'], w[0]['drop']
        wk = w[0].get('week_gain') or 0.0
        parts.append(f"The wire: put in a claim for {a['name']} ({a['pos']}, {a['team']}) and release {d['name']}: "
                     f"about {_fmt(w[0]['gain'])} lineup points a week the rest of the way"
                     + (f", {_fmt(wk)} of it this week" if wk >= 0.5 else '')
                     + (f"; {len(w) - 1} more claim{'s' if len(w) > 2 else ''} on the card below." if len(w) > 1 else '.'))
    else:
        parts.append("The wire: nothing available beats what we have on the bench.")
    t = p.get('trades') or []
    if t:
        parts.append(f"The phones: {t[0]['partner']} could use {t[0]['send'][0]['name']}; "
                     f"for {t[0]['receive'][0]['name']} it nets us {_fmt(t[0]['my_delta'])} a week and them "
                     f"{_fmt(t[0]['their_delta'])}, a call worth making.")
    for pr in (p.get('proposals') or [])[:2]:
        parts.append(f"The inbox: {pr.get('partner')} offers {_names(pr.get('get'))} for {_names(pr.get('send'))}. "
                     f"My call is {pr.get('verdict')}: {_fmt(pr.get('my_ros_delta') or 0)} lineup points a week "
                     f"the rest of the way and {_fmt(pr.get('my_week_delta') or 0)} this week for us.")
    parts.append("Next note in 12 hours.")
    return ' '.join(parts)


def _names(briefs):
    names = [b.get('name') for b in (briefs or []) if b and b.get('name')]
    return ', '.join(names) if names else 'nothing'

