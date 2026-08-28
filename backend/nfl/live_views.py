"""Live data proxy views.

The hourly cron keeps the database fresh enough for schedules and finals,
but in-game state needs seconds-fresh data. These views proxy ESPN's public
endpoints with a short server-side cache, so any number of browser clients
costs at most one upstream request per TTL window.
"""
import logging
import threading
import time

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from utils import get_data

logger = logging.getLogger(__name__)

SCOREBOARD_URL = ('https://site.api.espn.com/apis/site/v2/sports/football/'
                  'nfl/scoreboard')
SUMMARY_URL = ('https://site.api.espn.com/apis/site/v2/sports/football/nfl/'
               'summary?event={event_id}')

LIVE_TTL = 20          # a game is in progress
PRE_TTL = 60           # nothing live right now
FINAL_TTL = 6 * 3600   # finished games no longer change

_cache = {}
_cache_lock = threading.Lock()


def _cached(key, fetch):
    """Serve from cache; ``fetch`` must return (payload, ttl_seconds)."""
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    payload, ttl = fetch()
    with _cache_lock:
        _cache[key] = (now + ttl, payload)
    return payload


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value):
    try:
        return float(str(value).replace(',', ''))
    except (TypeError, ValueError):
        return None


def _scoreboard_payload():
    data = get_data.session.get(SCOREBOARD_URL, timeout=20).json()
    games = []
    any_live = False
    for event in data.get('events', []):
        comp = (event.get('competitions') or [{}])[0]
        status = event.get('status') or {}
        stype = status.get('type') or {}
        state = stype.get('state')
        any_live = any_live or state == 'in'

        sides = {}
        for c in comp.get('competitors', []):
            side = c.get('homeAway')
            if side in ('home', 'away'):
                sides[side] = c
        situation = comp.get('situation') or {}

        games.append({
            'event_id': _to_int(event.get('id')),
            'state': state,  # pre | in | post
            'detail': stype.get('detail'),
            'short_detail': stype.get('shortDetail'),
            'completed': bool(stype.get('completed')),
            'clock': status.get('displayClock'),
            'period': status.get('period'),
            'home_score': _to_int(sides.get('home', {}).get('score')),
            'away_score': _to_int(sides.get('away', {}).get('score')),
            'home_team_id': _to_int(sides.get('home', {}).get('id')),
            'away_team_id': _to_int(sides.get('away', {}).get('id')),
            'possession_team_id': _to_int(situation.get('possession')),
            'down_distance': (situation.get('shortDownDistanceText')
                              or situation.get('downDistanceText')),
            'last_play': (situation.get('lastPlay') or {}).get('text'),
        })
    ttl = LIVE_TTL if any_live else PRE_TTL
    return {'games': games}, ttl


@require_http_methods(["GET"])
def live_scoreboard(request):
    """Current ESPN scoreboard, trimmed to live-display fields."""
    try:
        return JsonResponse(_cached('scoreboard', _scoreboard_payload))
    except Exception as e:
        logger.error(f"live scoreboard fetch failed: {e}")
        return JsonResponse({'error': 'live scoreboard unavailable',
                             'message': str(e)}, status=502)


# Fantasy scoring (points per unit). Receptions are handled separately so
# standard/half/full PPR can all be reported from one accumulation pass.
FANTASY_WEIGHTS = {
    'passingYards': 0.04,
    'passingTouchdowns': 4.0,
    'interceptions': -2.0,
    'rushingYards': 0.1,
    'rushingTouchdowns': 6.0,
    'receivingYards': 0.1,
    'receivingTouchdowns': 6.0,
    'fumblesLost': -2.0,
}
# Only count 'interceptions' thrown (passing category), not defensive ones.
FANTASY_CATEGORIES = {'passing', 'rushing', 'receiving', 'fumbles'}
FANTASY_STAT_FIELDS = {
    'passingYards': 'pass_yd', 'passingTouchdowns': 'pass_td',
    'interceptions': 'int', 'rushingYards': 'rush_yd',
    'rushingTouchdowns': 'rush_td', 'receptions': 'rec',
    'receivingYards': 'rec_yd', 'receivingTouchdowns': 'rec_td',
    'fumblesLost': 'fum_lost',
}


def _accumulate_fantasy(fantasy, cat_name, keys, entry, team_abbr):
    if cat_name not in FANTASY_CATEGORIES:
        return
    athlete = entry.get('athlete') or {}
    athlete_id = athlete.get('id')
    if not athlete_id:
        return
    row = fantasy.setdefault(athlete_id, {
        'athlete_id': athlete_id,
        'name': athlete.get('displayName'),
        'team_abbr': team_abbr,
        'pts_std': 0.0,
    })
    for key, value in zip(keys, entry.get('stats') or []):
        num = _to_float(value)
        if num is None:
            continue
        if cat_name == 'passing' and key == 'interceptions':
            row['int'] = row.get('int', 0) + num
            row['pts_std'] += num * FANTASY_WEIGHTS['interceptions']
            continue
        if key == 'receptions':
            row['rec'] = row.get('rec', 0) + num
            continue
        if key in FANTASY_WEIGHTS and not (
                cat_name != 'passing' and key == 'interceptions'):
            field = FANTASY_STAT_FIELDS.get(key)
            if field:
                row[field] = row.get(field, 0) + num
            row['pts_std'] += num * FANTASY_WEIGHTS[key]


def _boxscore_payload(event_id):
    data = get_data.session.get(
        SUMMARY_URL.format(event_id=event_id), timeout=25).json()

    header = data.get('header') or {}
    hcomp = (header.get('competitions') or [{}])[0]
    status = hcomp.get('status') or {}
    stype = status.get('type') or {}
    state = stype.get('state')

    sides = {}
    for c in hcomp.get('competitors', []):
        side = c.get('homeAway')
        if side in ('home', 'away'):
            team = c.get('team') or {}
            sides[side] = {
                'team_id': _to_int(team.get('id')),
                'abbr': team.get('abbreviation'),
                'score': _to_int(c.get('score')),
            }

    teams_out = []
    fantasy = {}
    for block in (data.get('boxscore') or {}).get('players') or []:
        team = block.get('team') or {}
        team_abbr = team.get('abbreviation')
        categories = []
        for category in block.get('statistics', []):
            cat_name = category.get('name', 'general')
            keys = category.get('keys') or []
            entries = []
            for entry in category.get('athletes', []):
                athlete = entry.get('athlete') or {}
                stats = entry.get('stats') or []
                if not stats or not athlete:
                    continue
                entries.append({
                    'athlete_id': athlete.get('id'),
                    'name': athlete.get('displayName'),
                    'jersey': athlete.get('jersey'),
                    'stats': stats,
                })
                _accumulate_fantasy(fantasy, cat_name, keys, entry, team_abbr)
            if entries:
                categories.append({
                    'name': cat_name,
                    'label': category.get('text') or cat_name.title(),
                    'labels': category.get('labels') or [],
                    'entries': entries,
                })
        teams_out.append({
            'team_id': _to_int(team.get('id')),
            'abbr': team_abbr,
            'name': team.get('displayName'),
            'categories': categories,
        })

    fantasy_rows = []
    for row in fantasy.values():
        rec = row.get('rec', 0)
        row['pts_std'] = round(row['pts_std'], 2)
        row['pts_half'] = round(row['pts_std'] + 0.5 * rec, 2)
        row['pts_ppr'] = round(row['pts_std'] + 1.0 * rec, 2)
        if row['pts_ppr'] != 0 or rec:
            fantasy_rows.append(row)
    fantasy_rows.sort(key=lambda r: r['pts_ppr'], reverse=True)

    payload = {
        'event_id': event_id,
        'state': state,  # pre | in | post
        'detail': stype.get('detail'),
        'short_detail': stype.get('shortDetail'),
        'completed': bool(stype.get('completed')),
        'clock': status.get('displayClock'),
        'period': status.get('period'),
        'home': sides.get('home'),
        'away': sides.get('away'),
        'teams': teams_out,
        'fantasy': fantasy_rows[:20],
    }
    if state == 'post':
        ttl = FINAL_TTL
    elif state == 'in':
        ttl = LIVE_TTL
    else:
        ttl = PRE_TTL
    return payload, ttl


@require_http_methods(["GET"])
def game_boxscore(request, event_id):
    """Player-level boxscore for one game, live or historical."""
    try:
        return JsonResponse(
            _cached(f'boxscore:{event_id}',
                    lambda: _boxscore_payload(event_id)))
    except Exception as e:
        logger.error(f"boxscore fetch failed for {event_id}: {e}")
        return JsonResponse({'error': 'boxscore unavailable',
                             'message': str(e),
                             'event_id': event_id}, status=502)


# ---------------- NFL standings ----------------

STANDINGS_URL = 'https://site.api.espn.com/apis/v2/sports/football/nfl/standings'
STANDINGS_TTL = 300

# ESPN's standings payload is conference-level only; the division layout
# has been fixed since the 2002 realignment, so a static map is the
# simplest reliable grouping.
NFL_DIVISIONS = [
    ('AFC', 'East', ['BUF', 'MIA', 'NE', 'NYJ']),
    ('AFC', 'North', ['BAL', 'CIN', 'CLE', 'PIT']),
    ('AFC', 'South', ['HOU', 'IND', 'JAX', 'TEN']),
    ('AFC', 'West', ['DEN', 'KC', 'LV', 'LAC']),
    ('NFC', 'East', ['DAL', 'NYG', 'PHI', 'WSH']),
    ('NFC', 'North', ['CHI', 'DET', 'GB', 'MIN']),
    ('NFC', 'South', ['ATL', 'CAR', 'NO', 'TB']),
    ('NFC', 'West', ['ARI', 'LAR', 'SF', 'SEA']),
]

_STANDINGS_STATS = {
    'wins': 'wins', 'losses': 'losses', 'ties': 'ties',
    'winPercent': 'pct', 'pointsFor': 'points_for',
    'pointsAgainst': 'points_against', 'differential': 'differential',
    'streak': 'streak', 'playoffSeed': 'seed',
}


def _standings_payload():
    data = get_data.session.get(STANDINGS_URL, timeout=20).json()
    rows = {}
    for conference in data.get('children', []):
        for entry in ((conference.get('standings') or {}).get('entries') or []):
            team = entry.get('team') or {}
            row = {
                'team_id': _to_int(team.get('id')),
                'name': team.get('displayName'),
                'abbr': team.get('abbreviation'),
            }
            try:
                from utils import helpers
                row['logo'] = helpers.get_team_logo(row['team_id'])
            except Exception:
                row['logo'] = None
            for stat in entry.get('stats', []):
                key = _STANDINGS_STATS.get(stat.get('name'))
                if key:
                    row[key] = stat.get('displayValue')
                    row[f'{key}_value'] = stat.get('value')
            rows[row['abbr']] = row

    conferences = []
    for conf_name in ('AFC', 'NFC'):
        divisions = []
        for conf, div_name, abbrs in NFL_DIVISIONS:
            if conf != conf_name:
                continue
            teams = [rows[a] for a in abbrs if a in rows]
            teams.sort(key=lambda t: (-(t.get('pct_value') or 0),
                                      -(t.get('wins_value') or 0),
                                      -(t.get('differential_value') or 0)))
            divisions.append({'name': f'{conf_name} {div_name}', 'teams': teams})
        conferences.append({'name': conf_name, 'divisions': divisions})

    season = data.get('season') or {}
    payload = {
        'season': season.get('year'),
        'season_label': season.get('displayName') or data.get('name'),
        'conferences': conferences,
        'total_teams': len(rows),
    }
    return payload, STANDINGS_TTL


@require_http_methods(['GET'])
def standings(request):
    """League standings by conference and division, proxied from ESPN with
    a 5-minute cache. Records update as games go final."""
    try:
        return JsonResponse(_cached('standings', _standings_payload))
    except Exception as e:
        logger.error(f'standings proxy failed: {e}')
        return JsonResponse({'error': 'standings unavailable'}, status=502)
