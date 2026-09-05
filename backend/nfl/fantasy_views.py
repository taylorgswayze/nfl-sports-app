"""My-leagues fantasy overview: one composed payload for all of a Sleeper
user's leagues, with live per-player points from Sleeper's own league-scored
matchup data plus real-game status from the live scoreboard proxy.

Everything here is read-only against public Sleeper endpoints; the username
is just a lookup key, no account linkage exists.
"""
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from utils import sleeper
from . import live_views

logger = logging.getLogger(__name__)

MAX_LEAGUES = 12

# Sleeper team abbreviations that differ from ESPN's scoreboard abbreviations.
SLEEPER_TO_ESPN = {'WAS': 'WSH', 'JAC': 'JAX', 'OAK': 'LV', 'SD': 'LAC'}


def _scoring_label(league):
    rec = (league.get('scoring_settings') or {}).get('rec', 0)
    label = 'PPR' if rec >= 1 else 'Half PPR' if rec >= 0.5 else 'Standard'
    if 'SUPER_FLEX' in (league.get('roster_positions') or []):
        label += ', superflex'
    return label


def _round2(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _player_rows(ids, players_points, player_index, game_map):
    rows = []
    for pid in ids or []:
        if not pid or pid == '0':
            continue
        meta = player_index.get(str(pid)) or {}
        team = meta.get('team')
        live = game_map.get(SLEEPER_TO_ESPN.get(team, team)) if team else None
        rows.append({
            'player_id': str(pid),
            'name': meta.get('name') or str(pid),
            'pos': meta.get('pos'),
            'team': team,
            'points': _round2((players_points or {}).get(str(pid))),
            'game_state': (live or {}).get('state'),
            'game_detail': (live or {}).get('short_detail'),
        })
    return rows


def _live_team_map():
    """{espn_abbr: {state, short_detail}} using the Desk Team table for ids."""
    try:
        payload = live_views._cached('scoreboard', live_views._scoreboard_payload)
    except Exception as e:
        logger.warning(f'live scoreboard unavailable for overview: {e}')
        return {}
    from .models import Team
    id_to_abbr = dict(Team.objects.values_list('team_id', 'short_name'))
    out = {}
    for g in payload.get('games', []):
        entry = {'state': g.get('state'), 'short_detail': g.get('short_detail')}
        for key in ('home_team_id', 'away_team_id'):
            abbr = id_to_abbr.get(g.get(key))
            if abbr:
                out[abbr] = entry
    return out


@require_http_methods(["GET"])
def overview(request):
    username = (request.GET.get('username') or '').strip()
    if not username:
        return JsonResponse({'error': 'username parameter is required'}, status=400)

    try:
        st = sleeper.state()
        season = str(request.GET.get('season') or st.get('season'))
        week = int(request.GET.get('week') or st.get('week') or 1) or 1

        user = sleeper.user(username)
        if not user or not user.get('user_id'):
            return JsonResponse({'error': f"Sleeper user '{username}' not found"},
                                status=404)
        user_id = user['user_id']

        player_index = sleeper.players()
        game_map = _live_team_map()

        leagues_out = []
        aggregate = {}
        for lg in sleeper.leagues(user_id, season)[:MAX_LEAGUES]:
            league_id = lg['league_id']
            entry = {
                'league_id': league_id,
                'name': lg.get('name'),
                'status': lg.get('status'),  # pre_draft|drafting|in_season|complete
                'teams': (lg.get('settings') or {}).get('num_teams'),
                'scoring': _scoring_label(lg),
                'draft_id': lg.get('draft_id'),
            }
            try:
                rosters = sleeper.league_rosters(league_id)
                users = {u['user_id']: u for u in sleeper.league_users(league_id)}
                mine = next((r for r in rosters
                             if r.get('owner_id') == user_id
                             or user_id in (r.get('co_owners') or [])), None)
                if mine:
                    s = mine.get('settings') or {}
                    fpts = _round2(f"{s.get('fpts', 0)}.{s.get('fpts_decimal', 0):02d}"
                                   if isinstance(s.get('fpts'), int) else s.get('fpts'))
                    standings = sorted(
                        rosters,
                        key=lambda r: (-(r.get('settings') or {}).get('wins', 0),
                                       -((r.get('settings') or {}).get('fpts', 0))))
                    rank = next((i + 1 for i, r in enumerate(standings)
                                 if r['roster_id'] == mine['roster_id']), None)
                    owner_meta = (users.get(user_id) or {}).get('metadata') or {}
                    entry.update({
                        'my_roster_id': mine['roster_id'],
                        'my_team_name': owner_meta.get('team_name')
                                        or user.get('display_name'),
                        'record': {'wins': s.get('wins', 0),
                                   'losses': s.get('losses', 0),
                                   'ties': s.get('ties', 0)},
                        'points_for': fpts,
                        'rank': rank,
                    })

                    matchups = sleeper.league_matchups(league_id, week)
                    m_mine = next((m for m in matchups
                                   if m.get('roster_id') == mine['roster_id']), None)
                    if m_mine:
                        opp = next((m for m in matchups
                                    if m.get('matchup_id') == m_mine.get('matchup_id')
                                    and m.get('roster_id') != mine['roster_id']), None)
                        opp_name = None
                        if opp:
                            opp_roster = next((r for r in rosters
                                               if r['roster_id'] == opp['roster_id']), {})
                            opp_user = users.get(opp_roster.get('owner_id')) or {}
                            opp_name = ((opp_user.get('metadata') or {}).get('team_name')
                                        or opp_user.get('display_name'))
                        starters = _player_rows(m_mine.get('starters'),
                                                m_mine.get('players_points'),
                                                player_index, game_map)
                        starter_ids = set(m_mine.get('starters') or [])
                        bench_ids = [p for p in (m_mine.get('players') or [])
                                     if p not in starter_ids]
                        bench = _player_rows(bench_ids, m_mine.get('players_points'),
                                             player_index, game_map)
                        entry['matchup'] = {
                            'week': week,
                            'my_points': _round2(m_mine.get('points')),
                            'opp_points': _round2((opp or {}).get('points')),
                            'opp_name': opp_name,
                            'starters': starters,
                            'bench': bench,
                        }
                        for row in starters + bench:
                            agg = aggregate.setdefault(row['player_id'], {
                                'player_id': row['player_id'], 'name': row['name'],
                                'pos': row['pos'], 'team': row['team'],
                                'game_state': row['game_state'],
                                'game_detail': row['game_detail'],
                                'leagues': 0, 'started': 0, 'total_points': 0.0,
                                'league_names': [],
                            })
                            agg['leagues'] += 1
                            agg['league_names'].append(lg.get('name'))
                            if row['player_id'] in starter_ids:
                                agg['started'] += 1
                            agg['total_points'] = round(
                                agg['total_points'] + (row['points'] or 0), 2)
            except Exception as e:
                logger.warning(f'overview: league {league_id} failed: {e}')
                entry['error'] = 'could not load this league'
            leagues_out.append(entry)

        agg_rows = sorted(aggregate.values(),
                          key=lambda a: (-a['leagues'], -(a['total_points'] or 0)))
        return JsonResponse({
            'username': username,
            'user_id': user_id,
            'season': season,
            'week': week,
            'season_type': st.get('season_type'),
            'leagues': leagues_out,
            'aggregate': agg_rows,
        })
    except Exception as e:
        logger.error(f'fantasy overview failed for {username}: {e}')
        return JsonResponse({'error': 'fantasy overview unavailable',
                             'message': str(e)}, status=502)


@require_http_methods(["GET"])
def insights(request):
    """The Week Room for every league of a Sleeper user.

    Stored reports return immediately (status 'ready', with each league's
    generated_at). When none exist for the username, or ?refresh=1 asks for
    a fresh set and the stored one is older than 20 minutes, generation
    starts in the background and the response says 'generating'; the page
    polls until the rows land. The cron job keeps saved users fresh on a
    12-hour cadence regardless."""
    from django.utils import timezone
    from datetime import timedelta
    from . import fantasy_insights as fi

    username = (request.GET.get('username') or '').strip()
    if not username:
        return JsonResponse({'error': 'username parameter is required'}, status=400)
    try:
        user = sleeper.user(username)
    except Exception as e:
        return JsonResponse({'error': 'sleeper unavailable', 'message': str(e)}, status=502)
    if not user or not user.get('user_id'):
        return JsonResponse({'error': f"Sleeper user '{username}' not found"}, status=404)
    user_id = user['user_id']
    rows = fi.stored(user_id)
    want_refresh = request.GET.get('refresh') in ('1', 'true')
    stale_enough = (not rows) or (timezone.now() - min(r.generated_at for r in rows) > timedelta(minutes=20))
    generating = fi.in_progress(user_id)
    if (not rows or (want_refresh and stale_enough)) and not generating:
        generating = fi.generate_in_background(username, user_id)
    payloads = [r.payload for r in rows]
    return JsonResponse({
        'username': username, 'user_id': user_id,
        'status': 'ready' if rows else ('generating' if generating else 'empty'),
        'generating': generating,
        'generated_at': min(r.generated_at for r in rows).isoformat() if rows else None,
        'refresh_hours': fi.REFRESH_HOURS,
        'leagues': payloads,
    })
