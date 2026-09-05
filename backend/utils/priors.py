"""Season projection prior (ML, PPR points per game) keyed by Sleeper id.

Loaded once per process from backend/priors/season_prior_<season>.json,
which backend/utils/export_prior.py regenerates from the modeling repo.
Missing season file -> empty prior; the engine then leans entirely on the
weekly projections, which the 2025 backtest showed is still a strong
lineup setter (+3.5 pts/week over human lineups vs +4.5 with the prior).
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PRIORS_DIR = Path(__file__).resolve().parent.parent / 'priors'
_loaded = {}


def season_prior(season):
    season = int(season)
    if season in _loaded:
        return _loaded[season]
    path = PRIORS_DIR / f'season_prior_{season}.json'
    players = {}
    try:
        if path.exists():
            players = json.loads(path.read_text()).get('players') or {}
        else:
            logger.warning(f'no season prior file for {season} ({path.name})')
    except Exception as e:
        logger.warning(f'season prior load failed: {e}')
    _loaded[season] = players
    return players
