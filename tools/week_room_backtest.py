#!/usr/bin/env python3
"""Week Room backtest: the evaluation gate for the projection blend and the
rest-of-season (ROS) value used by nfl/fantasy_engine.py.

Replays one finished Sleeper league season with the production engine code
(scoring, lineup solver, blend weights) against Sleeper's stored weekly
projections and actuals. Five tests, see PLAN-WEEK-ROOM.md section 2:

  1. scoring fidelity vs Sleeper's own players_points (must be exact)
  2. weekly projection accuracy (MAE/RMSE) for each candidate blend
  3. lineup decision quality: engine lineups vs the humans' vs hindsight
  4. waiver ranking: future points of the top-3 free agents per position
  5. ROS metric rank correlation with the next four weeks, rostered players

Run from the repo root with the Desk venv (numpy, requests):

  venv/bin/python tools/week_room_backtest.py --league 1256102582414233600 --season 2025

Data is fetched once into --cache (default backend/data/backtest/, about
50 MB per season) and reused. Pass --prior to point at a season prior JSON
(default backend/priors/season_prior_<season>.json; the 2025 walk-forward
prior used for the shipped numbers came from preds_ml.parquet, see
backend/utils/export_prior.py).
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'backend'))
from nfl import fantasy_engine as fe  # noqa: E402

POS = ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
V1 = 'https://api.sleeper.app/v1'
DATA = 'https://api.sleeper.com'


def fetch(cache, name, url):
    path = cache / name
    if path.exists():
        return json.loads(path.read_text())
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    path.write_text(r.text)
    return r.json()


def load(cache, league_id, season, weeks):
    q = '&'.join(f'position[]={p}' for p in POS)
    league = fetch(cache, f'league_{league_id}.json', f'{V1}/league/{league_id}')
    players = fetch(cache, 'players_nfl.json', f'{V1}/players/nfl')
    proj, stats, matchups = {}, {}, {}
    for w in range(1, weeks + 1):
        proj[w] = {r['player_id']: r for r in fetch(
            cache, f'proj_{season}_{w}.json',
            f'{DATA}/projections/nfl/{season}/{w}?season_type=regular&{q}&order_by=pts_ppr')}
        stats[w] = {r['player_id']: r for r in fetch(
            cache, f'stats_{season}_{w}.json',
            f'{DATA}/stats/nfl/{season}/{w}?season_type=regular&{q}&order_by=pts_ppr')}
        matchups[w] = fetch(cache, f'matchups_{league_id}_{w}.json', f'{V1}/league/{league_id}/matchups/{w}')
    season_proj = {r['player_id']: r for r in fetch(
        cache, f'season_proj_{season}.json',
        f'{DATA}/projections/nfl/{season}?season_type=regular&{q}&order_by=adp_ppr')}
    return league, players, proj, stats, matchups, season_proj


def positions_of(players, pid, row=None):
    p = players.get(pid) or {}
    fp = p.get('fantasy_positions') or ([p['position']] if p.get('position') else [])
    if not fp and row:
        pr = row.get('player') or {}
        fp = pr.get('fantasy_positions') or [pr.get('position')]
    return [x for x in fp if x]


def spearman(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    rx = x.argsort().argsort(); ry = y.argsort().argsort()
    return float(np.corrcoef(rx, ry)[0, 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--league', required=True, help='a finished Sleeper league id (previous_league_id)')
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--weeks', type=int, default=17)
    ap.add_argument('--cache', default=str(ROOT / 'backend' / 'data' / 'backtest'))
    ap.add_argument('--prior', default=None)
    a = ap.parse_args()
    cache = Path(a.cache); cache.mkdir(parents=True, exist_ok=True)
    league, players, proj, stats, matchups, season_proj = load(cache, a.league, a.season, a.weeks)
    S = league['scoring_settings']
    prior_path = Path(a.prior) if a.prior else ROOT / 'backend' / 'priors' / f'season_prior_{a.season}.json'
    prior = json.loads(prior_path.read_text()).get('players', {}) if prior_path.exists() else {}
    print(f"league {league['name']} {league['season']}: {league['settings'].get('num_teams')} teams, "
          f"{league['roster_positions']}; prior players: {len(prior)}")

    # --- test 1: scoring fidelity ---
    diffs = []
    for w, ms in matchups.items():
        for m in ms:
            for pid, pts in (m.get('players_points') or {}).items():
                if (players.get(pid) or {}).get('position') not in POS:
                    continue
                row = stats[w].get(pid)
                diffs.append(abs(pts) if row is None else abs(fe.score(row['stats'], S) - pts))
    d = np.array(diffs)
    print(f'\nTEST 1 scoring fidelity: n={len(d)} exact(<=0.05)={np.mean(d <= 0.05):.4f} max={d.max():.2f}')

    # --- candidate projections ---
    factor = {}
    for pid, r in season_proj.items():
        st = r.get('stats') or {}
        ppr = fe.score(st, fe.PPR)
        if ppr > 20:
            factor[pid] = fe.score(st, S) / ppr
    actual = {w: {pid: fe.score(r['stats'], S) for pid, r in stats[w].items()} for w in stats}

    def slp(w, pid):
        r = proj[w].get(pid)
        return fe.score(r['stats'], S) if r else None

    def prior_ppg(pid):
        p = prior.get(pid)
        return None if not p or p.get('ppg') is None else float(p['ppg']) * factor.get(pid, 1.0)

    def trailing(w, pid, k=3):
        vals = [actual[v][pid] for v in range(max(1, w - k), w) if pid in actual[v]]
        return sum(vals) / len(vals) if vals else None

    def production_blend(w, pid):
        s = slp(w, pid); p = prior_ppg(pid)
        if s is None:
            return None
        if p is None:
            return s
        wp = fe.prior_weight(w)
        return (1 - wp) * s + wp * p

    def production_ros(w, pid):
        s = slp(w, pid)
        parts = [x for x in (prior_ppg(pid), trailing(w, pid)) if x is not None]
        longrun = sum(parts) / len(parts) if parts else None
        nxt = s if (s is not None and s > 0) else longrun
        if nxt is None:
            return None
        if longrun is None:
            longrun = nxt
        return 0.5 * nxt + 0.5 * longrun

    cands = {
        'sleeper weekly': slp,
        'season prior only': lambda w, pid: prior_ppg(pid),
        'trailing 3': lambda w, pid: trailing(w, pid, 3),
        'production blend (shrink prior)': production_blend,
    }

    # --- test 2 ---
    rows = []
    for w in range(2, a.weeks + 1):
        for pid, r in proj[w].items():
            s = slp(w, pid)
            if s is None or s < 5 or (r.get('player') or {}).get('position') not in POS:
                continue
            rows.append((w, pid, actual[w].get(pid, 0.0)))
    print(f'\nTEST 2 projection accuracy (league scoring, proj >= 5, weeks 2-{a.weeks}), n={len(rows)}')
    for name, f in cands.items():
        e = np.array([f(w, pid) - act for w, pid, act in rows if f(w, pid) is not None])
        print(f'  {name:32s} MAE {np.abs(e).mean():6.3f}  RMSE {np.sqrt((e ** 2).mean()):6.3f}  cover {len(e) / len(rows):.2f}')

    # --- test 3 ---
    slots = [s for s in fe.starting_slots(league['roster_positions']) if s in fe.SLOT_ELIG]
    all_slots = fe.starting_slots(league['roster_positions'])
    idx = [i for i, s in enumerate(all_slots) if s in fe.SLOT_ELIG]
    res = defaultdict(list)
    for w in range(1, a.weeks + 1):
        for m in matchups[w]:
            pp = m.get('players_points') or {}
            roster = m.get('players') or []
            starters = m.get('starters') or []
            human = sum(pp.get(starters[i], 0.0) for i in idx if i < len(starters) and starters[i] not in (None, '0', ''))
            hind = fe.optimal_lineup(slots, [(pid, positions_of(players, pid), pp.get(pid, 0.0)) for pid in roster])[0]
            res['human'].append(human); res['hindsight'].append(hind)
            for name, f in cands.items():
                c = []
                for pid in roster:
                    v = f(w, pid)
                    if v is None:
                        v = slp(w, pid) or 0.0
                    c.append((pid, positions_of(players, pid, proj[w].get(pid)), v))
                _t, asg = fe.optimal_lineup(slots, c)
                res[name].append(sum(pp.get(pid, 0.0) for pid in asg.values()))
    h = np.array(res['human']); hs = np.array(res['hindsight'])
    print(f'\nTEST 3 lineup decision quality: {len(h)} roster-weeks, human {h.mean():.2f}, hindsight {hs.mean():.2f}')
    for name in cands:
        e = np.array(res[name]); dlt = e - h
        t = dlt.mean() / (dlt.std(ddof=1) / math.sqrt(len(dlt)))
        print(f'  {name:32s} {e.mean():7.2f}  vs human {dlt.mean():+6.2f} (t={t:5.2f})  '
              f'gap captured {(e.mean() - h.mean()) / (hs.mean() - h.mean()):+.2f}')

    # --- tests 4 and 5 ---
    rankers = {'next-week projection': slp, 'trailing 3': lambda w, pid: trailing(w, pid),
               'season prior': lambda w, pid: prior_ppg(pid), 'production ROS': production_ros}
    fut = defaultdict(list)
    last = min(a.weeks - 4, 13)
    for w in range(1, last + 1):
        rostered = set()
        for m in matchups[w]:
            rostered.update(m.get('players') or [])
        for pos in ('QB', 'RB', 'WR', 'TE'):
            fas = [pid for pid, r in proj[w].items() if pid not in rostered
                   and (r.get('player') or {}).get('position') == pos and (r.get('player') or {}).get('team')
                   and (players.get(pid) or {}).get('status') == 'Active']

            def future(pid):
                return sum(actual[v].get(pid, 0.0) for v in range(w + 1, min(w + 5, a.weeks + 1))) / 4
            for name, f in rankers.items():
                sc = sorted([(f(w, pid), pid) for pid in fas if f(w, pid) is not None], reverse=True)[:3]
                if sc:
                    fut[(name, pos)].append(np.mean([future(pid) for _v, pid in sc]))
    print(f'\nTEST 4 waiver ranking: next-4-week ppg of the top-3 free agents per position, weeks 1-{last}')
    print(f"  {'ranker':32s} " + ' '.join(f'{p:>6s}' for p in ('QB', 'RB', 'WR', 'TE')))
    for name in rankers:
        print(f'  {name:32s} ' + ' '.join(f'{np.mean(fut[(name, p)]):6.2f}' for p in ('QB', 'RB', 'WR', 'TE')))
    print(f'\nTEST 5 rank correlation with next-4-week points, rostered players, weeks 2-{last}')
    for name, f in rankers.items():
        xs, ys = [], []
        for w in range(2, last + 1):
            for m in matchups[w]:
                for pid in m.get('players') or []:
                    v = f(w, pid)
                    if v is None:
                        continue
                    xs.append(v); ys.append(sum(actual[u].get(pid, 0.0) for u in range(w + 1, min(w + 5, a.weeks + 1))))
        print(f'  {name:32s} spearman {spearman(xs, ys):.3f}  n={len(xs)}')


if __name__ == '__main__':
    main()
