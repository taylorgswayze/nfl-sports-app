from django.urls import path
from . import views
from . import live_views
from . import draft_proxy
from . import fantasy_views
from . import auth_views

urlpatterns = [
    path('', views.api_root, name='api_root'),  # Root API endpoint with enhanced documentation
    path('auth/login/', auth_views.login, name='auth_login'),  # Redirect to Google sign-in
    path('auth/callback/', auth_views.callback, name='auth_callback'),  # OAuth code exchange
    path('auth/logout/', auth_views.logout, name='auth_logout'),  # Clear session
    path('me/', auth_views.me, name='me'),  # Current user + saved settings (GET/PATCH)
    path('seasons/', views.seasons, name='seasons'),  # Seasons with available data
    path('games/', views.games, name='games'),  # All games for current week
    path('games/window/', views.games_window, name='games_window'),  # Rolling slate: last 24h + next 7 days
    path('games/<int:week_num>/', views.games, name='games_by_week'),  # Games for specific week
    path('team-schedule/<int:team_id>/', views.team_schedules, name='team_schedules'),  # Team schedule
    path('teams/', views.teams, name='teams'),  # All real teams, sorted by name
    path('matchup/<int:event_id>/', views.matchup, name='matchup'),  # Game matchup details
    path('live/', live_views.live_scoreboard, name='live_scoreboard'),  # Live scoreboard proxy (short cache)
    path('standings/', live_views.standings, name='standings'),  # NFL standings by conference/division (5 min cache)
    path('game/<int:event_id>/boxscore/', live_views.game_boxscore, name='game_boxscore'),  # Player boxscore, live or past
    path('draft/<str:endpoint>/', draft_proxy.proxy, name='draft_proxy'),  # Federated Draft Room API
    path('fantasy/overview/', fantasy_views.overview, name='fantasy_overview'),  # Multi-league Sleeper dashboard
    path('fantasy/insights/', fantasy_views.insights, name='fantasy_insights'),  # The Week Room: per-league roster advice

    path('teams/<int:team_id>/roster/', views.team_roster, name='team_roster'),  # Team roster
    path('teams/<int:team_id>/stats/', views.team_stats, name='team_stats'),  # Team statistics
    path('team-stat/<str:stat_name>/', views.team_stat_comparison, name='team_stat_comparison'),  # Team stat comparison
    path('position/<str:position>/stats/', views.position_stats, name='position_stats'),  # Position stats
]
