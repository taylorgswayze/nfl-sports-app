# NFL Sports Information Web Application

**Last Updated:** September 15, 2025 at 12:00 PM EDT  
**Version:** 1.0.2  
**Status:** Development Ready

## Project Overview

This is a full-stack web application that provides comprehensive NFL sports information including game schedules, team statistics, player rosters, and real-time odds data. The application features a Django REST API backend with an SQLite database and a React frontend built with Vite.

## The Week Room (fantasy roster advice)

Each league card on `/leagues` opens with the Week Room: the projected
optimal lineup vs the one set on Sleeper, free agents worth a claim with the
drop named, one-for-one trade ideas scored for both sides, and a short note.
Reports are stored per (Sleeper user, league) and reprinted every 12 hours
by `nfl.cron.WeekRoomRefresh`; `manage.py fantasy_insights --username X`
builds them by hand. Engine, validation and design: `PLAN-WEEK-ROOM.md`.
Optional prose via OpenAI (`OPENAI_API_KEY`, `OPENAI_MODEL` in `.env`).

## Architecture

### Backend (Django)
- **Framework:** Django 4.2.20 with Django REST Framework patterns
- **Database:** SQLite3 (development) - easily portable to PostgreSQL/MySQL for production
- **API:** RESTful endpoints serving JSON data
- **Data Sources:** ESPN Sports API integration
- **Cron Jobs:** Automated data refresh and player statistics updates

### Frontend (React)
- **Framework:** React 18.2.0 with React Router DOM for navigation
- **Build Tool:** Vite 4.1.0 for fast development and optimized builds
- **Styling:** CSS-in-JS with component-scoped styles
- **State Management:** React hooks (useState, useEffect)

## Project Structure

```
nfl-sports-app/
├── backend/
│   ├── sports/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── nfl/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── cron.py
│   │   ├── static_views.py
│   │   ├── migrations/
│   │   └── management/
│   │       └── commands/
│   ├── utils/
│   │   ├── get_data.py
│   │   ├── helpers.py
│   │   └── test.py
│   ├── db.sqlite3
│   └── manage.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── GameDisplay.jsx
│   │   │   ├── TeamSchedule.jsx
│   │   │   └── PositionStats.jsx
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── api.js
│   │   └── index.css
│   ├── public/
│   │   └── logos/
│   ├── dist/
│   ├── node_modules/
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   └── index.html
├── venv/
├── requirements.txt
├── .gitignore
└── README.md
```

## Database Schema

### Core Models

**Team**
- `team_id` (Primary Key): IntegerField
- `team_name`: CharField
- `short_name`: CharField
- `record`: CharField
- `last_updated`: DateTimeField

**Calendar**
- `id` (Primary Key): AutoField
- `name`: CharField
- `details`: CharField
- `week_num`: IntegerField
- `season`: IntegerField
- `season_type_name`: CharField
- `season_type_id`: IntegerField
- `start_date`: DateTimeField
- `end_date`: DateTimeField

**Game**
- `event_id` (Primary Key): IntegerField
- `short_name`: CharField
- `game_datetime`: DateTimeField
- `season`: IntegerField
- `week_num`: IntegerField
- `season_type_id`: IntegerField (2=regular season, 3=postseason)
- `home_team`: ForeignKey to Team
- `away_team`: ForeignKey to Team
- `week`: ForeignKey to Calendar
- `home_score` / `away_score`: IntegerField (null until played)
- `status`: CharField (`scheduled` / `in` / `final`)

**Outcome**
- `event_id` (Primary Key): OneToOneField to Game
- `spread_display`: CharField
- `spread`: IntegerField
- `home_win_prob`: FloatField
- `away_win_prob`: FloatField
- `pred_diff`: FloatField
- `last_updated`: DateTimeField

**Athlete**
- `athlete_id` (Primary Key): IntegerField
- `first_name`: CharField
- `last_name`: CharField
- `display_name`: CharField
- `jersey`: IntegerField
- `team`: ForeignKey to Team
- `position_id`: IntegerField
- `position`: CharField
- `position_abbreviation`: CharField
- `age`: IntegerField
- `weight`: IntegerField
- `height`: IntegerField
- `debut_year`: IntegerField
- `active`: CharField
- `status_id`: IntegerField
- `status`: CharField
- `injuries`: CharField

**SeasonStatistic**
- `id` (Primary Key): AutoField
- `athlete`: ForeignKey to Athlete
- `season_year`: IntegerField
- `season_type`: CharField
- `category_name`: CharField
- `stat_name`: CharField
- `stat_value`: DecimalField
- `stat_display_value`: CharField
- `last_updated`: DateTimeField

**GameStatistic**
- `id` (Primary Key): AutoField
- `athlete`: ForeignKey to Athlete
- `event_id`: CharField
- `game_date`: DateField
- `opponent`: CharField
- `category_name`: CharField
- `stat_name`: CharField
- `stat_value`: DecimalField
- `stat_display_value`: CharField
- `last_updated`: DateTimeField

**StatTeam**
- `id` (Primary Key): AutoField
- `team_id`: ForeignKey to Team
- `season`: IntegerField
- `category`: CharField
- `stat_name`: CharField
- `value`: FloatField
- `rank`: IntegerField
- `display_rank`: CharField
- `description`: CharField
- Unique on (team, season, category, stat_name)

### Legacy stat naming note

SeasonStatistic rows written before the 2026 rehab may carry meaningless
generated names (`stat_0` ... `stat_19`). All fetchers now store REAL ESPN
stat names (e.g. `passingYards`); the alias tables in
`nfl/views.py` (`position_stats`) exist only so those legacy rows keep
rendering. Once historical seasons are re-backfilled, the `stat_N` aliases
can be deleted.

## API Endpoints (all under `/api/`)

- `GET /`: API root with documentation.
- `GET /seasons/`: Seasons with available game data + current season.
- `GET /games/`: Current week games with scores, odds and probabilities.
  Params: `?season=`, `?season_type=` (2=regular [default], 3=postseason).
- `GET /games/<week_num>/`: Games for a specific week (same params).
- `GET /team-schedule/<team_id>/`: Team schedule with scores and W/L/T
  results. Params: `?season=`.
- `GET /matchup/<event_id>/`: Detailed game matchup information incl.
  scores/status and season-scoped team stats.
- `GET /teams/<team_id>/roster/`: Team roster with player details.
- `GET /teams/<team_id>/stats/`: Team season statistics. Params: `?season=`.
  Returns honest empty data (`has_stats: false`) when nothing is stored —
  no fabricated numbers.
- `GET /team-stat/<stat_name>/`: All teams ranked by one stat.
  Params: `?season=`.
- `GET /position/<str:position>/stats/`: Position-specific player
  statistics. Params: `?season=`.

## Data management commands

Run from `backend/` with the venv python:

- `manage.py backfill_season --season 2023 [--types 2,3] [--weeks 1-4]
  [--skip-game-stats] [--dry-run]`: full historical load for one season —
  calendar, teams, games with final scores, closing odds, season-keyed team
  stats/records, and per-game player boxscores (GameStatistic with real
  ESPN stat names; missing historical athletes are created).
  `--dry-run` prints planned request counts.
- `manage.py backfill_range --from 2020 --to 2024`: seasons oldest-first.
- `manage.py repair_data [--season 2025]`: repairs the pre-rehab calendar
  corruption (re-fetches the season calendar, repoints games, separates
  playoff weeks, removes junk team rows, purges cron-log spam).
- `manage.py update_recent_player_stats`: boxscore refresh of recently
  completed games (used by the 6-hourly cron job).
- `manage.py update_season_data` / `update_team_stats`: the hourly cron
  bodies (schedule+scores+odds, team stats).

## Frontend Components

### App.jsx
- **Purpose:** Main application component that handles routing.
- **Features:**
  - Uses `react-router-dom` to define routes for different views.
  - `GameDisplay`, `TeamSchedule`, and `PositionStats` components are rendered based on the URL.
  - Wrappers are used to pass URL parameters as props to components.

### GameDisplay.jsx
- **Purpose:** Main landing page displaying current week games.
- **Features:**
  - Week selector dropdown.
  - Game cards with team logos, records, and odds.
  - Win probability display.
  - Team navigation links.
- **State Management:** Games data, loading states, week selection.
- **API Integration:** Fetches games data.

### TeamSchedule.jsx
- **Purpose:** Comprehensive team information view.
- **Features:**
  - Three-tab interface: Schedule, Team Stats, Roster.
  - Complete season schedule display.
  - Roster organized by position groups (Offense/Defense/Special Teams).
  - Player links to position statistics.
  - Season selector for historical data.
- **Navigation:** React Router integration with URL parameters.
- **API Integration:** Fetches data for schedule, stats, and roster.

### PositionStats.jsx
- **Purpose:** Player position statistics and comparisons.
- **Features:**
    - Displays a table of players for a given position, with sortable columns for various stats.
    - Highlights the selected player.
    - Season selector for historical data.
- **API Integration:** Fetches position stats.

### api.js
- **Purpose:** Centralized API communication.
- **Features:**
  - Base URL configuration.
  - Error handling and response parsing.
  - A `get` function for making GET requests.

## Deployment

Host-standard deployment (matches every other app on this host): gunicorn
behind systemd plus a dedicated Cloudflare tunnel service. All assets live
in `deploy/`. Target host: Raspberry Pi (Debian 12, python3.11) with the
repo at `/home/t/projects/nfl-sports-app`.

```bash
# 1. venv + dependencies (venv shebangs are absolute — rebuild, never copy)
cd /home/t/projects/nfl-sports-app
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# 2. secrets
cp .env.example .env   # then put a freshly generated DJANGO_SECRET_KEY in it

# 3. migrate + sanity check
cd backend && ../venv/bin/python manage.py migrate
DJANGO_SECRET_KEY=$(grep -oP '(?<=DJANGO_SECRET_KEY=).*' ../.env) \
  ../venv/bin/python manage.py check --deploy --settings sports.production_settings

# 4. app service (gunicorn on 127.0.0.1:8001)
sudo cp ../deploy/nfl.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now nfl.service

# 5. cloudflare tunnel (needs ~/.cloudflared/3dd555b4-...json credentials)
cp ../deploy/nfl-tunnel.yml /home/t/.cloudflared/
sudo cp ../deploy/cloudflared-nfl.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now cloudflared-nfl.service

# 6. scheduled data refresh
crontab -e   # paste deploy/crontab.snippet
```

The old tmux + `runserver` + hand-run tunnel flow (`start_production.sh`)
is retired; use the systemd units.

## Troubleshooting

### Common Issues
1. **CORS Errors:** Ensure frontend URL is in `CORS_ALLOWED_ORIGINS` in `backend/sports/settings.py`.
2. **Database Errors:** Run migrations after model changes (`python backend/manage.py migrate`).
3. **API Timeouts:** Check ESPN API availability and rate limits.
4. **Missing Logos:** Verify team logo files in `frontend/public/logos/`.
5. **Hardcoded URLs:** Ensure frontend components use relative paths for API calls by using the `get` function from `api.js` instead of hardcoding `http://localhost:8000`.
6. **Blank Page in Production:** If the application shows a blank page after running `build_frontend.sh`, it's likely an issue with static file serving. When `DEBUG` is `False`, Django doesn't serve static files automatically. The `build_frontend.sh` script places the built frontend files in `backend/staticfiles`, and the production server is configured to serve files from this directory. Ensure that the `start_production.sh` script is used to run the server, as it applies the correct production settings. If you've modified the build process or file locations, ensure that `sports/production_settings.py` and `sports/urls.py` are configured to find the static files.

