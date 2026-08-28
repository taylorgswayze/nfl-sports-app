# Plan: Gridiron Desk as a native Swift iOS app

Date: 2026-08-08. Status: proposal, not yet started. Companion to
PLAN-DRAFT-ROOM-CONSOLIDATION.md (the web consolidation should land first, or
at least the /api/draft/* federation, so the app talks to one API surface).

## 1. Why native, and what it buys

The web app already covers browsing. Native buys exactly the things Safari
cannot do (verified against WWDC 2026 / iOS 27 state of the platform):

- Live Activities: persistent, silently updating score card on the lock
  screen and Dynamic Island for a followed game. ActivityKit is native-only.
- Widgets: today's slate or your team's next game on the home screen.
- Push notifications with tight OS integration (scores, red zone, your
  fantasy players), plus Time Sensitive delivery through Focus modes.
- Draft-night ergonomics: a real full-screen advisor with local notifications
  when you are on the clock, no Safari tab discipline required.

## 2. Architecture

Thin native client over the existing self-hosted APIs. No new database, no
duplicate business logic on the phone.

- App: SwiftUI, iOS 17+ target (Observation framework, TimelineView), MVVM
  with a small APIClient (URLSession + async/await + Codable structs mirroring
  the JSON the web app already consumes).
- Backend, read paths (all existing): /api/games/, /api/live/ (20s server
  cache), /api/game/<id>/boxscore/ (player stats + fantasy points),
  /api/matchup/, /api/teams/..., /api/draft/board, /api/draft/advise.
- Backend, one new component: a push daemon ("desk-pusher", small Python
  service on rpi5) that polls /api/live/ on the same cadence the site does,
  detects deltas (score change, possession change, quarter, final), and sends
  APNs pushes: remote notifications for subscribed alert types, and Live
  Activity update pushes (APNs token-based auth, HTTP/2, `liveactivity` push
  type) for any activity tokens registered with it.
- New tiny API on the Django side for device state: register device token,
  register/unregister a Live Activity token for an event id, notification
  preferences. Keyed by device, no user accounts needed; endpoint should be
  rate-limited and unlisted since the fleet is otherwise Taylor-only.

Data flow for a Live Activity: app starts activity for event -> receives
ActivityKit push token -> POSTs it to Django -> desk-pusher polls /api/live/,
on delta pushes updated content-state to APNs -> lock screen updates ->
pusher ends the activity at final. Update budget: score/possession/quarter
changes only (a few dozen per game), well inside ActivityKit budgets; request
the frequent-updates entitlement only if red-zone pulse updates are wanted.

## 3. Screens (mirroring the consolidated IA)

1. The Slate (home): week's games, live cards pinned first with score, clock,
   possession; pull-to-refresh plus 30s auto-refresh; season/week pickers.
   Tapping a live card offers "Pin to Lock Screen" (starts the Live Activity).
2. Game Desk: header score (live-polling), box score categories, fantasy
   points table, head-to-head ledger. Same data as web, native tables.
3. Team Desk: schedule + season stats.
4. The Draft Desk: board (searchable, filterable, v1/v2 toggle) and Live
   Advisor (Sleeper username stored in app storage; 5s polling during an
   active draft; local notification "You are on the clock" when pick index
   hits; recommendation card with survival odds).
5. My Roster (in-season, after the consolidation phase 3 crosswalk exists):
   live fantasy points for the user's Sleeper roster, the screen most likely
   to become the app's daily driver.
6. Settings: favorite team, notification toggles (game start, score change,
   final, red zone, fantasy player scores), advisor engine default.

Design language: carry the Night Edition almanac over (dark stock, bone ink,
single green accent, tabular numerals via SF Mono / New York serif accents).
It will look deliberately un-iOS in the best way, and it keeps parity with
the web app.

## 4. Live Activity design

- Lock screen card: away/home abbreviations + logos, big scores, quarter and
  clock, possession dot, down and distance line; final state shows FINAL and
  persists briefly, then ends.
- Dynamic Island: compact = two scores; minimal = leading team abbr; expanded
  = full card with last play text.
- Widgets (WidgetKit, shares the APIClient via an App Group): small = next or
  live game for favorite team; medium = today's slate top 3; refresh via
  timeline (15 min) plus push-triggered reload when a followed game is live.

## 5. Delivery phases

Phase 1, read-only scores app (2 to 3 sessions of work): project scaffold
(XcodeGen or plain project in ~/projects/gridiron-ios, buildable via
xcodebuild for agent-driven iteration, simulator testing), APIClient +
models, Slate + Game Desk + Team screens, settings stub. Runs against the
production API immediately.

Phase 2, Live Activities + widgets (2 to 3 sessions): ActivityKit UI,
device/activity-token registration endpoints in Django, desk-pusher daemon
(aioapns), APNs key setup, end-to-end on-device test during a real game
window (preseason games make this testable in August), WidgetKit extension.

Phase 3, Draft Desk (1 to 2 sessions): board + advisor screens over
/api/draft/*, on-the-clock local notifications. Best landed before draft
night; the web advisor remains the fallback.

Phase 4, My Roster + alert notifications (after web phase 3 crosswalk):
roster screen, desk-pusher alert rules (score change for followed team,
fantasy player TD), notification preference plumbing.

## 6. Distribution and accounts (the honest constraints)

- Apple Developer Program, $99/year, is effectively required: it enables
  APNs (without which Live Activities cannot update from the server),
  TestFlight installs that last 90 days, and stable personal deployment.
- Free-account sideloading works for phase 1 only (7-day resign cycle, no
  push). Fine for a first look, wrong for the destination.
- App Review is not needed: TestFlight internal testing or direct Xcode
  install covers personal use. Nothing in the app violates ESPN/Sleeper
  terms differently than the website already does, but it stays personal,
  not App Store distributed.

## 7. Risks

- APNs plumbing is the only genuinely new infrastructure; isolate it in
  desk-pusher so the web stack stays untouched. Test with the APNs sandbox
  first.
- ActivityKit update budgets: stick to state-change-driven updates; do not
  stream the clock every second (the OS interpolates the timer display from
  the content state's date fields anyway).
- ESPN unofficial API drift breaks the app and site together; the shared
  server-side proxy means one fix covers both.
- Xcode-on-CI ergonomics: agent-driven iteration needs xcodebuild + simulator
  workflows on the Mac mini; budget a session for scaffolding that cleanly.
