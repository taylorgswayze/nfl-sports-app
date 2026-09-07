"""The Week Room: builds and stores the per-league insight payloads.

generate_for_user(username) walks a Sleeper user's leagues, projects every
relevant player under each league's exact scoring (utils.sleeper feeds +
the season prior), runs the engine (fantasy_engine) and stores one
FantasyInsight row per league. The cron job refreshes every saved user
every 12 hours; the API generates on first sight of a username.
"""
import logging
import os
import threading
import time
from datetime import timedelta

from django.utils import timezone

from utils import llm, priors, sleeper
from . import fantasy_engine as fe
from .models import FantasyInsight, Game

logger = logging.getLogger(__name__)

MAX_LEAGUES = 12
REFRESH_HOURS = 12
# Sleeper's live abbreviations match ESPN's except Washington; the legacy
# OAK/SD/JAC codes only appear on retired players.
SLEEPER_TO_ESPN = {'WAS': 'WSH'}
WAIVER_TYPES = {0: 'rolling priority', 1: 'reverse standings', 2: 'FAAB bidding'}
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
# One generation per Sleeper user at a time across gunicorn workers and the
# cron driver: a lock file per user under backend/data/locks (stale after
# LOCK_STALE seconds, in case a process died mid-run).
LOCK_DIR = sleeper.DATA_DIR / 'locks'
LOCK_STALE = 15 * 60


def _scoring_label(league):
    rec = (league.get('scoring_settings') or {}).get('rec', 0)
    label = 'PPR' if rec >= 1 else 'Half PPR' if rec >= 0.5 else 'Standard'
    if 'SUPER_FLEX' in (league.get('roster_positions') or []):
        label += ', superflex'
    return label


def _schedule(season, week):
    """{sleeper_team_abbr: {has_game, started, final, kickoff, opp}} from
    the Desk's own schedule; {} when the week is not loaded."""
    games = (Game.objects.filter(season=season, week_num=week, season_type_id=2)
             .select_related('home_team', 'away_team'))
    now = timezone.now()
    espn_to_sleeper = {v: k for k, v in SLEEPER_TO_ESPN.items()}
    out = {}
    for g in games:
        for me, them in ((g.home_team, g.away_team), (g.away_team, g.home_team)):
            abbr = espn_to_sleeper.get(me.short_name, me.short_name)
            out[abbr] = {
                'has_game': True,
                'started': g.status == Game.STATUS_IN or (g.game_datetime and g.game_datetime <= now),
                'final': g.status == Game.STATUS_FINAL,
                'kickoff': g.game_datetime.isoformat() if g.game_datetime else None,
                'opp': espn_to_sleeper.get(them.short_name, them.short_name),
            }
    return out


def build_base_context(season, week):
    players = sleeper.players()
    proj = sleeper.weekly_projections(season, week)
    prior = priors.season_prior(season)
    try:
        season_proj = sleeper.season_projections(season)
    except Exception as e:
        logger.warning(f'season projections unavailable: {e}')
        season_proj = {}
    history = {}
    for w in range(max(1, int(week) - 3), int(week)):
        try:
            history[w] = sleeper.weekly_stats(season, w)
        except Exception as e:
            logger.warning(f'weekly stats {season} w{w} unavailable: {e}')
    schedule = _schedule(season, week)
    trending = {str(t.get('player_id')): t.get('count') for t in sleeper.trending_adds()}
    return {
        'season': int(season), 'week': int(week), 'players': players, 'proj': proj,
        'prior': prior, 'season_proj': season_proj, 'history': history,
        'schedule': schedule, 'trending': trending,
    }


def league_context(base, settings):
    """Bind the league's scoring into the closures the engine calls."""
    season_proj = base['season_proj']
    pos_factor = {}
    factor_cache = {}

    def factor(pid, pos):
        if pid in factor_cache:
            return factor_cache[pid]
        stats = season_proj.get(pid)
        f = None
        if stats:
            ppr = fe.score(stats, fe.PPR)
            if ppr > 20:
                f = fe.score(stats, settings) / ppr
        if f is None:
            if pos not in pos_factor:
                ratios = []
                for p, st in season_proj.items():
                    meta = base['players'].get(p) or {}
                    if meta.get('pos') != pos:
                        continue
                    ppr = fe.score(st, fe.PPR)
                    if ppr > 20:
                        ratios.append(fe.score(st, settings) / ppr)
                ratios.sort()
                pos_factor[pos] = ratios[len(ratios) // 2] if ratios else 1.0
            f = pos_factor[pos]
        factor_cache[pid] = f
        return f

    def trailing(pid):
        vals = [fe.score(stats[pid], settings) for stats in base['history'].values() if pid in stats]
        return (sum(vals) / len(vals)) if vals else None

    def season_ppg(pid, _settings):
        st = season_proj.get(pid)
        if not st:
            return None
        # the snapshot's gp is unreliable (1.0 on team defenses); season totals over 17
        return fe.score(st, settings) / 17.0

    def team_game(team):
        if not base['schedule']:
            return None
        return base['schedule'].get(team) or {'has_game': False, 'started': False, 'final': False}

    return {
        'players': base['players'], 'proj': base['proj'], 'prior': base['prior'],
        'factor': factor, 'trailing': trailing, 'season_ppg': season_ppg, 'team_game': team_game,
    }


def _team_name(users, roster, fallback):
    u = users.get((roster or {}).get('owner_id')) or {}
    return ((u.get('metadata') or {}).get('team_name') or u.get('display_name') or fallback)


HISTORY_KEEP = 3


def league_insight(base, lg, user_id, use_llm=True, previous=None):
    league_id = lg['league_id']
    settings = lg.get('scoring_settings') or {}
    lg_settings = lg.get('settings') or {}
    week = base['week']
    slots = fe.starting_slots(lg.get('roster_positions'))
    payload = {
        'league_id': league_id, 'name': lg.get('name'), 'season': base['season'], 'week': week,
        'status': lg.get('status'), 'scoring': _scoring_label(lg),
        'teams': lg_settings.get('num_teams'), 'slots': slots,
        'refresh_hours': REFRESH_HOURS,
        'projection_note': (f"Sleeper weekly projections scored under this league's rules, blended "
                            f"{int(round(fe.prior_weight(week) * 100))}% with the Desk season model."),
    }
    if lg.get('status') in ('pre_draft', 'drafting'):
        payload['narrative'] = fe.template_narrative(payload)
        payload['narrative_source'] = 'template'
        return payload

    rosters = sleeper.league_rosters(league_id)
    users = {u['user_id']: u for u in sleeper.league_users(league_id)}
    mine = next((r for r in rosters if r.get('owner_id') == user_id
                 or user_id in (r.get('co_owners') or [])), None)
    if not mine:
        payload['error'] = 'you do not own a roster in this league'
        payload['narrative'] = payload['error']
        payload['narrative_source'] = 'template'
        return payload
    matchups = sleeper.league_matchups(league_id, week)
    by_roster = {m.get('roster_id'): m for m in matchups}
    m_mine = by_roster.get(mine['roster_id']) or {}
    ctx = league_context(base, settings)

    all_rostered = set()
    for r in rosters:
        all_rostered.update(str(p) for p in (r.get('players') or []))
    values = fe.player_values(all_rostered, ctx, settings, week)

    my_pids = [str(p) for p in (m_mine.get('players') or mine.get('players') or [])]
    my_starters = m_mine.get('starters') or mine.get('starters') or []
    reserve = [str(p) for p in ((mine.get('reserve') or []) + (mine.get('taxi') or []))]
    lineup = fe.lineup_report(slots, my_pids, my_starters, values, reserve)

    # matchup projection: both sides as they stand
    opp = None
    if m_mine.get('matchup_id') is not None:
        opp = next((m for m in matchups if m.get('matchup_id') == m_mine.get('matchup_id')
                    and m.get('roster_id') != mine['roster_id']), None)
    matchup = None
    if opp:
        opp_roster = next((r for r in rosters if r['roster_id'] == opp['roster_id']), {})
        opp_reserve = [str(p) for p in ((opp_roster.get('reserve') or []) + (opp_roster.get('taxi') or []))]
        opp_cur, opp_opt = fe.matchup_projection(slots, [str(p) for p in (opp.get('players') or [])],
                                                 opp.get('starters') or [], values, opp_reserve)
        matchup = {
            'opp_name': _team_name(users, opp_roster, 'Opponent'),
            'my_total': lineup['optimal_total'], 'my_current': lineup['current_total'],
            'opp_total': round(opp_opt, 2), 'opp_current': round(opp_cur, 2),
            'my_points': m_mine.get('points'), 'opp_points': opp.get('points'),
        }

    # free agents: everyone with a projection or a prior who is not rostered
    startable = set()
    for s in slots:
        startable.update(fe.SLOT_ELIG.get(s, ()))
    fa_pool = []
    for pid, meta in base['players'].items():
        if pid in all_rostered or meta.get('status') != 'Active' or not meta.get('team'):
            continue
        if meta.get('pos') not in startable:
            continue
        if pid in base['proj'] or pid in base['prior']:
            fa_pool.append(pid)
    fa_values = fe.player_values(fa_pool, ctx, settings, week)
    top_fa = []
    by_pos = {}
    for pid, v in fa_values.items():
        by_pos.setdefault(v['pos'], []).append(v)
    for pos, rows in by_pos.items():
        rows.sort(key=lambda v: -v['ros'])
        top_fa.extend(v['player_id'] for v in rows[:12])
    protected = lineup.get('starting') or []
    waivers = fe.waiver_report(slots, my_pids, values, top_fa, fa_values, reserve, base['trending'],
                               protected=protected)
    drops = fe.drop_candidates(slots, my_pids, values, reserve, protected=protected)

    trades = []
    deadline = lg_settings.get('trade_deadline')
    if lg.get('status') == 'in_season' and (not deadline or week <= int(deadline)):
        partners = []
        for r in rosters:
            if r['roster_id'] == mine['roster_id']:
                continue
            m = by_roster.get(r['roster_id']) or {}
            pids = [str(p) for p in (m.get('players') or r.get('players') or [])]
            partners.append({'name': _team_name(users, r, f"Roster {r['roster_id']}"),
                             'pids': pids, 'values': values})
        try:
            trades = fe.trade_report(slots, my_pids, values, partners)
        except Exception as e:
            logger.warning(f'trade report failed for {league_id}: {e}')

    flags = [fe._brief(values[p]) for p in my_pids if p in values
             and any(f in ('bye', 'out', 'ir', 'doubtful', 'questionable', 'no projection', 'pup', 'sus')
                     for f in values[p]['flags'])]
    s = mine.get('settings') or {}
    payload.update({
        'my_roster_id': mine['roster_id'],
        'my_team_name': _team_name(users, mine, 'My team'),
        'record': {'wins': s.get('wins', 0), 'losses': s.get('losses', 0), 'ties': s.get('ties', 0)},
        'rank': None,
        'waiver': {
            'type': WAIVER_TYPES.get(lg_settings.get('waiver_type'), 'waivers'),
            'position': s.get('waiver_position'),
            'budget_left': (lg_settings.get('waiver_budget') or 0) - (s.get('waiver_budget_used') or 0)
            if lg_settings.get('waiver_type') == 2 else None,
            'runs': DAYS[lg_settings['waiver_day_of_week']]
            if isinstance(lg_settings.get('waiver_day_of_week'), int) and 0 <= lg_settings['waiver_day_of_week'] < 7 else None,
        },
        'trade_deadline': deadline,
        'matchup': matchup, 'lineup': lineup, 'flags': flags,
        'waivers': waivers, 'drops': drops, 'trades': trades,
    })
    standings = sorted(rosters, key=lambda r: (-(r.get('settings') or {}).get('wins', 0),
                                               -((r.get('settings') or {}).get('fpts', 0))))
    payload['rank'] = next((i + 1 for i, r in enumerate(standings) if r['roster_id'] == mine['roster_id']), None)

    text = llm.narrate(payload, previous=previous) if use_llm else None
    payload['narrative'] = text or fe.template_narrative(payload)
    prov = llm.provider() if text else None
    payload['narrative_source'] = f'{prov[0]}:{prov[3]}' if prov else 'template'
    return payload


PRE_DRAFT = ('pre_draft', 'drafting')


def newly_drafted_leagues(user_id, season):
    """League ids whose stored note predates the draft: the note says
    pre-draft (or is missing) while Sleeper now reports the league in
    season. Uses the cached leagues call, so it is cheap to ask often."""
    stored = {row.league_id: (row.payload or {}).get('status') for row in
              FantasyInsight.objects.filter(sleeper_user_id=user_id)}
    changed = []
    for lg in sleeper.leagues(user_id, season)[:MAX_LEAGUES]:
        live = lg.get('status')
        was = stored.get(lg['league_id'])
        if live in PRE_DRAFT:
            continue
        if was is None or was in PRE_DRAFT:
            changed.append(lg['league_id'])
    return changed


def generate_for_user(username, use_llm=True, league_ids=None):
    """Compute and store insights for every league of a Sleeper user, or
    only for league_ids when given (a freshly drafted league gets its note
    without rewriting the others). Returns the list of payloads."""
    st = sleeper.state()
    season = int(st.get('season'))
    week = int(st.get('week') or 1) or 1
    user = sleeper.user(username)
    if not user or not user.get('user_id'):
        raise ValueError(f"Sleeper user '{username}' not found")
    user_id = user['user_id']
    base = build_base_context(season, week)
    # the GM's earlier notes per league, so each reprint finds new material
    history = {}
    for row in FantasyInsight.objects.filter(sleeper_user_id=user_id):
        prev = list((row.payload or {}).get('narrative_history') or [])
        if (row.payload or {}).get('narrative_source', 'template') != 'template' and row.payload.get('narrative'):
            prev.append(row.payload['narrative'])
        history[row.league_id] = prev[-HISTORY_KEEP:]
    out = []
    wanted = set(league_ids) if league_ids else None
    for lg in sleeper.leagues(user_id, season)[:MAX_LEAGUES]:
        if wanted is not None and lg['league_id'] not in wanted:
            continue
        try:
            payload = league_insight(base, lg, user_id, use_llm=use_llm,
                                     previous=history.get(lg['league_id']))
            payload['narrative_history'] = history.get(lg['league_id'], [])
        except Exception as e:
            logger.exception(f'week room failed for league {lg.get("league_id")}: {e}')
            payload = {'league_id': lg['league_id'], 'name': lg.get('name'), 'season': season,
                       'week': week, 'status': lg.get('status'), 'error': 'could not build this report',
                       'narrative': 'The Week Room could not build this report; it will retry at the next refresh.',
                       'narrative_source': 'template'}
        payload['generated_at'] = timezone.now().isoformat()
        FantasyInsight.objects.update_or_create(
            sleeper_user_id=user_id, league_id=lg['league_id'],
            defaults={'username': username, 'season': season, 'week': week, 'payload': payload})
        out.append(payload)
    if wanted is None:
        # leagues that vanished (dropped out mid-season) lose their rows
        FantasyInsight.objects.filter(sleeper_user_id=user_id).exclude(
            league_id__in=[p['league_id'] for p in out]).delete()
    logger.info(f'week room: {username} {len(out)} leagues, season {season} week {week}')
    return out


def refresh_newly_drafted(use_llm=True):
    """For every user with stored notes, write the note for any league
    that has drafted since its note was printed. Returns {username:
    [league_ids]} of what was regenerated. Run by the 30-minute watcher."""
    st = sleeper.state()
    season = int(st.get('season'))
    done = {}
    users = (FantasyInsight.objects.values_list('sleeper_user_id', 'username').distinct())
    for user_id, username in users:
        try:
            changed = newly_drafted_leagues(user_id, season)
        except Exception as e:
            logger.warning(f'draft watch: leagues for {username} unavailable: {e}')
            continue
        if not changed:
            continue
        if not _acquire(user_id):
            logger.info(f'draft watch: {username} already generating; skipping')
            continue
        try:
            generate_for_user(username, use_llm=use_llm, league_ids=changed)
            done[username] = changed
        except Exception as e:
            logger.error(f'draft watch: {username} failed: {e}')
        finally:
            _release(user_id)
    return done


def stored(user_id):
    rows = FantasyInsight.objects.filter(sleeper_user_id=user_id).order_by('id')
    return list(rows)


def is_fresh(rows, hours=REFRESH_HOURS):
    if not rows:
        return False
    oldest = min(r.generated_at for r in rows)
    return timezone.now() - oldest < timedelta(hours=hours)


def _lock_path(user_id):
    return LOCK_DIR / f'weekroom-{user_id}.lock'


def _acquire(user_id):
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    path = _lock_path(user_id)
    try:
        if path.exists() and time.time() - path.stat().st_mtime > LOCK_STALE:
            path.unlink()
    except OSError:
        pass
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return True


def _release(user_id):
    try:
        _lock_path(user_id).unlink()
    except OSError:
        pass


def in_progress(user_id):
    path = _lock_path(user_id)
    try:
        return path.exists() and time.time() - path.stat().st_mtime <= LOCK_STALE
    except OSError:
        return False


def generate_in_background(username, user_id, use_llm=True, league_ids=None):
    """Start one generation per user at a time; returns True when started."""
    if not _acquire(user_id):
        return False

    def run():
        try:
            generate_for_user(username, use_llm=use_llm, league_ids=league_ids)
        except Exception as e:
            logger.error(f'background week room for {username} failed: {e}')
        finally:
            _release(user_id)

    threading.Thread(target=run, name=f'weekroom-{username}', daemon=True).start()
    return True


def kick_for_username(username):
    """First-time link of a Sleeper handle (or a change of handle): build the
    Week Room right away unless a fresh set already exists. Returns True when
    a generation was started. Never raises: linking must not fail because
    Sleeper is down."""
    try:
        su = sleeper.user(username)
        if not su or not su.get('user_id'):
            return False
        rows = stored(su['user_id'])
        if is_fresh(rows):
            return False
        return generate_in_background(username, su['user_id'])
    except Exception as e:
        logger.warning(f'week room kick for {username} failed: {e}')
        return False
