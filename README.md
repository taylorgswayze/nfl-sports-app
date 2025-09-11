# NFL Sports Information Web Application

**Last Updated:** September 11, 2025 at 5:38 PM EDT  
**Version:** 1.0.0  
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
nfl-2/
├── backend/                    # Django backend application
│   ├── sports/                # Main Django project configuration
│   │   ├── settings.py        # Django settings with CORS, database config
│   │   ├── urls.py            # Root URL configuration
│   │   ├── wsgi.py            # WSGI application entry point
│   │   └── asgi.py            # ASGI application entry point
│   ├── nfl/                   # Main Django app
│   │   ├── models.py          # Database models (Team, Game, Athlete, etc.)
│   │   ├── views.py           # API endpoints and business logic
│   │   ├── urls.py            # App-specific URL patterns
│   │   ├── admin.py           # Django admin configuration
│   │   ├── apps.py            # App configuration
│   │   ├── cron.py            # Scheduled tasks for data updates
│   │   ├── static_views.py    # Static content views
│   │   ├── migrations/        # Database migration files
│   │   └── management/        # Custom Django management commands
│   │       └── commands/      # Individual management commands
│   │           ├── initial.py              # Initial data setup
│   │           ├── update_calendar.py      # Calendar data updates
│   │           ├── update_game_info.py     # Game information updates
│   │           ├── update_player_stats.py  # Player statistics updates
│   │           ├── fetch_player_stats.py   # Fetch player data from API
│   │           ├── fix_player_names.py     # Data cleanup utilities
│   │           ├── create_tbd_team.py      # Create placeholder teams
│   │           └── current_week.py         # Current week determination
│   ├── utils/                 # Utility modules
│   │   ├── get_data.py        # ESPN API integration and data fetching
│   │   ├── helpers.py         # Helper functions and utilities
│   │   └── test.py            # Testing utilities
│   ├── db.sqlite3             # SQLite database file
│   └── manage.py              # Django management script
├── frontend/                  # React frontend application
│   ├── src/                   # Source code
│   │   ├── components/        # React components
│   │   │   ├── GameDisplay.jsx     # Main games listing component
│   │   │   ├── TeamSchedule.jsx    # Team schedule and roster view
│   │   │   └── PositionStats.jsx   # Player position statistics
│   │   ├── App.jsx            # Main application component with routing
│   │   ├── main.jsx           # React application entry point
│   │   ├── api.js             # API service layer for backend communication
│   │   └── index.css          # Global styles and component styling
│   ├── public/                # Static assets
│   │   └── logos/             # NFL team logos (32 team logo files)
│   ├── dist/                  # Built application (generated)
│   ├── node_modules/          # NPM dependencies (generated)
│   ├── package.json           # NPM configuration and dependencies
│   ├── package-lock.json      # NPM lock file
│   ├── vite.config.js         # Vite build configuration
│   └── index.html             # HTML template
├── venv/                      # Python virtual environment
├── requirements.txt           # Python dependencies
├── .gitignore                # Git ignore patterns
└── README.md                 # This documentation file
```

## Database Schema

### Core Models

**Team**
- `team_id` (Primary Key): ESPN team identifier
- `team_name`: Full team name (e.g., "New England Patriots")
- `short_name`: Team abbreviation (e.g., "NE")
- `record`: Current season record (e.g., "10-7")
- `last_updated`: Timestamp of last data update

**Game**
- `event_id` (Primary Key): ESPN event identifier
- `short_name`: Game description
- `game_datetime`: Scheduled game time
- `season`: Season year
- `week_num`: Week number (1-18 regular season)
- `home_team`: Foreign key to Team model
- `away_team`: Foreign key to Team model
- `week`: Foreign key to Calendar model

**Athlete**
- `athlete_id` (Primary Key): ESPN athlete identifier
- `first_name`, `last_name`, `display_name`: Player names
- `jersey`: Jersey number
- `team`: Foreign key to Team model
- `position`, `position_abbreviation`: Player position
- `age`, `weight`, `height`: Physical attributes
- `debut_year`: First NFL season
- `active`, `status`: Player status information

**Calendar**
- Manages NFL season structure and week definitions
- Links games to specific weeks and season types

**Outcome**
- Stores betting odds and win probabilities for games
- `spread_display`: Formatted betting spread
- `home_win_prob`, `away_win_prob`: Win probability percentages

**Statistics Models**
- `SeasonStatistic`: Player season-long statistics
- `GameStatistic`: Individual game performance data
- `StatTeam`: Team-level statistics and rankings

## API Endpoints

### Games and Schedules
- `GET /` - API root with documentation
- `GET /games/` - Current week games with odds and probabilities
- `GET /games/<week_num>/` - Games for specific week
- `GET /team-schedule/<team_id>/` - Complete team schedule

### Team Information
- `GET /teams/<team_id>/roster/` - Team roster with player details
- `GET /teams/<team_id>/stats/` - Team season statistics

### Player Data
- `GET /matchup/<event_id>/` - Detailed game matchup information
- `GET /position/<position>/stats/` - Position-specific player statistics

## Frontend Components

### GameDisplay.jsx
- **Purpose:** Main landing page displaying current week games
- **Features:**
  - Week selector dropdown
  - Game cards with team logos, records, and odds
  - Win probability display
  - Team navigation links
- **State Management:** Games data, loading states, week selection
- **API Integration:** Fetches games data via gameService

### TeamSchedule.jsx
- **Purpose:** Comprehensive team information view
- **Features:**
  - Three-tab interface: Schedule, Team Stats, Roster
  - Complete season schedule display
  - Roster organized by position groups (Offense/Defense/Special Teams)
  - Player links to position statistics
  - Season selector for historical data
- **Navigation:** React Router integration with URL parameters
- **Responsive Design:** Mobile-friendly layout with CSS-in-JS styling

### PositionStats.jsx
- **Purpose:** Player position statistics and comparisons
- **Features:** Individual player performance metrics
- **Integration:** Links from roster view for detailed player analysis

### API Service Layer (api.js)
- **Purpose:** Centralized API communication
- **Features:**
  - Base URL configuration
  - Error handling and response parsing
  - Parameterized request building
- **Services:** gameService for game-related API calls

## Data Management

### ESPN API Integration
- **Primary Source:** ESPN Sports Core API
- **Data Types:** Teams, games, schedules, player rosters, statistics
- **Update Frequency:** Configurable via Django cron jobs
- **Error Handling:** Robust error handling with logging

### Cron Jobs (nfl/cron.py)
- `RefreshDataCronJob`: Periodic data refresh from ESPN API
- `UpdatePlayerStatsEvery10Minutes`: Real-time statistics updates
- `UpdatePlayerStatsPostGame`: Post-game statistics processing

### Management Commands
- **Initial Setup:** `python manage.py initial` - Bootstrap database
- **Data Updates:** Various commands for specific data refresh operations
- **Maintenance:** Player name fixes, calendar updates, current week detection

## Development Setup

### Prerequisites
- Python 3.13+ with pip
- Node.js 16+ with npm
- Git for version control

### Backend Setup
```bash
# Navigate to project directory
cd nfl-2

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Run database migrations
cd backend
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install Node.js dependencies
npm install

# Start development server
npm run dev
```

### Access Points
- **Frontend:** http://localhost:5173 (Vite dev server)
- **Backend API:** http://localhost:8000 (Django dev server)
- **Admin Panel:** http://localhost:8000/admin (if superuser created)

## Production Deployment

### Option 1: Traditional Nginx + SSL Setup
Use `setup_raspberry_pi.sh` for traditional deployment with:
- **Database:** PostgreSQL
- **Web Server:** Nginx with Let's Encrypt SSL
- **Process Management:** Supervisor + Gunicorn
- **Security:** Firewall, SSL certificates, secure headers

### Option 2: Cloudflare Tunnel Setup (Recommended)
Use `setup_cloudflare_tunnel.sh` for modern deployment with:
- **Database:** PostgreSQL
- **Tunnel:** Cloudflare tunnel (no open ports, automatic SSL)
- **Process Management:** Supervisor + Gunicorn
- **Domain:** https://nfl.taylorswayze.com

#### Cloudflare Tunnel Benefits
- No open ports required (more secure)
- Automatic SSL/TLS termination
- DDoS protection and CDN
- Easy domain management
- No need for port forwarding or firewall rules

#### Cloudflare Setup Steps
```bash
# Run the setup script
./setup_cloudflare_tunnel.sh

# Complete manual Cloudflare steps:
# 1. Login: cloudflared tunnel login
# 2. Create tunnel: cloudflared tunnel create nfl-app
# 3. Update nfl-tunnel.yml with tunnel ID
# 4. Add CNAME DNS record in Cloudflare dashboard
# 5. Start tunnel service: sudo systemctl enable --now cloudflared-nfl
```

### Frontend Build
```bash
cd frontend
npm run build
```
- Generates optimized static files served by Django
- Single-page application with React Router support

## Key Features

### Real-time Data
- Live game odds and win probabilities
- Current week automatic detection
- Scheduled data updates via cron jobs

### User Experience
- Responsive design for mobile and desktop
- Fast navigation with React Router
- Intuitive team and player exploration
- Visual team logos and branding

### Data Integrity
- Comprehensive error handling
- Data validation and cleanup utilities
- Robust API integration with fallback handling

## Future Enhancements

### Planned Features
- Player comparison tools
- Historical statistics analysis
- Fantasy football integration
- Real-time game tracking
- Push notifications for game updates

### Technical Improvements
- Redis caching for improved performance
- WebSocket integration for real-time updates
- GraphQL API for more efficient data fetching
- Progressive Web App (PWA) capabilities
- Comprehensive test suite

## Troubleshooting

### Common Issues
1. **CORS Errors:** Ensure frontend URL is in CORS_ALLOWED_ORIGINS
2. **Database Errors:** Run migrations after model changes
3. **API Timeouts:** Check ESPN API availability and rate limits
4. **Missing Logos:** Verify team logo files in frontend/public/logos/

### Development Tips
- Use Django admin panel for data inspection
- Monitor Django logs for API integration issues
- Use browser developer tools for frontend debugging
- Test API endpoints directly before frontend integration

---

## AI Agent Research Methodology

**For Future AI Agents Updating This Documentation:**

### Research Process Used
1. **Recursive Directory Analysis:** Used `fs_read` with depth=3 to map complete project structure
2. **Key File Identification:** Prioritized Django core files (settings.py, models.py, views.py, urls.py) and React components
3. **Code Analysis:** Read and analyzed each critical file to understand functionality and relationships
4. **Architecture Mapping:** Traced data flow from API endpoints through models to frontend components
5. **Dependency Analysis:** Examined package.json and requirements.txt for technology stack
6. **Feature Documentation:** Identified user-facing features through component analysis

### Update Instructions for AI Agents
1. **File Analysis:** Always start with recursive directory scan using `fs_read` operations
2. **Core Files Priority:** Focus on Django settings, models, views, URLs, and main React components
3. **Change Detection:** Compare current file contents with existing documentation
4. **Timestamp Update:** Update the "Last Updated" timestamp at the top of this README
5. **Version Increment:** Update version number if significant changes are detected
6. **Structure Validation:** Verify project structure section matches actual directory layout
7. **Dependency Updates:** Check for new dependencies in package.json and requirements.txt
8. **Feature Updates:** Document any new API endpoints, components, or functionality discovered

### Timestamp Update Command
When updating this README, change the timestamp using this format:
```
**Last Updated:** [Month] [Day], [Year] at [Time] [Timezone]
```

### Research Tools Used
- `fs_read` for file and directory analysis
- `fs_write` for documentation creation
- Systematic code review of backend models, views, and frontend components
- API endpoint mapping through URL configuration analysis
- Database schema documentation through Django model analysis

This methodology ensures comprehensive project understanding and accurate documentation maintenance.
