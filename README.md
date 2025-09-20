# NFL Sports Information Web Application

**Last Updated:** September 15, 2025 at 12:00 PM EDT  
**Version:** 1.0.2  
**Status:** Development Ready

## Project Overview

This is a full-stack web application that provides comprehensive NFL sports information including game schedules, team statistics, player rosters, and real-time odds data. The application features a Django REST API backend with an SQLite database and a React frontend built with Vite.

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
- `home_team`: ForeignKey to Team
- `away_team`: ForeignKey to Team
- `week`: ForeignKey to Calendar

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
- `category`: CharField
- `stat_name`: CharField
- `value`: FloatField
- `rank`: IntegerField
- `display_rank`: CharField
- `description`: CharField

## API Endpoints

- `GET /`: API root with documentation.
- `GET /games/`: Current week games with odds and probabilities.
- `GET /games/<week_num>/`: Games for a specific week.
- `GET /team-schedule/<team_id>/`: Complete team schedule.
- `GET /matchup/<event_id>/`: Detailed game matchup information.
- `GET /teams/<team_id>/roster/`: Team roster with player details.
- `GET /teams/<team_id>/stats/`: Team season statistics.
- `GET /position/<str:position>/stats/`: Position-specific player statistics.

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

## Troubleshooting

### Common Issues
1. **CORS Errors:** Ensure frontend URL is in `CORS_ALLOWED_ORIGINS` in `backend/sports/settings.py`.
2. **Database Errors:** Run migrations after model changes (`python backend/manage.py migrate`).
3. **API Timeouts:** Check ESPN API availability and rate limits.
4. **Missing Logos:** Verify team logo files in `frontend/public/logos/`.
5. **Hardcoded URLs:** Ensure frontend components use relative paths for API calls by using the `get` function from `api.js` instead of hardcoding `http://localhost:8000`.
6. **Blank Page in Production:** If the application shows a blank page after running `build_frontend.sh`, it's likely an issue with static file serving. When `DEBUG` is `False`, Django doesn't serve static files automatically. The `build_frontend.sh` script places the built frontend files in `backend/staticfiles`, and the production server is configured to serve files from this directory. Ensure that the `start_production.sh` script is used to run the server, as it applies the correct production settings. If you've modified the build process or file locations, ensure that `sports/production_settings.py` and `sports/urls.py` are configured to find the static files.

