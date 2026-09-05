"""Sleeper public-API client with per-endpoint TTL caching.

Read-only, unauthenticated endpoints (https://docs.sleeper.com) plus the
undocumented projections/stats host that Sleeper's own apps read
(https://api.sleeper.com), which the Week Room engine uses for weekly
stat-level projections and finished-week actuals. Heavy payloads (the ~15
MB players dump, the ~2 MB weekly projection files) are slimmed and cached on
disk under backend/data/ (runtime state: gitignored, excluded from deploy
rsync); everything else lives in a small in-memory TTL cache so the
my-leagues overview stays cheap to poll.
"""
import json
import logging
import threading
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

BASE = 'https://api.sleeper.app/v1'
DATA_BASE = 'https://api.sleeper.com'
DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
PLAYERS_CACHE = DATA_DIR / 'sleeper_players_v2.json'
PLAYERS_TTL = 24 * 3600
PROJ_TTL = 6 * 3600
STATS_TTL = 12 * 3600
SEASON_PROJ_TTL = 24 * 3600
POSITIONS = ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')

session = requests.Session()
session.headers['User-Agent'] = 'gridiron-desk/1.0'

_cache = {}
_lock = threading.Lock()


def _get_json(path, timeout=20, base=BASE):
    r = session.get(f'{base}{path}', timeout=timeout)
    r.raise_for_status()
    return r.json()


def _cached(key, ttl, fetch):
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    data = fetch()
    with _lock:
        _cache[key] = (now + ttl, data)
    return data


def _disk_cached(path, ttl, fetch, mem_ttl=3600):
    """Disk-then-memory cache for large, slow-changing payloads."""
    key = f'disk:{path.name}'
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
    data = None
    try:
        if path.exists() and (time.time() - path.stat().st_mtime < ttl):
            data = json.loads(path.read_text())
    except Exception as e:
        logger.warning(f'cache read failed for {path.name}: {e}')
    if data is None:
        data = fetch()
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        except Exception as e:
            logger.warning(f'cache write failed for {path.name}: {e}')
    with _lock:
        _cache[key] = (time.monotonic() + mem_ttl, data)
    return data


def state():
    """League-wide NFL state: season, week, season_type."""
    return _cached('state', 300, lambda: _get_json('/state/nfl'))


def user(username):
    return _cached(f'user:{username.lower()}', 3600,
                   lambda: _get_json(f'/user/{username}') or {})


def leagues(user_id, season):
    return _cached(f'leagues:{user_id}:{season}', 300,
                   lambda: _get_json(f'/user/{user_id}/leagues/nfl/{season}') or [])


def league(league_id):
    return _cached(f'league:{league_id}', 600,
                   lambda: _get_json(f'/league/{league_id}') or {})


def league_rosters(league_id):
    return _cached(f'rosters:{league_id}', 60,
                   lambda: _get_json(f'/league/{league_id}/rosters') or [])


def league_users(league_id):
    return _cached(f'users:{league_id}', 600,
                   lambda: _get_json(f'/league/{league_id}/users') or [])


def league_matchups(league_id, week):
    return _cached(f'matchups:{league_id}:{week}', 25,
                   lambda: _get_json(f'/league/{league_id}/matchups/{week}') or [])


def trending_adds(hours=48, limit=60):
    """[{player_id, count}] most-added players league-wide; a market signal
    for the waiver report. Empty on any failure."""
    def fetch():
        try:
            return _get_json(f'/players/nfl/trending/add?lookback_hours={hours}&limit={limit}') or []
        except Exception as e:
            logger.warning(f'trending adds unavailable: {e}')
            return []
    return _cached(f'trending:{hours}:{limit}', 1800, fetch)


def _positions_query():
    return '&'.join(f'position[]={p}' for p in POSITIONS)


def weekly_projections(season, week):
    """{player_id: {stats, pos, team, opp, injury}} for one regular-season
    week from Sleeper's projection feed (stat-level, so any league's
    scoring_settings can be applied exactly). Disk-cached for 6 hours."""
    def fetch():
        rows = _get_json(
            f'/projections/nfl/{season}/{week}?season_type=regular&{_positions_query()}&order_by=pts_ppr',
            timeout=60, base=DATA_BASE) or []
        out = {}
        for r in rows:
            p = r.get('player') or {}
            pos = p.get('position')
            if pos not in POSITIONS:
                continue
            stats = r.get('stats') or {}
            out[str(r['player_id'])] = {
                'stats': {k: v for k, v in stats.items() if not k.startswith(('adp_', 'pos_adp'))},
                'pos': pos, 'team': r.get('team') or p.get('team'),
                'opp': r.get('opponent'), 'injury': p.get('injury_status'),
            }
        return out
    return _disk_cached(DATA_DIR / f'proj_{season}_w{week}.json', PROJ_TTL, fetch)


def weekly_stats(season, week):
    """{player_id: stats} actual stat lines for a finished (or in-progress)
    regular-season week. Disk-cached for 12 hours."""
    def fetch():
        rows = _get_json(
            f'/stats/nfl/{season}/{week}?season_type=regular&{_positions_query()}&order_by=pts_ppr',
            timeout=60, base=DATA_BASE) or []
        return {str(r['player_id']): (r.get('stats') or {}) for r in rows
                if (r.get('player') or {}).get('position') in POSITIONS}
    return _disk_cached(DATA_DIR / f'stats_{season}_w{week}.json', STATS_TTL, fetch)


def season_projections(season):
    """{player_id: stats} season-total stat projections (the pre-season
    snapshot Sleeper serves alongside ADP). Used only as a fallback prior
    for players the ML model does not cover. Disk-cached for a day."""
    def fetch():
        rows = _get_json(
            f'/projections/nfl/{season}?season_type=regular&{_positions_query()}&order_by=adp_ppr',
            timeout=60, base=DATA_BASE) or []
        return {str(r['player_id']): {k: v for k, v in (r.get('stats') or {}).items()
                                      if not k.startswith(('adp_', 'pos_adp'))}
                for r in rows if (r.get('player') or {}).get('position') in POSITIONS}
    return _disk_cached(DATA_DIR / f'season_proj_{season}.json', SEASON_PROJ_TTL, fetch)


def players():
    """Slim {player_id: {name, pos, positions, team, status, injury, exp}}
    index, disk-cached for a day.

    Includes team DEF entries (id like 'PHI') which the full dump also has.
    """
    def fetch():
        raw = _get_json('/players/nfl', timeout=90)
        slim = {}
        for pid, p in raw.items():
            if not isinstance(p, dict):
                continue
            name = p.get('full_name') or (
                f"{p.get('first_name', '')} {p.get('last_name', '')}".strip())
            slim[pid] = {
                'name': name or pid,
                'pos': p.get('position'),
                'positions': p.get('fantasy_positions') or ([p['position']] if p.get('position') else []),
                'team': p.get('team'),
                'status': p.get('status'),
                'injury': p.get('injury_status'),
                'exp': p.get('years_exp'),
            }
        return slim
    return _disk_cached(PLAYERS_CACHE, PLAYERS_TTL, fetch)
