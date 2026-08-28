# Plan: Consolidating The Draft Room into nfl.taylorswayze.com

Date: 2026-08-08. Status: proposal, not yet started.

## 0. Verification of what runs where

Confirmed before planning: nfl.taylorswayze.com is served by the Gridiron Desk
app (Django + React) from /home/t/projects/nfl-sports-app on rpi3 via
`nfl.service` (gunicorn :8001) and `cloudflared-nfl.service`. The live-score
and box-score features shipped 2026-08-08 are visible on that domain, which
proves the deployed instance is the codebase this plan modifies.
fantasy.taylorswayze.com is The Draft Room: static pages plus FastAPI
(`fantasy.service`, uvicorn :8010, same rpi3 host), repo
taylorgswayze/fantasy-football with deployd auto-deploy, models exported from
~/fantasy-football-modeling on the Mac.

## 1. The two use cases (UX research summary)

Use case A, "follow the real game": check the slate, watch live scores, read
a box score, browse team schedules and stats. Casual, repeated, year-round,
read-only, mostly phone-sized sessions of a minute or two.

Use case B, "win my fantasy league": study the draft board in July and August,
run the live advisor on draft night, and (a natural extension) track my
players in season. Intense, seasonal, tool-like. Draft night is a high-stakes
two-hour session, usually on a phone or a second screen next to the Sleeper
app, where speed and scannability beat density (industry pattern: the best
draft tools keep everything in one screen and update without user action;
see Sleeper's draft room and DraftKings best-ball UX).

Key UX findings that shape the design:

- These are different modes, not different pages of one mode. Users arrive
  with one job in mind. The right pattern is a small number of top-level
  sections with a persistent switcher, exactly how a newspaper separates
  sections, which the Gridiron Desk metaphor already provides.
- Draft-night UX must be latency-first: one glance = current recommendation,
  no scrolling required for the top pick, refresh without interaction
  (the advisor already polls every 5s; keep that).
- Cross-linking is the payoff of consolidation: a board player should link to
  their real game log; a live box score should surface fantasy points (the
  Desk now computes PPR per game); in season, "my roster" should read live
  scoring from the same feed the slate uses.
- Two visual identities (night-edition almanac vs daylight field-green) must
  not coexist on one domain. Consolidation means adopting the Desk design
  system; the Draft Room becomes a section of the paper, not a guest.

## 2. Information architecture (target state)

Masthead gains a section switcher (styled like the existing printed controls):

- THE SLATE (current front page): scores, live games, box scores, teams.
- THE DRAFT DESK (new section, from The Draft Room):
  - /draft = the board (player value table, model v1/v2 toggle, position
    filters, search), restyled as a Desk almanac table.
  - /draft/advisor = the live advisor (Sleeper username, league picker,
    engine picker, recommendation panel), restyled as a live instrument.
  - /draft/about = the About/methodology page, printed as Desk footnotes.
- Seasonal default emphasis: during July and August the masthead promotes
  THE DRAFT DESK (a quiet "Draft season" flag); from week 1 the slate leads.

Cross-links once ids are joined (phase 3): board row -> player page with real
game log; game box score -> player's draft-board card; MY ROSTER (in-season) ->
live fantasy points per rostered player, from the existing boxscore endpoint.

## 3. Technical integration options considered

Option 1, reverse-proxy composition (fastest, days): route
nfl.taylorswayze.com/draft/* to the FastAPI service via cloudflared
path-based ingress (supported: ingress rules match hostname + path regex;
order rules before the catch-all to :8001). Keep the Draft Room pages as they
are, add masthead links both ways, 301 fantasy.taylorswayze.com to /draft.
Pros: near-zero code, keeps repo auto-deploy. Cons: two design systems on one
URL, no shared components, double mastheads, jarring on mobile. Acceptable
only as a transitional step.

Option 2, frontend unification with backend federation (RECOMMENDED):
rebuild board + advisor as React routes inside the Desk SPA, keep the FastAPI
service as the model/advice backend.

- Frontend: new routes /draft, /draft/advisor, /draft/about in the existing
  Vite app, using Desk furniture (Masthead, Folio, .stats tables, wire/notice
  states). The board is naturally a .stats table (it is already a sortable
  table with position chips); the advisor becomes a "live desk" panel using
  the same polling pattern as live scores.
- Backend: FastAPI stays the system of record for values and advice (it owns
  the parquet exports, league adaptation, Sleeper client, v1/v2 engines).
  Expose it under the nfl domain as /api/draft/* via cloudflared path ingress
  (preferred; zero Django changes) or a thin Django proxy view (fallback if
  ingress path matching misbehaves). Endpoints consumed: board data
  (currently board.json; serve it from FastAPI as /api/draft/board),
  /api/draft/leagues, /api/draft/advise.
- Deploys stay as they are: fantasy repo auto-deploys the model service;
  the Desk frontend deploys with the NFL app. The two release trains stay
  independent, which matters because model exports come from the Mac.

Option 3, full merge into Django (rejected): porting the advisor and value
serving into Django buys nothing, loses the fantasy repo's auto-deploy, and
drags the Polars/LightGBM export pipeline into the scores app's dependency
set. Model iteration velocity (freeze coming mid-Aug) argues for leaving the
Python service untouched.

## 4. Phased delivery

Phase 1, one afternoon: cloudflared ingress path rules on the nfl tunnel
(/api/draft/* -> :8010, plus temporary /draft/* -> :8010 static pages);
masthead cross-links in both apps; 301 redirect from the fantasy domain.
Ship value: one URL immediately, nothing breaks, rollback is trivial.

Phase 2, the real consolidation (1 to 2 days of focused work): React board
route (fetch /api/draft/board, Desk-styled table, model toggle, position
filter chips as Desk controls, search, sort); React advisor route (username ->
leagues -> advise loop with 5s polling during an active draft, recommendation
card printed as the lead story with alternatives as a ledger table); About
content moved into Desk footnote styling; retire the static pages; drop the
temporary /draft/* proxy; keep /api/draft/*.

Phase 3, the consolidation dividend (2 to 3 days, when wanted): player id
crosswalk (board uses gsis/sleeper ids, Desk uses ESPN ids; nflverse id
mapping tables join them; store espn_id on the board export or a mapping
table in the Desk DB). Then: board -> player game log links, box-score ->
board-card links, and MY ROSTER: read the user's Sleeper roster (public API,
username already the advisor's login) and print live fantasy points per
player from /api/game/<id>/boxscore/ during games. This turns the app from
draft-week tool into all-season companion, which is also the iOS app's core
screen (see PLAN-IOS-APP.md).

Phase 4, cleanup: retire fantasy.taylorswayze.com tunnel + service entry
after a few weeks of redirects, update the fleet manifest (run
fleet-manifest), update memory docs.

## 5. Design notes for the restyle (phase 2)

- The board keeps ALL current columns (pos, pos#, market, proj ppg, proj
  total, p10-p90 range, exp games, VBD value) but set in the Desk's .stats
  table with tabular numerals; leader rows use the existing green-tick idiom;
  position chips reuse the entry-flag style rather than colored pills.
- Model toggle (v1 ranking vs v2 value) becomes a printed control in the
  Folio line, with the honest one-line backtest blurb as a footnote, keeping
  the no-hype tone of both apps.
- Advisor states: idle (enter username), pre-draft (league loaded, draft not
  live: print roster settings the engine adapted to), on-the-clock (LIVE flag
  + recommendation as the lead entry + "survives until your next pick" odds
  as a gauge, reusing the win-probability gauge), between-picks (muted, next
  pick countdown), post-draft (final roster ledger).
- Mobile: advisor is a single-column stack, recommendation card first, no
  table wider than the viewport (tablewrap scroll for alternatives).

## 6. Risks and mitigations

- Cloudflared path ingress ordering mistakes could 404 the API: stage the
  ingress change with a curl checklist before DNS-level redirect; rollback is
  restoring the previous sports-info-tunnel.yml.
- rpi3 headroom: both services already run there (37 MB + 83 MB RSS); no new
  processes are added. Fine.
- The two repos drift visually: mitigated by moving all UI into the Desk repo
  in phase 2; the fantasy repo keeps zero user-facing HTML afterward.
- Sleeper API rate limits during draft night: unchanged from today (the
  FastAPI advisor already throttles per draft, 3s).
- No git repo on the NFL app remains the top operational risk: initialize a
  repo for nfl-sports-app before phase 2 lands so deploys and rollbacks match
  the fleet's normal pipeline (this also fixes the rpi5/rpi3 drift that was
  found and patched on 2026-08-08).
