from django.urls import path
from . import views

urlpatterns = [
    path('', views.api_root, name='api_root'),  # Root API endpoint with enhanced documentation
    path('games/', views.games, name='games'),  # All games for current week
    path('games/<int:week_num>/', views.games, name='games_by_week'),  # Games for specific week
    path('team-schedule/<int:team_id>/', views.team_schedules, name='team_schedules'),  # Team schedule
    path('matchup/<int:event_id>/', views.matchup, name='matchup'),  # Game matchup details
    path('teams/<int:team_id>/roster/', views.team_roster, name='team_roster'),  # Team roster
    path('teams/<int:team_id>/stats/', views.team_stats, name='team_stats'),  # Team statistics
    path('position/<str:position>/stats/', views.position_stats, name='position_stats'),  # Position stats
]
