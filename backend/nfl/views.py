from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import models
from .models import Calendar, Team, Game, Athlete, Outcome, StatTeam, SeasonStatistic
import utils.get_data as get_data
import utils.helpers as h
from datetime import timedelta, datetime
from django.utils import timezone
import logging

# Set up logging
logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def api_root(request):
    """Enhanced root view that returns comprehensive API documentation"""
    endpoints = {
        'message': 'NFL Sports Info API',
        'version': '1.0.0',
        'description': 'RESTful API for NFL game data, team information, and statistics',
        'available_endpoints': {
            'seasons': {
                'url': '/seasons/',
                'method': 'GET',
                'description': 'Seasons with available game data',
                'response': 'List of seasons plus the current season'
            },
            'teams': {
                'url': '/teams/',
                'method': 'GET',
                'description': 'All 32 teams sorted by name (placeholder rows excluded)',
                'response': 'List of teams with team_id, name, abbr, and logo filename'
            },
            'games': {
                'url': '/games/',
                'method': 'GET',
                'description': 'Get all games for current week',
                'parameters': {'season': 'Optional season year', 'season_type': 'Optional: 2=regular (default), 3=postseason'},
                'response': 'Games list with scores, team info, odds, and win probabilities'
            },
            'games_by_week': {
                'url': '/games/<week_num>/',
                'method': 'GET',
                'description': 'Get games for specific week number',
                'parameters': {'week_num': 'Integer (1-18 regular season, 1-5 postseason)',
                               'season': 'Optional season year',
                               'season_type': 'Optional: 2=regular (default), 3=postseason'},
                'response': 'Games list filtered by week'
            },
            'team_schedule': {
                'url': '/team-schedule/<team_id>/',
                'method': 'GET',
                'description': 'Get complete season schedule for a team',
                'parameters': {'team_id': 'Integer (1-32)'},
                'response': 'Team schedule with game details'
            },
            'matchup': {
                'url': '/matchup/<event_id>/',
                'method': 'GET',
                'description': 'Get detailed matchup information for a specific game',
                'parameters': {'event_id': 'Integer (ESPN event ID)'},
                'response': 'Game details with team statistics'
            },
            'team_roster': {
                'url': '/teams/<team_id>/roster/',
                'method': 'GET',
                'description': 'Get team roster with player details',
                'parameters': {'team_id': 'Integer (1-32)'},
                'response': 'Player roster with positions, stats, and info'
            },
            'team_stats': {
                'url': '/teams/<team_id>/stats/',
                'method': 'GET',
                'description': 'Get team season statistics',
                'parameters': {'team_id': 'Integer (1-32)'},
                'response': 'Team performance statistics'
            }
        },
        'admin': '/admin/',
        'status': 'operational',
        'last_updated': get_data.format_datetime_to_est(datetime.now().strftime('%Y-%m-%d %H:%M:%S')) if hasattr(get_data, 'format_datetime_to_est') else 'N/A'
    }
    return JsonResponse(endpoints)


def format_game_time(datetime_obj):
    """Format game datetime for better readability"""
    if not datetime_obj:
        return 'TBD'
    
    try:
        formatted = get_data.format_datetime_to_est(datetime_obj)
        return formatted
    except Exception as e:
        logger.warning(f"Error formatting datetime {datetime_obj}: {e}")
        return str(datetime_obj)


def safe_get_outcome_data(game, field, default='N/A'):
    """Safely get outcome data with proper error handling"""
    try:
        outcome = getattr(game, 'outcome', None)
        if outcome and hasattr(outcome, field):
            value = getattr(outcome, field)
            if value is not None:
                if field in ['home_win_prob', 'away_win_prob'] and isinstance(value, (int, float)):
                    return int(value)
                return value
        return default
    except Exception as e:
        logger.warning(f"Error getting outcome field {field}: {e}")
        return default


@require_http_methods(["GET"])
def seasons(request):
    """List seasons that have game data, newest first."""
    try:
        available = sorted(set(Game.objects.values_list('season', flat=True)), reverse=True)
        return JsonResponse({
            'seasons': available,
            'current_season': h.current_season(),
        })
    except Exception as e:
        logger.error(f"Error in seasons view: {e}")
        return JsonResponse({'error': 'Internal server error while fetching seasons'}, status=500)


@require_http_methods(["GET"])
def teams(request):
    """All real teams sorted by name. Placeholder rows (TBD) are excluded.
    One query; logo filenames come from the local map, not the network."""
    try:
        rows = Team.objects.exclude(team_name='TBD').order_by('team_name')
        teams_list = [{
            'team_id': t.team_id,
            'name': t.team_name,
            'abbr': t.short_name,
            'logo': h.get_team_logo(t.team_id),
        } for t in rows]
        return JsonResponse({'teams': teams_list, 'count': len(teams_list)})
    except Exception as e:
        logger.error(f"Error in teams view: {e}")
        return JsonResponse({'error': 'Internal server error while fetching teams'}, status=500)


def serialize_game(game):
    """One game card dict, shared by the week view and the rolling slate."""
    return {
        'event_id': game.event_id,
        'short_name': game.short_name,
        'game_datetime': format_game_time(game.game_datetime),
        'game_datetime_utc': game.game_datetime.isoformat() if game.game_datetime else None,
        'season': game.season,
        'week_num': game.week_num,
        'season_type_id': game.season_type_id,
        'home_score': game.home_score,
        'away_score': game.away_score,
        'status': game.status,
        'home_team': game.home_team.team_name if game.home_team else 'TBD',
        'home_team_id': game.home_team.team_id if game.home_team else None,
        'home_team_abbr': game.home_team.short_name if game.home_team else None,
        'home_team_record': game.home_team.record if game.home_team else '0-0',
        'away_team': game.away_team.team_name if game.away_team else 'TBD',
        'away_team_id': game.away_team.team_id if game.away_team else None,
        'away_team_abbr': game.away_team.short_name if game.away_team else None,
        'away_team_record': game.away_team.record if game.away_team else '0-0',
        'home_team_logo': h.get_team_logo(game.home_team.team_id) if game.home_team else 'default-logo.png',
        'away_team_logo': h.get_team_logo(game.away_team.team_id) if game.away_team else 'default-logo.png',
        'odds': safe_get_outcome_data(game, 'spread_display'),
        'home_win_prob': safe_get_outcome_data(game, 'home_win_prob'),
        'away_win_prob': safe_get_outcome_data(game, 'away_win_prob'),
        'pred_diff': safe_get_outcome_data(game, 'pred_diff'),
        'odds_last_updated': format_game_time(safe_get_outcome_data(game, 'last_updated', None)) if safe_get_outcome_data(game, 'last_updated', None) else 'N/A',
    }


@require_http_methods(["GET"])
def games_window(request):
    """Rolling slate: every game from the last 24 hours through the next
    7 days, in chronological order, grouped into sections by calendar week
    so the frontend can render week dividers. Spans season-type and season
    boundaries (e.g. preseason into regular season) naturally."""
    try:
        now = timezone.now()
        start = now - timedelta(hours=24)
        end = now + timedelta(days=7)
        qs = (Game.objects
              .filter(game_datetime__gte=start, game_datetime__lte=end)
              .select_related('home_team', 'away_team', 'outcome', 'week')
              .order_by('game_datetime'))
        sections = []
        by_key = {}
        for game in qs:
            key = (game.season, game.season_type_id, game.week_num)
            section = by_key.get(key)
            if section is None:
                wk = game.week
                section = {
                    'season': game.season,
                    'season_type_id': game.season_type_id,
                    'season_type_name': wk.season_type_name if wk else None,
                    'week_num': game.week_num,
                    'week_name': wk.name if wk else f'Week {game.week_num}',
                    'week_details': wk.details if wk else None,
                    'games': [],
                }
                by_key[key] = section
                sections.append(section)
            try:
                section['games'].append(serialize_game(game))
            except Exception as e:
                logger.error(f"Error processing game {game.event_id}: {e}")
        return JsonResponse({
            'window_start': start.isoformat(),
            'window_end': end.isoformat(),
            'sections': sections,
            'total_games': sum(len(s['games']) for s in sections),
        })
    except Exception as e:
        logger.error(f"Error in games_window view: {e}")
        return JsonResponse({'error': 'Internal server error while fetching games'},
                            status=500)


@require_http_methods(["GET"])
def games(request, week_num=None):
    """Get games for a week.

    Query params: ?season= (default: current season), ?season_type=
    (2=regular season [default], 3=postseason) to disambiguate colliding
    week numbers between regular season and playoffs.
    """
    try:
        try:
            season = int(request.GET.get('season', h.current_season()))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid season parameter'}, status=400)
        try:
            season_type = int(request.GET.get('season_type', 2))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid season_type parameter'}, status=400)

        # All weeks for the season (both season types, postseason exposed too)
        unique_weeks = Calendar.objects.filter(season=season).order_by(
            'season_type_id', 'week_num')
        unique_weeks_data = [{
            'name': week.name,
            'details': week.details,
            'week_num': week.week_num,
            'season': week.season,
            'season_type_id': week.season_type_id,
            'season_type_name': week.season_type_name,
            'start_date': week.start_date,
            'end_date': week.end_date
        } for week in unique_weeks]

        # Determine which week to show
        if week_num:
            week = Calendar.objects.filter(
                season=season,
                season_type_id=season_type,
                week_num=week_num
            ).first()
            if not week:
                return JsonResponse({
                    'error': f'Week {week_num} (type {season_type}) not found for season {season}',
                    'available_weeks': [
                        {'week_num': w['week_num'], 'season_type_id': w['season_type_id']}
                        for w in unique_weeks_data]
                }, status=404)
        else:
            # Current week when browsing the current season; else week 1.
            week = None
            try:
                current = h.current_week()
                if current and current.season == season:
                    week = current
            except Exception as e:
                logger.warning(f"Error getting current week: {e}")
            if not week:
                week = unique_weeks.first() if unique_weeks else None
            if not week:
                return JsonResponse({'error': f'No calendar data available for season {season}'}, status=404)

        # Get games for the selected week
        games_queryset = Game.objects.filter(week=week).select_related('home_team', 'away_team', 'outcome').order_by('game_datetime')
        
        games_list = []
        for game in games_queryset:
            try:
                games_list.append(serialize_game(game))
            except Exception as e:
                logger.error(f"Error processing game {game.event_id}: {e}")
                continue

        current_week_data = {
            'name': week.name,
            'details': week.details,
            'week_num': week.week_num,
            'season': week.season,
            'season_type_id': week.season_type_id,
            'season_type_name': week.season_type_name,
            'start_date': week.start_date,
            'end_date': week.end_date
        }

        return JsonResponse({
            'games': games_list,
            'weeks': unique_weeks_data,
            'current_week': current_week_data,
            'season': season,
            'season_type': week.season_type_id,
            'total_games': len(games_list),
            'week_requested': week_num
        })

    except Exception as e:
        logger.error(f"Error in games view: {e}")
        return JsonResponse({
            'error': 'Internal server error while fetching games',
            'message': str(e) if hasattr(e, 'message') else str(e)
        }, status=500)


@require_http_methods(["GET"])
def team_schedules(request, team_id):
    """Get team schedule with enhanced error handling and data validation"""
    try:
        # Validate team exists
        try:
            team = Team.objects.get(pk=team_id)
        except Team.DoesNotExist:
            return JsonResponse({
                'error': f'Team with ID {team_id} not found',
                'message': 'Please provide a valid team ID (1-32)'
            }, status=404)
    
        try:
            season = int(request.GET.get('season', h.current_season()))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid season parameter'}, status=400)

        games = Game.objects.filter(
            models.Q(home_team_id=team_id) | models.Q(away_team_id=team_id)
        ).select_related('home_team', 'away_team', 'outcome').order_by('game_datetime')

        available_seasons = sorted(set(games.values_list('season', flat=True)), reverse=True)
        if season not in available_seasons and available_seasons:
            # Requested/current season has no games yet; fall back to the
            # latest season with data.
            season = available_seasons[0]
        games = games.filter(season=season)

        schedule = []
        for game in games:
            try:
                is_home = int(team_id) == int(game.home_team_id)
                opponent = game.away_team if is_home else game.home_team

                team_score = game.home_score if is_home else game.away_score
                opponent_score = game.away_score if is_home else game.home_score
                result = None
                if game.status == Game.STATUS_FINAL and team_score is not None and opponent_score is not None:
                    result = 'W' if team_score > opponent_score else ('L' if team_score < opponent_score else 'T')

                game_data = {
                    'event_id': game.event_id,
                    'game_datetime': format_game_time(game.game_datetime),
                    'week_num': game.week_num,
                    'season': game.season,
                    'season_type_id': game.season_type_id,
                    'is_home': is_home,
                    'home_score': game.home_score,
                    'away_score': game.away_score,
                    'team_score': team_score,
                    'opponent_score': opponent_score,
                    'status': game.status,
                    'result': result,
                    'opponent': opponent.team_name if opponent else 'TBD',
                    'opponent_id': opponent.team_id if opponent else None,
                    'opponent_abbr': opponent.short_name if opponent else None,
                    'opponent_logo': h.get_team_logo(opponent.team_id) if opponent else 'default-logo.png',
                    'opponent_record': opponent.record if opponent else '0-0',
                    'odds': safe_get_outcome_data(game, 'spread_display'),
                    'home_win_prob': safe_get_outcome_data(game, 'home_win_prob'),
                    'away_win_prob': safe_get_outcome_data(game, 'away_win_prob'),
                }
                schedule.append(game_data)

            except Exception as e:
                logger.error(f"Error processing game {game.event_id}: {e}")
                continue

        return JsonResponse({
            'schedule': schedule,
            'team': team.team_name,
            'team_abbr': team.short_name,
            'team_id': team_id,
            'season': season,
            'available_seasons': available_seasons,
            'total_games': len(schedule),
            'home_games': len([g for g in schedule if g['is_home']]),
            'away_games': len([g for g in schedule if not g['is_home']])
        })

    except Exception as e:
        logger.error(f"Error in team_schedules view for team_id {team_id}: {e}")
        return JsonResponse({
            'error': 'Internal server error while fetching team schedule',
            'message': str(e),
            'team_id': team_id
        }, status=500)


# ---------------------------------------------------------------------------
# Head-to-head matchup apparatus
#
# H2H_ROWS is the explicit mapping table for the matchup view: stat key ->
# data source, label, better-side direction and display format.
#
# Source kinds:
#   'scores'                          computed point-in-time from the Game
#                                     table (finals before the viewed game's
#                                     kickoff, in the stats season)
#   ('stat', (category, stat_name))   full-season StatTeam value (real ESPN
#                                     stat names, verified in the DB)
#   ('ratio', num_pair, den_pair)     ratio of two StatTeam values
#   ('per_game', (category, name))    StatTeam value / games played
#
# Rows from the owner's research list that are DROPPED because the data does
# not exist in StatTeam (never fabricated):
#   - Yards per play allowed          (defensive|yardsAllowed is zeroed in the
#                                      ESPN backfill; no opponent-plays stat)
#   - Net yards/pass attempt allowed  (no allowed/opponent passing stat)
#   - Third down conversion % allowed (no allowed variant)
# ---------------------------------------------------------------------------

H2H_GAMES_PLAYED_SOURCES = [('general', 'gamesPlayed'), ('passing', 'teamGamesPlayed')]

H2H_ROWS = [
    {'key': 'record',          'label': 'Record',                      'src': 'scores', 'dir': None,     'fmt': 'text'},
    {'key': 'ppg',             'label': 'Points per game',             'src': 'scores', 'dir': 'higher', 'fmt': 'num1'},
    {'key': 'papg',            'label': 'Points allowed per game',     'src': 'scores', 'dir': 'lower',  'fmt': 'num1'},
    {'key': 'point_diff',      'label': 'Point differential per game', 'src': 'scores', 'dir': 'higher', 'fmt': 'signed1'},
    {'key': 'yards_per_play',  'label': 'Yards per play',
     'src': ('ratio', ('passing', 'totalYards'), ('passing', 'totalOffensivePlays')), 'dir': 'higher', 'fmt': 'num2'},
    {'key': 'turnover_margin', 'label': 'Turnover margin',
     'src': ('stat', ('miscellaneous', 'turnOverDifferential')), 'dir': 'higher', 'fmt': 'signed0'},
    {'key': 'net_pass_ypa',    'label': 'Net yards per pass attempt',
     'src': ('stat', ('passing', 'netYardsPerPassAttempt')), 'dir': 'higher', 'fmt': 'num2'},
    {'key': 'rush_ypa',        'label': 'Rushing yards per attempt',
     'src': ('stat', ('rushing', 'yardsPerRushAttempt')), 'dir': 'higher', 'fmt': 'num2'},
    {'key': 'third_down_pct',  'label': 'Third down conversion',
     'src': ('stat', ('miscellaneous', 'thirdDownConvPct')), 'dir': 'higher', 'fmt': 'pct1'},
    {'key': 'red_zone_td_pct', 'label': 'Red zone touchdown rate',
     'src': ('stat', ('miscellaneous', 'redzoneTouchdownPct')), 'dir': 'higher', 'fmt': 'pct1'},
    {'key': 'passer_rating',   'label': 'Team passer rating',
     'src': ('stat', ('passing', 'QBRating')), 'dir': 'higher', 'fmt': 'num1'},
    {'key': 'sacks_def',       'label': 'Sacks, defense',
     'src': ('stat', ('defensive', 'sacks')), 'dir': 'higher', 'fmt': 'int'},
    {'key': 'sacks_allowed',   'label': 'Sacks allowed',
     'src': ('stat', ('passing', 'sacks')), 'dir': 'lower', 'fmt': 'int'},
    {'key': 'ints_thrown',     'label': 'Interceptions thrown',
     'src': ('stat', ('passing', 'interceptions')), 'dir': 'lower', 'fmt': 'int'},
    {'key': 'penalty_ypg',     'label': 'Penalty yards per game',
     'src': ('per_game', ('miscellaneous', 'totalPenaltyYards')), 'dir': 'lower', 'fmt': 'num1'},
    {'key': 'possession_time', 'label': 'Time of possession per game',
     'src': ('per_game', ('miscellaneous', 'possessionTimeSeconds')), 'dir': 'higher', 'fmt': 'clock'},
    {'key': 'total_ypg',       'label': 'Total yards per game',
     'src': ('stat', ('passing', 'yardsPerGame')), 'dir': 'higher', 'fmt': 'num1'},
]


def _h2h_format(value, fmt):
    """Render a raw stat value as a printed figure. Text rows pass through."""
    if value is None:
        return None
    if fmt == 'text':
        return str(value)
    value = float(value)
    if fmt == 'num1':
        return f'{value:.1f}'
    if fmt == 'num2':
        return f'{value:.2f}'
    if fmt == 'signed1':
        return f'{value:+.1f}'
    if fmt == 'signed0':
        return f'{value:+.0f}'
    if fmt == 'pct1':
        return f'{value:.1f}%'
    if fmt == 'int':
        return f'{value:.0f}'
    if fmt == 'clock':
        seconds = int(round(value))
        return f'{seconds // 60}:{seconds % 60:02d}'
    return str(value)


def _score_lines(team_ids, season, kickoff):
    """Point-in-time score-derived figures for the given teams: only games
    completed (status=final) BEFORE the viewed game's kickoff in `season`.
    One query for both teams."""
    finals = Game.objects.filter(
        season=season,
        status=Game.STATUS_FINAL,
        game_datetime__lt=kickoff,
        home_score__isnull=False,
        away_score__isnull=False,
    ).filter(
        models.Q(home_team_id__in=team_ids) | models.Q(away_team_id__in=team_ids)
    ).values('home_team_id', 'away_team_id', 'home_score', 'away_score')

    tally = {tid: {'w': 0, 'l': 0, 't': 0, 'pf': 0, 'pa': 0, 'n': 0} for tid in team_ids}
    for g in finals:
        for tid in team_ids:
            if g['home_team_id'] == tid:
                us, them = g['home_score'], g['away_score']
            elif g['away_team_id'] == tid:
                us, them = g['away_score'], g['home_score']
            else:
                continue
            t = tally[tid]
            t['n'] += 1
            t['pf'] += us
            t['pa'] += them
            if us > them:
                t['w'] += 1
            elif us < them:
                t['l'] += 1
            else:
                t['t'] += 1

    lines = {}
    for tid, t in tally.items():
        if t['n'] == 0:
            lines[tid] = {'record': None, 'ppg': None, 'papg': None, 'point_diff': None}
            continue
        record = f"{t['w']}-{t['l']}" + (f"-{t['t']}" if t['t'] else '')
        lines[tid] = {
            'record': record,
            'ppg': t['pf'] / t['n'],
            'papg': t['pa'] / t['n'],
            'point_diff': (t['pf'] - t['pa']) / t['n'],
        }
    return lines


def _build_h2h(game):
    """Build the head-to-head rows for a game.

    Season rule (owner's spec): for a game in season Y, if BOTH teams have at
    least one completed game in season Y before the viewed game's kickoff,
    use season Y; otherwise use season Y-1 (full season)."""
    away_id = game.away_team_id
    home_id = game.home_team_id
    team_ids = [away_id, home_id]

    current = _score_lines(team_ids, game.season, game.game_datetime)
    in_season = all(current[tid]['record'] is not None for tid in team_ids)
    if in_season:
        stats_season = game.season
        score_lines = current
        stats_note = f'{stats_season} season, through Week {game.week_num}'
        stats_scope = 'to_kickoff'
    else:
        stats_season = game.season - 1
        # A prior season's games all precede this kickoff, so the same
        # point-in-time computation yields true full-season figures.
        score_lines = _score_lines(team_ids, stats_season, game.game_datetime)
        stats_note = f'full {stats_season} season'
        stats_scope = 'full_season'

    # Every StatTeam figure for both team-seasons in one batched query.
    needed_names = {H2H_GAMES_PLAYED_SOURCES[0][1], H2H_GAMES_PLAYED_SOURCES[1][1]}
    for row in H2H_ROWS:
        src = row['src']
        if src == 'scores':
            continue
        if src[0] == 'ratio':
            needed_names.update([src[1][1], src[2][1]])
        else:
            needed_names.add(src[1][1])
    stat_rows = StatTeam.objects.filter(
        team_id__in=team_ids, season=stats_season, stat_name__in=needed_names,
    ).values('team_id', 'category', 'stat_name', 'value')
    values = {(r['team_id'], r['category'], r['stat_name']): r['value'] for r in stat_rows}

    def stat(tid, pair):
        return values.get((tid, pair[0], pair[1]))

    def games_played(tid):
        for pair in H2H_GAMES_PLAYED_SOURCES:
            v = stat(tid, pair)
            if v:
                return v
        return None

    def resolve(tid, row):
        src = row['src']
        if src == 'scores':
            return score_lines[tid][row['key']]
        kind = src[0]
        if kind == 'stat':
            return stat(tid, src[1])
        if kind == 'ratio':
            num, den = stat(tid, src[1]), stat(tid, src[2])
            if num is None or not den:
                return None
            return num / den
        if kind == 'per_game':
            total, n = stat(tid, src[1]), games_played(tid)
            if total is None or not n:
                return None
            return total / n
        return None

    h2h = []
    for row in H2H_ROWS:
        away_val = resolve(away_id, row)
        home_val = resolve(home_id, row)
        # No fabricated data: a row missing a real value on either side is
        # omitted entirely (a one-sided comparison is no comparison).
        if away_val is None or home_val is None:
            continue
        better = None
        if row['dir'] and away_val != home_val:
            away_leads = away_val > home_val
            if row['dir'] == 'lower':
                away_leads = not away_leads
            better = 'away' if away_leads else 'home'
        h2h.append({
            'key': row['key'],
            'label': row['label'],
            'away': _h2h_format(away_val, row['fmt']),
            'home': _h2h_format(home_val, row['fmt']),
            'better': better,
            'direction': row['dir'],
            'season_used': stats_season,
            'scope': 'to_kickoff' if (row['src'] == 'scores' and stats_scope == 'to_kickoff') else 'full_season',
            'format': row['fmt'],
        })

    return h2h, stats_season, stats_scope, stats_note, score_lines


@require_http_methods(["GET"])
def matchup(request, event_id):
    """Game header plus the head-to-head comparison table."""
    try:
        try:
            game = Game.objects.select_related('home_team', 'away_team', 'outcome').get(event_id=event_id)
        except Game.DoesNotExist:
            return JsonResponse({
                'error': f'Game with event_id {event_id} not found',
                'message': 'Please check the event_id and try again'
            }, status=404)

        if not game.home_team or not game.away_team:
            return JsonResponse({
                'error': f'Game {event_id} has incomplete team data'
            }, status=404)

        h2h, stats_season, stats_scope, stats_note, score_lines = _build_h2h(game)

        def team_block(team, line):
            return {
                'team_id': team.team_id,
                'name': team.team_name,
                'abbr': team.short_name,
                'record': line['record'],  # point-in-time; None when no games counted
                'logo': h.get_team_logo(team.team_id),
            }

        matchup_data = {
            'event_id': game.event_id,
            'short_name': game.short_name,
            'game_datetime': format_game_time(game.game_datetime),
            'season': game.season,
            'week_num': game.week_num,
            'season_type_id': game.season_type_id,
            'status': game.status,
            'home_score': game.home_score,
            'away_score': game.away_score,
            'away_team': team_block(game.away_team, score_lines[game.away_team_id]),
            'home_team': team_block(game.home_team, score_lines[game.home_team_id]),
            'odds': safe_get_outcome_data(game, 'spread_display'),
            'home_win_prob': safe_get_outcome_data(game, 'home_win_prob'),
            'away_win_prob': safe_get_outcome_data(game, 'away_win_prob'),
            'pred_diff': safe_get_outcome_data(game, 'pred_diff'),
            'odds_last_updated': format_game_time(safe_get_outcome_data(game, 'last_updated', None)) if safe_get_outcome_data(game, 'last_updated', None) else 'N/A',
            'stats_season': stats_season,
            'stats_scope': stats_scope,
            'stats_note': stats_note,
            'h2h': h2h,
        }

        return JsonResponse(matchup_data)

    except Exception as e:
        logger.error(f"Error in matchup view for event_id {event_id}: {e}")
        return JsonResponse({
            'error': 'Internal server error while fetching matchup data',
            'message': str(e),
            'event_id': event_id
        }, status=500)


def _roster_stat_totals(athlete_ids, season):
    """Season-to-date regular season totals per athlete from GameStatistic
    (fresh, boxscore-fed) joined to Game. GameStatistic.event_id is a
    CharField, so CAST bridges to Game's integer primary key. Returns
    ({athlete_id: {(category, stat): (sum, max)}}, {athlete_id: games})."""
    if not athlete_ids:
        return {}, {}
    ids = list(athlete_ids)
    placeholders = ','.join(['%s'] * len(ids))
    totals_sql = f'''
        SELECT gs.athlete_id, gs.category_name, gs.stat_name,
               SUM(CAST(gs.stat_value AS REAL)), MAX(CAST(gs.stat_value AS REAL))
        FROM nfl_gamestatistic gs
        JOIN nfl_game g ON CAST(gs.event_id AS INTEGER) = g.event_id
        WHERE g.season = %s AND g.season_type_id = 2
          AND gs.athlete_id IN ({placeholders})
        GROUP BY gs.athlete_id, gs.category_name, gs.stat_name
    '''
    games_sql = f'''
        SELECT gs.athlete_id, COUNT(DISTINCT gs.event_id)
        FROM nfl_gamestatistic gs
        JOIN nfl_game g ON CAST(gs.event_id AS INTEGER) = g.event_id
        WHERE g.season = %s AND g.season_type_id = 2
          AND gs.athlete_id IN ({placeholders})
        GROUP BY gs.athlete_id
    '''
    from django.db import connection
    totals, games = {}, {}
    with connection.cursor() as cursor:
        cursor.execute(totals_sql, [season, *ids])
        for aid, cat, name, total, peak in cursor.fetchall():
            totals.setdefault(aid, {})[(cat, name)] = (total or 0.0, peak or 0.0)
        cursor.execute(games_sql, [season, *ids])
        games = dict(cursor.fetchall())
    return totals, games


def _fmt_count(v):
    return format(int(round(v)), ',')


def _sum(t, cat, name):
    return (t.get((cat, name)) or (0.0, 0.0))[0]


def _max(t, cat, name):
    return (t.get((cat, name)) or (0.0, 0.0))[1]


# Key season-to-date metrics per position abbreviation. Each entry maps a
# column label to a formatter over that athlete's stat totals. Rate stats
# are recomputed from components (summed per-game rates are meaningless).
_QB_METRICS = [
    ('CMP/ATT', lambda t: f"{_fmt_count(_sum(t, 'passing', 'completions'))}/{_fmt_count(_sum(t, 'passing', 'passingAttempts'))}"),
    ('YDS', lambda t: _fmt_count(_sum(t, 'passing', 'passingYards'))),
    ('TD', lambda t: _fmt_count(_sum(t, 'passing', 'passingTouchdowns'))),
    ('INT', lambda t: _fmt_count(_sum(t, 'passing', 'interceptions'))),
]
_RB_METRICS = [
    ('CAR', lambda t: _fmt_count(_sum(t, 'rushing', 'rushingAttempts'))),
    ('YDS', lambda t: _fmt_count(_sum(t, 'rushing', 'rushingYards'))),
    ('TD', lambda t: _fmt_count(_sum(t, 'rushing', 'rushingTouchdowns'))),
    ('REC', lambda t: _fmt_count(_sum(t, 'receiving', 'receptions'))),
]
_REC_METRICS = [
    ('REC', lambda t: _fmt_count(_sum(t, 'receiving', 'receptions'))),
    ('TGTS', lambda t: _fmt_count(_sum(t, 'receiving', 'receivingTargets'))),
    ('YDS', lambda t: _fmt_count(_sum(t, 'receiving', 'receivingYards'))),
    ('TD', lambda t: _fmt_count(_sum(t, 'receiving', 'receivingTouchdowns'))),
]
_FRONT7_METRICS = [
    ('TKL', lambda t: _fmt_count(_sum(t, 'defensive', 'totalTackles'))),
    ('SACKS', lambda t: f"{_sum(t, 'defensive', 'sacks'):.1f}"),
    ('TFL', lambda t: _fmt_count(_sum(t, 'defensive', 'tacklesForLoss'))),
    ('QB HITS', lambda t: _fmt_count(_sum(t, 'defensive', 'QBHits'))),
]
_DB_METRICS = [
    ('TKL', lambda t: _fmt_count(_sum(t, 'defensive', 'totalTackles'))),
    ('INT', lambda t: _fmt_count(_sum(t, 'interceptions', 'interceptions'))),
    ('PD', lambda t: _fmt_count(_sum(t, 'defensive', 'passesDefended'))),
]
_K_METRICS = [
    ('FG', lambda t: f"{_fmt_count(_sum(t, 'kicking', 'fieldGoalsMade'))}/{_fmt_count(_sum(t, 'kicking', 'fieldGoalAttempts'))}"),
    ('LONG', lambda t: _fmt_count(_max(t, 'kicking', 'longFieldGoalMade'))),
    ('XP', lambda t: f"{_fmt_count(_sum(t, 'kicking', 'extraPointsMade'))}/{_fmt_count(_sum(t, 'kicking', 'extraPointAttempts'))}"),
    ('PTS', lambda t: _fmt_count(_sum(t, 'kicking', 'totalKickingPoints'))),
]
_P_METRICS = [
    ('PUNTS', lambda t: _fmt_count(_sum(t, 'punting', 'punts'))),
    ('AVG', lambda t: f"{(_sum(t, 'punting', 'puntYards') / _sum(t, 'punting', 'punts')):.1f}" if _sum(t, 'punting', 'punts') else '0.0'),
    ('IN 20', lambda t: _fmt_count(_sum(t, 'punting', 'puntsInside20'))),
    ('LONG', lambda t: _fmt_count(_max(t, 'punting', 'longPunt'))),
]
ROSTER_METRICS = {
    'QB': _QB_METRICS,
    'RB': _RB_METRICS, 'FB': _RB_METRICS,
    'WR': _REC_METRICS, 'TE': _REC_METRICS,
    'DE': _FRONT7_METRICS, 'DT': _FRONT7_METRICS, 'NT': _FRONT7_METRICS,
    'LB': _FRONT7_METRICS, 'OLB': _FRONT7_METRICS, 'MLB': _FRONT7_METRICS,
    'ILB': _FRONT7_METRICS, 'EDGE': _FRONT7_METRICS,
    'CB': _DB_METRICS, 'S': _DB_METRICS, 'FS': _DB_METRICS,
    'SS': _DB_METRICS, 'DB': _DB_METRICS,
    'PK': _K_METRICS, 'K': _K_METRICS,
    'P': _P_METRICS,
    # OL and long snappers have no boxscore stats; bio columns carry them.
}


@require_http_methods(["GET"])
def team_roster(request, team_id):
    """Get roster data for a specific team with enhanced error handling"""
    try:
        # Validate team exists
        try:
            team = Team.objects.get(pk=team_id)
        except Team.DoesNotExist:
            return JsonResponse({
                'error': f'Team with ID {team_id} not found',
                'message': 'Please provide a valid team ID (1-32)'
            }, status=404)

        # Current roster only: rows created by boxscore ingestion for
        # historical players carry no status and are excluded. Depth-chart
        # rank orders each position (starters first, NULL depth last).
        players = (Athlete.objects
                   .filter(team_id=team_id, status__isnull=False)
                   .order_by('position',
                             models.F('depth_rank').asc(nulls_last=True),
                             'jersey'))

        # Season-to-date key stats: the current season once regular-season
        # games exist, else last season (clearly labeled in the response).
        stats_season = h.current_season()
        athlete_ids = [p.athlete_id for p in players]
        totals, games_played = _roster_stat_totals(athlete_ids, stats_season)
        if not totals and stats_season:
            stats_season -= 1
            totals, games_played = _roster_stat_totals(athlete_ids, stats_season)
        
        roster_list = []
        for player in players:
            try:
                # Handle name display - use display_name if available, otherwise combine first/last
                if player.display_name:
                    name = player.display_name
                elif player.first_name and player.last_name:
                    name = f"{player.first_name} {player.last_name}".strip()
                elif player.first_name:
                    name = player.first_name
                elif player.last_name:
                    name = player.last_name
                else:
                    name = f"Player #{player.jersey}" if player.jersey else "Unknown Player"
                
                metrics = ROSTER_METRICS.get(player.position_abbreviation)
                stat_totals = totals.get(player.athlete_id, {})
                player_data = {
                    'athlete_id': player.athlete_id,
                    'jersey': player.jersey,
                    'first_name': player.first_name,
                    'last_name': player.last_name,
                    'display_name': name,
                    'position': player.position or 'Unknown',
                    'position_abbreviation': player.position_abbreviation,
                    'height': player.height,
                    'weight': player.weight,
                    'age': player.age,
                    'debut_year': player.debut_year,
                    'status': player.status,
                    'depth_rank': player.depth_rank,
                    'depth_slot': player.depth_slot,
                    'starter': player.depth_rank == 1,
                    'games_played': games_played.get(player.athlete_id, 0),
                    'key_stats': [
                        {'label': label, 'value': fmt(stat_totals)}
                        for label, fmt in metrics
                    ] if metrics else [],
                }
                roster_list.append(player_data)
            except Exception as e:
                logger.warning(f"Error processing player {player.athlete_id}: {e}")
                continue
        
        # Group players by position for better organization
        positions = {}
        for player in roster_list:
            pos = player['position']
            if pos not in positions:
                positions[pos] = []
            positions[pos].append(player)
        
        return JsonResponse({
            'team': team.team_name,
            'team_id': team_id,
            'roster': roster_list,
            'roster_by_position': positions,
            'total_players': len(roster_list),
            'positions_count': len(positions),
            'stats_season': stats_season,
        })
        
    except Exception as e:
        logger.error(f"Error in team_roster view for team_id {team_id}: {e}")
        return JsonResponse({
            'error': 'Internal server error while fetching team roster',
            'message': str(e),
            'team_id': team_id
        }, status=500)


def get_stat_priority_order():
    """Define stat priority tiers based on NFL analytics importance"""
    return {
        # Tier 1: Critical Performance Indicators
        1: ['totalPointsPerGame', 'totalPoints', 'turnOverDifferential', 'thirdDownConvPct', 
            'redzoneScoringPct', 'yardsPerCompletion', 'yardsPerPassAttempt', 'totalYards'],
        
        # Tier 2: Offensive Efficiency  
        2: ['netYardsPerPassAttempt', 'yardsPerRushAttempt', 'yardsPerGame', 'passingYardsPerGame',
            'rushingYardsPerGame', 'netYardsPerGame', 'avgGain'],
            
        # Tier 3: Scoring & Red Zone
        3: ['redzoneEfficiencyPct', 'redzoneTouchdownPct', 'totalTouchdowns', 'fieldGoalPct',
            'fieldGoalsMade', 'passingTouchdowns', 'rushingTouchdowns'],
            
        # Tier 4: Turnovers & Ball Security
        4: ['interceptions', 'fumblesLost', 'fumblesRecovered', 'totalTakeaways', 'totalGiveaways',
            'fumbles', 'interceptionPct'],
            
        # Tier 5: Third Down & Situational
        5: ['thirdDownAttempts', 'thirdDownConvs', 'fourthDownConvPct', 'firstDowns',
            'firstDownsPerGame', 'possessionTimeSeconds'],
            
        # Tier 6: Defensive Efficiency
        6: ['pointsAllowed', 'yardsAllowed', 'sacks', 'totalTackles', 'soloTackles',
            'tacklesForLoss', 'passesDefended'],
            
        # Tier 7: Special Teams
        7: ['kickReturnYards', 'puntReturnYards', 'netAvgPuntYards', 'yardsPerKickReturn',
            'yardsPerPuntReturn', 'kickoffReturnYards'],
            
        # Tier 8: Discipline & Penalties
        8: ['totalPenalties', 'totalPenaltyYards'],
        
        # Tier 9: Volume Stats
        9: ['totalOffensivePlays', 'passingAttempts', 'rushingAttempts', 'completions',
            'receptions', 'receivingTargets', 'gamesPlayed']
    }


def order_stats_by_priority(stats_queryset):
    """Order stats by priority tiers, then alphabetically within tiers"""
    priority_tiers = get_stat_priority_order()
    
    # Create a mapping of stat names to priority
    stat_priorities = {}
    for tier, stat_names in priority_tiers.items():
        for stat_name in stat_names:
            stat_priorities[stat_name] = tier
    
    # Convert queryset to list and sort
    stats_list = list(stats_queryset)
    
    def get_sort_key(stat_obj):
        priority = stat_priorities.get(stat_obj.stat_name, 10)  # Default to tier 10 for unknown stats
        return (priority, stat_obj.stat_name)  # Sort by priority, then alphabetically
    
    return sorted(stats_list, key=get_sort_key)


@require_http_methods(["GET"])
def team_stats(request, team_id):
    """Get season stats for a specific team with prioritized ordering"""
    try:
        # Validate team exists
        try:
            team = Team.objects.get(pk=team_id)
        except Team.DoesNotExist:
            return JsonResponse({
                'error': f'Team with ID {team_id} not found',
                'message': 'Please provide a valid team ID (1-32)'
            }, status=404)
        
        try:
            season = int(request.GET.get('season', h.current_season()))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid season parameter'}, status=400)

        available_seasons = sorted(set(
            StatTeam.objects.filter(team_id=team_id).values_list('season', flat=True)
        ), reverse=True)

        # No fabricated fallback: return honest empty data with a flag.
        all_team_stats = StatTeam.objects.filter(team_id=team_id, season=season)
        stats_data = []
        for stat_obj in order_stats_by_priority(all_team_stats):
            stats_data.append({
                'name': stat_obj.stat_name,
                'value': stat_obj.value,
                'rank': stat_obj.rank,
                'display_rank': stat_obj.display_rank,
                'description': stat_obj.description,
                'category': stat_obj.category
            })

        response_data = {
            'team': team.team_name,
            'team_id': team_id,
            'stats': stats_data,
            'season': season,
            'available_seasons': available_seasons,
            'has_stats': bool(stats_data),
            'data_source': 'database' if stats_data else 'none'
        }

        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error in team_stats view for team_id {team_id}: {e}")
        return JsonResponse({
            'error': 'Internal server error while fetching team stats',
            'message': str(e),
            'team_id': team_id
        }, status=500)


@require_http_methods(["GET"])
def team_stat_comparison(request, stat_name):
    """Rank teams by a specific stat. Only real database rows are returned;
    teams without the stat are listed separately, never fabricated."""
    try:
        try:
            season = int(request.GET.get('season', h.current_season()))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid season parameter'}, status=400)

        available_seasons = sorted(set(
            StatTeam.objects.filter(stat_name=stat_name).values_list('season', flat=True)
        ), reverse=True)
        if season not in available_seasons and available_seasons:
            season = available_seasons[0]

        # Single batched query instead of one per team
        stat_rows = StatTeam.objects.filter(
            stat_name=stat_name, season=season
        ).select_related('team_id')

        team_stats = []
        teams_with_stat = set()
        for stat_obj in stat_rows:
            team = stat_obj.team_id
            teams_with_stat.add(team.team_id)
            team_stats.append({
                'team_id': team.team_id,
                'team_name': team.team_name,
                'short_name': team.short_name,
                'logo': h.get_team_logo(team.team_id),
                'value': stat_obj.value,
                'rank': stat_obj.rank,
                'display_rank': stat_obj.display_rank,
                'description': stat_obj.description,
                'category': stat_obj.category
            })

        missing_teams = [
            {'team_id': t.team_id, 'team_name': t.team_name, 'short_name': t.short_name}
            for t in Team.objects.exclude(team_id__in=teams_with_stat).exclude(team_name='TBD')
        ]

        # Sort by rank ascending (lower is better); unranked rows last
        team_stats.sort(key=lambda x: (x['rank'] is None, x['rank']))

        if not team_stats:
            return JsonResponse({
                'stat_name': stat_name,
                'season': season,
                'available_seasons': available_seasons,
                'teams': [],
                'has_stats': False,
                'error': f'No data for stat {stat_name} in season {season}'
            }, status=404)

        response_data = {
            'stat_name': stat_name,
            'teams': team_stats,
            'teams_missing_stat': missing_teams,
            'total_teams': len(team_stats),
            'season': season,
            'available_seasons': available_seasons,
            'has_stats': True
        }

        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error in team_stat_comparison view for stat {stat_name}: {e}")
        return JsonResponse({
            'error': 'Internal server error while fetching team stat comparison',
            'message': str(e),
            'stat_name': stat_name
        }, status=500)


@require_http_methods(["GET"])
def position_stats(request, position):
    """Get stats for all players of a specific position with ranking"""
    try:
        try:
            season = int(request.GET.get('season', h.current_season()))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid season parameter'}, status=400)
        
        # Position mapping and key stats (based on ESPN API order and NFL standards)
        position_mappings = {
            'quarterback': {
                'key_stats': ['yards', 'touchdowns', 'completion_pct', 'rating', 'interceptions'],
                'stat_aliases': {
                    'stat_2': 'yards', 'stat_5': 'touchdowns', 'stat_3': 'completion_pct', 
                    'stat_9': 'rating', 'stat_6': 'interceptions'
                },
                'ranking_formula': lambda stats: (
                    float(stats.get('yards', 0)) * 0.3 +
                    float(stats.get('touchdowns', 0)) * 100 +
                    float(stats.get('completion_pct', 0)) * 10 -
                    float(stats.get('interceptions', 0)) * 50 +
                    float(stats.get('rating', 0)) * 2
                )
            },
            'running back': {
                'key_stats': ['rush_attempts', 'rush_yards', 'rush_avg', 'rush_tds', 'receptions'],
                'stat_aliases': {
                    'stat_0': 'rush_attempts', 'stat_1': 'rush_yards', 'stat_2': 'rush_avg', 
                    'stat_3': 'rush_tds', 'stat_5': 'receptions'
                },
                'ranking_formula': lambda stats: (
                    float(stats.get('rush_yards', 0)) * 0.4 +
                    float(stats.get('rush_tds', 0)) * 60 +
                    float(stats.get('rush_avg', 0)) * 50 +
                    float(stats.get('receptions', 0)) * 8
                )
            },
            'wide receiver': {
                'key_stats': ['receptions', 'targets', 'rec_yards', 'rec_avg', 'rec_tds'],
                'stat_aliases': {
                    'stat_0': 'receptions', 'stat_1': 'targets', 'stat_2': 'rec_yards', 
                    'stat_4': 'rec_avg', 'stat_5': 'rec_tds'
                },
                'ranking_formula': lambda stats: (
                    float(stats.get('receptions', 0)) * 4 +
                    float(stats.get('rec_yards', 0)) * 0.5 +
                    float(stats.get('rec_tds', 0)) * 60 +
                    float(stats.get('rec_avg', 0)) * 8
                )
            },
            'tight end': {
                'key_stats': ['receptions', 'targets', 'rec_yards', 'rec_avg', 'rec_tds'],
                'stat_aliases': {
                    'stat_0': 'receptions', 'stat_1': 'targets', 'stat_2': 'rec_yards', 
                    'stat_3': 'rec_avg', 'stat_4': 'rec_tds'
                },
                'ranking_formula': lambda stats: (
                    float(stats.get('receptions', 0)) * 4 +
                    float(stats.get('rec_yards', 0)) * 0.5 +
                    float(stats.get('rec_tds', 0)) * 60
                )
            },
            'defensive line': {
                'key_stats': ['tackles', 'solo_tackles', 'assists', 'sacks', 'tfl'],
                'stat_aliases': {
                    'stat_2': 'tackles', 'stat_1': 'solo_tackles', 'stat_0': 'assists', 
                    'stat_3': 'sacks', 'stat_4': 'tfl'
                },
                'ranking_formula': lambda stats: (
                    float(stats.get('tackles', 0)) * 2 +
                    float(stats.get('sacks', 0)) * 20 +
                    float(stats.get('tfl', 0)) * 10
                )
            },
            'linebacker': {
                'key_stats': ['tackles', 'solo_tackles', 'assists', 'sacks', 'tfl'],
                'stat_aliases': {
                    'stat_2': 'tackles', 'stat_1': 'solo_tackles', 'stat_0': 'assists', 
                    'stat_4': 'sacks', 'stat_5': 'tfl'
                },
                'ranking_formula': lambda stats: (
                    float(stats.get('tackles', 0)) * 2 +
                    float(stats.get('sacks', 0)) * 15 +
                    float(stats.get('solo_tackles', 0)) * 1.5
                )
            },
            'defensive back': {
                'key_stats': ['tackles', 'solo_tackles', 'assists', 'interceptions', 'pass_def'],
                'stat_aliases': {
                    'stat_2': 'tackles', 'stat_1': 'solo_tackles', 'stat_0': 'assists', 
                    'stat_6': 'interceptions', 'stat_7': 'pass_def'
                },
                'ranking_formula': lambda stats: (
                    float(stats.get('tackles', 0)) * 1.5 +
                    float(stats.get('interceptions', 0)) * 40 +
                    float(stats.get('pass_def', 0)) * 5
                )
            },
            'kicker': {
                'key_stats': ['fg_made', 'fg_att', 'fg_pct', 'xp_made', 'points'],
                'stat_aliases': {
                    'stat_0': 'fg_made', 'stat_1': 'fg_att', 
                    'stat_2': 'fg_pct', 'stat_3': 'xp_made', 'stat_6': 'points'
                },
                'ranking_formula': lambda stats: (
                    float(stats.get('fg_made', 0)) * 3 +
                    float(stats.get('fg_pct', 0)) * 2 +
                    float(stats.get('points', 0)) * 1
                )
            }
        }
        
        # Aliases from REAL ESPN stat names (used for all rows written going
        # forward) to the semantic keys above. The stat_N aliases remain only
        # for legacy rows written before real names were stored.
        real_name_aliases = {
            'quarterback': {'passingYards': 'yards', 'passingTouchdowns': 'touchdowns',
                            'completionPct': 'completion_pct', 'QBRating': 'rating',
                            'interceptions': 'interceptions'},
            'running back': {'rushingAttempts': 'rush_attempts', 'rushingYards': 'rush_yards',
                             'yardsPerRushAttempt': 'rush_avg', 'rushingTouchdowns': 'rush_tds',
                             'receptions': 'receptions'},
            'wide receiver': {'receptions': 'receptions', 'receivingTargets': 'targets',
                              'receivingYards': 'rec_yards', 'yardsPerReception': 'rec_avg',
                              'receivingTouchdowns': 'rec_tds'},
            'tight end': {'receptions': 'receptions', 'receivingTargets': 'targets',
                          'receivingYards': 'rec_yards', 'yardsPerReception': 'rec_avg',
                          'receivingTouchdowns': 'rec_tds'},
            'defensive line': {'totalTackles': 'tackles', 'soloTackles': 'solo_tackles',
                               'assistTackles': 'assists', 'sacks': 'sacks',
                               'tacklesForLoss': 'tfl'},
            'linebacker': {'totalTackles': 'tackles', 'soloTackles': 'solo_tackles',
                           'assistTackles': 'assists', 'sacks': 'sacks',
                           'tacklesForLoss': 'tfl'},
            'defensive back': {'totalTackles': 'tackles', 'soloTackles': 'solo_tackles',
                               'assistTackles': 'assists', 'interceptions': 'interceptions',
                               'passesDefended': 'pass_def'},
            'kicker': {'fieldGoalsMade': 'fg_made', 'fieldGoalAttempts': 'fg_att',
                       'fieldGoalPct': 'fg_pct', 'extraPointsMade': 'xp_made',
                       'kickingPoints': 'points', 'totalPoints': 'points'},
        }

        position_lower = position.lower().replace('_', ' ')
        position_config = position_mappings.get(position_lower)

        if not position_config:
            return JsonResponse({'error': f'Position {position} not supported'}, status=400)

        stat_aliases = dict(position_config.get('stat_aliases', {}))
        stat_aliases.update(real_name_aliases.get(position_lower, {}))

        # Get all athletes for this position
        athletes = Athlete.objects.filter(
            position__icontains=position_lower.split()[0]
        ).select_related('team')

        # Single batched query for all athletes (was one query per athlete)
        stats_by_athlete = {}
        season_stats = SeasonStatistic.objects.filter(
            athlete__in=athletes,
            season_year=season,
            season_type='Regular Season'
        )
        for stat in season_stats:
            stats_by_athlete.setdefault(stat.athlete_id, {})[stat.stat_name] = stat.stat_value or 0

        players_data = []

        for athlete in athletes:
            player_stats = stats_by_athlete.get(athlete.athlete_id, {})

            # Map stored stat names (real ESPN names, or legacy stat_N) to
            # the semantic names used by the formulas
            mapped_stats = {}
            for generic_name, value in player_stats.items():
                meaningful_name = stat_aliases.get(generic_name, generic_name)
                mapped_stats[meaningful_name] = value

            # Only include players with some stats
            if player_stats:
                # Calculate ranking score using mapped stats
                ranking_score = position_config['ranking_formula'](mapped_stats)
                
                player_data = {
                    'athlete_id': athlete.athlete_id,
                    'name': athlete.display_name or f"{athlete.first_name} {athlete.last_name}",
                    'team': athlete.team.short_name if athlete.team else 'FA',
                    'team_id': athlete.team.team_id if athlete.team else None,
                    'jersey': athlete.jersey,
                    'position': athlete.position,
                    'stats': {stat: mapped_stats.get(stat, 0) for stat in position_config['key_stats']},
                    'ranking_score': ranking_score
                }
                players_data.append(player_data)
        
        # Sort by ranking score (highest first)
        players_data.sort(key=lambda x: x['ranking_score'], reverse=True)
        
        # Add rank numbers
        for i, player in enumerate(players_data):
            player['rank'] = i + 1
        
        return JsonResponse({
            'position': position,
            'season': season,
            'players': players_data,
            'key_stats': position_config['key_stats'],
            'total_players': len(players_data)
        })
        
    except Exception as e:
        logger.error(f"Error in position_stats view for position {position}: {e}")
        return JsonResponse({
            'error': 'Internal server error while fetching position stats',
            'message': str(e),
            'position': position
        }, status=500)
