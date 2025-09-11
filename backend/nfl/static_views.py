from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Team, Game, Calendar
import json

@require_http_methods(["GET"])
def static_routes(request):
    """Generate all static routes for prerendering"""
    routes = ['/']
    
    # Add team routes
    teams = Team.objects.all()
    for team in teams:
        routes.append(f'/team/{team.team_id}')
    
    # Add week routes
    weeks = Calendar.objects.filter(season=2024).values_list('week_num', flat=True).distinct()
    for week in weeks:
        routes.append(f'/games/{week}')
    
    return JsonResponse({'routes': routes})

@require_http_methods(["GET"])
def prerender_data(request):
    """Get all data needed for static generation"""
    teams = list(Team.objects.values())
    games = list(Game.objects.select_related('home_team', 'away_team').values(
        'event_id', 'week_num', 'game_datetime',
        'home_team__team_id', 'home_team__short_name', 'home_team__logo',
        'away_team__team_id', 'away_team__short_name', 'away_team__logo'
    ))
    weeks = list(Calendar.objects.filter(season=2024).values())
    
    return JsonResponse({
        'teams': teams,
        'games': games,
        'weeks': weeks
    })
