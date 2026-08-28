"""Sleeper public-API client with per-endpoint TTL caching.

Read-only, unauthenticated endpoints (https://docs.sleeper.com). The heavy
players dump (~5 MB) is slimmed to (name, pos, team) and cached on disk for a
day; everything else lives in a small in-memory TTL cache so the my-leagues
overview stays cheap to poll.
"""
import json
import logging
import threading
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

BASE = 'https://api.sleeper.app/v1'
PLAYERS_CACHE = Path(__file__).resolve().parent.parent / 'sleeper_players_cache.json'
PLAYERS_TTL = 24 * 3600

session = requests.Session()
session.headers['User-Agent'] = 'gridiron-desk/1.0'

_cache = {}
_lock = threading.Lock()


def _get_json(path, timeout=20):
    r = session.get(f'{BASE}{path}', timeout=timeout)
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


def state():
    """League-wide NFL state: season, week, season_type."""
    return _cached('state', 300, lambda: _get_json('/state/nfl'))


def user(username):
    return _cached(f'user:{username.lower()}', 3600,
                   lambda: _get_json(f'/user/{username}') or {})


def leagues(user_id, season):
    return _cached(f'leagues:{user_id}:{season}', 300,
                   lambda: _get_json(f'/user/{user_id}/leagues/nfl/{season}') or [])


def league_rosters(league_id):
    return _cached(f'rosters:{league_id}', 60,
                   lambda: _get_json(f'/league/{league_id}/rosters') or [])


def league_users(league_id):
    return _cached(f'users:{league_id}', 600,
                   lambda: _get_json(f'/league/{league_id}/users') or [])


def league_matchups(league_id, week):
    return _cached(f'matchups:{league_id}:{week}', 25,
                   lambda: _get_json(f'/league/{league_id}/matchups/{week}') or [])


def players():
    """Slim {player_id: {name, pos, team}} index, disk-cached for a day.

    Includes team DEF entries (id like 'PHI') which the full dump also has.
    """
    with _lock:
        hit = _cache.get('players')
        if hit and hit[0] > time.monotonic():
            return hit[1]

    slim = None
    try:
        if PLAYERS_CACHE.exists() and (
                time.time() - PLAYERS_CACHE.stat().st_mtime < PLAYERS_TTL):
            slim = json.loads(PLAYERS_CACHE.read_text())
    except Exception as e:
        logger.warning(f'players cache read failed: {e}')

    if slim is None:
        raw = _get_json('/players/nfl', timeout=60)
        slim = {}
        for pid, p in raw.items():
            if not isinstance(p, dict):
                continue
            name = p.get('full_name') or (
                f"{p.get('first_name', '')} {p.get('last_name', '')}".strip())
            slim[pid] = {
                'name': name or pid,
                'pos': p.get('position'),
                'team': p.get('team'),
            }
        try:
            PLAYERS_CACHE.write_text(json.dumps(slim))
        except Exception as e:
            logger.warning(f'players cache write failed: {e}')

    with _lock:
        _cache['players'] = (time.monotonic() + 3600, slim)
    return slim
