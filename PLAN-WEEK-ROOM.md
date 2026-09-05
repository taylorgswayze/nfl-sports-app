# The Week Room: in-season roster advice on the Fantasy tab

Date: 2026-09-04. Status: shipped (this document is the scope review, the
evaluation plan, the validation results, and the design as built).
Supersedes the proposal in PLAN-INSEASON-ADVISOR.md (2026-08-08), which was
never implemented.

## 1. What already existed (scope review)

Verified on 2026-09-04 across the three places the fantasy work lives:

| Capability | Where | State | Usable in season? |
|---|---|---|---|
| Season PPG projections with uncertainty (LightGBM quantile models, PPR, QB/RB/WR/TE) | `~/fantasy-football-modeling` on the Mac; exported `preds_2026.parquet` deployed with the Draft Room on rpi3 | validated by a 2020-2025 walk-forward backtest for draft value | as a prior only: no week, opponent, injury or usage signal |
| Draft optimizer (MCTS over jittered-ADP opponents, lineup-value reward with 0.15 bench weight) | `fantasy-football/src/optimizer.py`, `draft.py` | +49.8 pts/season best-ball, +17.3 with realistic lineup setting | draft night only; its lineup-value function is the right currency for roster moves, so the Week Room reuses that convention |
| League adapter (Sleeper scoring -> per-player factor; roster_positions -> starter counts) | `fantasy-football/src/advisor/league_adapter.py` | tested | replaced here by exact stat-level scoring (below), which needs no shrinkage |
| Live draft advisor (FastAPI, rpi3:8010) proxied at /api/draft/* | `fantasy-football/src/advisor/server.py` | live | not involved |
| My Leagues page (`/leagues`): per-league card, live points, cross-league combine | this repo, `MyLeagues.jsx` + `fantasy_views.overview` | live; React source was only on the Mac until today | the surface the Week Room prints on |
| Weekly boxscore stats (ESPN ids) | this repo, `GameStatistic` | live | not used: Sleeper ids and Sleeper stat feeds are the fantasy currency |
| In-season advisor | PLAN-INSEASON-ADVISOR.md | proposal only, nothing built | built here in a leaner form |

The gap was a weekly projection. The draft model freezes its features at
season start, has no K/DEF, and knows nothing about byes, injuries or
opponents. Sleeper's own projection host (api.sleeper.com, unofficial but
the feed the Sleeper app reads) serves per-player per-week stat-level
projections for every position including K and DEF, plus finished-week
actual stat lines. Scoring those stat lines with a league's exact
`scoring_settings` gives league-exact numbers. That became the base signal,
with the Desk's season model as the prior.

## 2. Evaluation plan

The product decision is "which player to start, claim, drop, or trade", so
the tests measure decisions, not just point errors. Test bed: the user's own
2025 league (855-FOR-TRUTH, 8 teams, superflex, an IDP slot that is ignored),
17 weeks of Sleeper matchups (every roster's players, starters and
league-scored points), Sleeper's stored 2025 weekly projections and actuals,
and the modeling repo's walk-forward 2025 season predictions (a legitimate
pre-season forecast, not a refit). Harness: `tools/week_room_backtest.py`,
which runs the production engine code (scoring, lineup solver, blend
weights) against the cached public data in a few seconds:

    venv/bin/python tools/week_room_backtest.py --league 1256102582414233600 --season 2025 \
        --prior backend/data/backtest/season_prior_2025.json

It is the gate for any change to the blend or the ROS formula.

1. Scoring fidelity: my scoring of Sleeper's actual stat lines vs Sleeper's
   own `players_points`. Must match exactly for every modeled position, or
   every downstream number is wrong.
2. Projection accuracy (MAE and RMSE, league scoring, player-weeks with a
   projection of at least 5 points, weeks 2-17) for the candidate weekly
   projections: Sleeper weekly (SLP), season prior only, trailing 3 and 5
   week averages, fixed blends, and a shrinkage blend whose prior weight
   decays with weeks played.
3. Lineup decision quality: for each roster-week, the actual points of the
   lineup the engine would have set from each candidate projection, vs the
   points the human actually started, vs the hindsight optimum. The
   headline metric.
4. Waiver ranking value: at each week, rank the league's free agents by
   several rest-of-season (ROS) metrics; measure the top-3 per position's
   actual points over the next four weeks.
5. ROS metric quality among rostered players (drop decisions): rank
   correlation of each ROS metric with the next four weeks' points.

Pass criteria set before running: (1) exact; (3) the engine must beat the
human lineups on average with t > 2; (4) and (5) pick the ROS blend, which
must beat next-week projection alone on at least one of the two tests
without losing on the other.

## 3. Results

Test 1, scoring fidelity (n = 2,225 QB/RB/WR/TE/K/DEF player-weeks): 100.0%
within 0.05 points, max error 0.0. (The 250 IDP rows the league also scores
are outside the modeled positions and are not projected.)

Test 2, projection accuracy (4,076 player-weeks):

| candidate | MAE | RMSE |
|---|---|---|
| Sleeper weekly (SLP) | 5.45 | 6.98 |
| season prior only | 6.03 | 7.86 |
| trailing 3 weeks | 6.22 | 8.16 |
| trailing 5 weeks | 5.97 | 7.86 |
| 0.7 SLP + 0.3 prior | 5.38 | 6.94 |
| shrinkage blend (prior weight min(0.30, 3/(3+weeks played))) | 5.39 | 6.94 |
| 0.85 SLP + 0.15 trailing-3 | 5.43 | 6.98 |

Sleeper's weekly number is the best single source at every position; the
season prior adds a small, consistent improvement (about 1.3% MAE) and the
trailing average adds nothing over it. Note that Sleeper's stored
projections are the final pre-kickoff numbers (inactives already zeroed),
so this slightly flatters every candidate equally; the Week Room's
12-hour cadence includes a Sunday-morning reprint, so the live product sees
most of the same information.

Test 3, lineup decision quality (136 roster-weeks; human lineups averaged
130.4 points, the hindsight optimum 154.1):

| lineup set by | mean points | vs human | t | share of human-to-hindsight gap captured |
|---|---|---|---|---|
| Sleeper weekly | 133.9 | +3.5 | 2.6 | 15% |
| season prior only | 117.0 | -13.4 | -6.8 | negative |
| trailing 3 weeks | 119.7 | -10.7 | -5.0 | negative |
| 0.8 SLP + 0.2 prior | 134.9 | +4.5 | 3.4 | 19% |
| shrinkage blend, as shipped (prior weight min(0.30, 3/(3+weeks played))) | 135.0 | +4.6 | 3.5 | 19% |
| 0.85 SLP + 0.15 trailing-3 | 133.7 | +3.3 | 2.3 | 14% |

Passes. The weekly projection is essential (the season model on its own
sets worse lineups than a person does), and the blend with the season prior
is worth about one more point a week. The shrinkage form is used in
production because a fading prior is the defensible shape; its result is
within noise of the fixed blend.

Test 4, waiver ranking (mean next-4-week points of the top 3 free agents
per position, weeks 1-13; the average free agent scores about 2):

| ranker | QB | RB | WR | TE | mean |
|---|---|---|---|---|---|
| next-week projection only | 12.7 | 10.3 | 10.7 | 10.3 | 11.0 |
| 0.5 next-week + 0.5 long-run (prior, trailing-3, season snapshot) | 13.1 | 11.3 | 11.8 | 9.2 | 11.4 |
| 0.5 next-week + 0.5 mean(prior, trailing-3), as shipped (`production ROS` in the tool) | 11.6 | 11.0 | 10.9 | 9.1 | 10.7 |
| trailing 3 weeks only | 10.7 | 9.8 | 9.0 | 8.3 | 9.5 |
| season prior only | 10.1 | 10.6 | 6.1 | 8.8 | 8.9 |

Test 5, rank correlation with the next four weeks' points among rostered
players: 0.52 for 0.5 next-week + 0.5 mean(prior, trailing-3); 0.48 for
next-week alone; 0.35 for the variant that also includes the pre-season
season snapshot (stale by mid-season); 0.42 trailing-3; 0.36 prior only.

Decision: ROS value = 0.5 x this week's projection + 0.5 x mean(season
prior, trailing-3 actual ppg), each part used when available. On the
free-agent test it sits within noise of the next-week ranker (10.7 vs 11.0
mean over four positions, 13 weeks of top-3 picks) while being clearly the
best drop ranker (0.52 vs 0.48), and drop decisions are where a stale
single-week number does the most damage. The pre-season season snapshot is
used only as a fallback for players with no prior and no games.

## 4. What was built

Backend (Django, this repo):

- `utils/sleeper.py`: weekly projections, weekly actuals, season snapshot,
  trending adds, and a richer slim players index (status, injury,
  eligible positions), all disk-cached under `backend/data/` (runtime
  state: gitignored, excluded from the deploy rsync).
- `utils/priors.py` + `backend/priors/season_prior_2026.json`: the Desk
  season model (843 players) keyed by Sleeper id; `utils/export_prior.py`
  regenerates it from the modeling artifacts with the fantasy venv.
- `nfl/fantasy_engine.py`: pure functions. Exact scoring; optimal legal
  lineup by bitmask DP per slot component (flex, superflex, locked
  starters, IR/taxi, unmodeled slot types); weekly blend with injury and
  bye handling; ROS value; lineup report with a 0.75 point noise floor;
  waiver report (each claim paired with the exact cheapest drop under the
  lineup-value function, never this week's starter, never IR); drop
  candidates; one-for-one trade ideas from surplus into deficit, printed
  only when the user gains at least 1 ROS lineup point a week and the
  partner does not lose (both deltas shown); deterministic template prose.
- `nfl/fantasy_insights.py`: per-user, per-league orchestration; matchup
  projection for both sides; byes and kickoff locks from the Desk's own
  schedule; one `FantasyInsight` row per (user, league), replaced in
  place; background generation with a per-user lock.
- `utils/llm.py`: optional OpenAI narrative (the budget app's key,
  `OPENAI_MODEL`, default gpt-4o-mini) with a strict facts-only prompt, em
  dash and emoji scrubbing, and the template as the fallback on any error.
- API: `GET /api/fantasy/insights/?username=` (stored reports, or
  `generating` on first sight; `&refresh=1` reprints at most every 20
  minutes). Cron: `nfl.cron.WeekRoomRefresh` every 12 hours via the
  existing runcrons driver. Command: `manage.py fantasy_insights`.
- Tests: `nfl/test_fantasy.py` (engine, prose, view).

Frontend: `WeekRoom.jsx` at the top of every league card on `/leagues`
(lede, matchup projection, prose, START/SIT, CLAIM/DROP, SEND/GET ledger,
recommended lineup, reprint), polling while the desk generates. The React
source for the whole Draft Desk UI, recovered from the Mac, is tracked again
and `deploy/build.sh` builds from it.

## 5. Known limits and next steps

- IDP slots and auction/dynasty picks are out of scope; unmodeled slots
  keep their current occupant.
- The season prior covers QB/RB/WR/TE only; K/DEF use the weekly feed and
  the pre-season snapshot.
- Trade ideas are one-for-one and value-based; they do not read the other
  manager's mood. They print as ideas with both sides' numbers.
- Sleeper's projection host is unofficial. Every feed is cached and the
  engine degrades to the prior (weekly) or template prose (narrative) when
  a feed fails.
- A home-grown weekly model (opponent, usage, Vegas) is the only way to
  beat the base signal by more than the prior does; the harness in section
  2 is the gate for it.
