"""Export the season projection prior consumed by the Week Room engine.

Reads the fantasy-football-modeling artifacts (preds_<season>.parquet and
the nflverse id crosswalk) and writes backend/priors/season_prior_<season>.json
keyed by Sleeper player_id. Needs polars, so run it with the fantasy
service's venv, not the Desk venv:

    ~/projects/fantasy-football/venv/bin/python backend/utils/export_prior.py \
        --model-root ~/projects/fantasy-football --season 2026

Commit the JSON; the engine reads it at startup (utils.priors).
"""
import argparse
import datetime as dt
import json
from pathlib import Path

import polars as pl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-root', required=True)
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    root = Path(a.model_root).expanduser()
    ids = (pl.read_parquet(root / 'data' / 'raw' / 'ff_playerids.parquet')
           .select(pl.col('sleeper_id').cast(pl.Utf8, strict=False), 'gsis_id')
           .drop_nulls())
    preds = pl.read_parquet(root / 'data' / 'processed' / f'preds_{a.season}.parquet')
    preds = preds.join(ids, left_on='player_id', right_on='gsis_id', how='left')
    players = {}
    for r in preds.drop_nulls('sleeper_id').to_dicts():
        if r.get('ml_ppg') is None:
            continue
        players[r['sleeper_id']] = {
            'name': r.get('player_display_name'), 'pos': r.get('position'),
            'ppg': round(r['ml_ppg'], 2),
            'p10': round(r['ml_p10'], 2) if r.get('ml_p10') is not None else None,
            'p90': round(r['ml_p90'], 2) if r.get('ml_p90') is not None else None,
            'games': round(r['exp_games_ml'], 1) if r.get('exp_games_ml') is not None else None,
        }
    out = Path(a.out or Path(__file__).resolve().parent.parent / 'priors' / f'season_prior_{a.season}.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        'season': a.season,
        'source': f'fantasy-football-modeling preds_{a.season}.parquet (LightGBM quantile PPR ppg), keyed by Sleeper player_id via ff_playerids',
        'exported': dt.date.today().isoformat(),
        'players': players,
    }, separators=(',', ':')))
    print(f'{len(players)} players -> {out}')


if __name__ == '__main__':
    main()
