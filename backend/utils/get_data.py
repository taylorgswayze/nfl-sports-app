from django.db.models import Q
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pytz
from django.utils import timezone
from datetime import timedelta, datetime
from nfl import models
import utils.helpers as h
import logging

logger = logging.getLogger(__name__)

# Define a retry strategy
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
    backoff_factor=1
)

# Create an adapter with the retry strategy
adapter = HTTPAdapter(max_retries=retry_strategy)

# Create a session and mount the adapter
session = requests.Session()
session.mount("https://", adapter)
session.mount("http://", adapter)

BASE_URL = 'https://sports.core.api.espn.com/v2/sports/football/leagues'

# ESPN uses these team ids as placeholders for undetermined (e.g. playoff)
# matchups.
TBD_TEAM_IDS = {31, 32}


def map_game_status(state, completed=False):
    """Map an ESPN status state ('pre'/'in'/'post') to Game.status."""
    if state == 'post' or completed:
        return models.Game.STATUS_FINAL
    if state == 'in':
        return models.Game.STATUS_IN
    return models.Game.STATUS_SCHEDULED


def get_team_for_game(team_id):
    """Resolve a team id from an ESPN payload, creating a TBD placeholder row
    for ESPN's placeholder ids if it does not exist yet."""
    team_id = int(team_id)
    try:
        return models.Team.objects.get(pk=team_id)
    except models.Team.DoesNotExist:
        if team_id in TBD_TEAM_IDS:
            team, _ = models.Team.objects.update_or_create(
                team_id=team_id, defaults={'team_name': 'TBD', 'short_name': 'TBD'})
            return team
        raise


def get_teams_from_espn(season=None):
    season = season or h.current_season()
    url = f'{BASE_URL}/nfl/seasons/{season}/teams?limit=50'
    logger.info(f"Fetching teams from {url}")
    data = session.get(url).json()
    for x in data['items']:
        team_id = h.extract_int(x['$ref'], 'teams')
        url = f'{BASE_URL}/nfl/seasons/{season}/teams/{team_id}'
        logger.info(f"Fetching team from {url}")
        team = session.get(url).json()
        team, created = models.Team.objects.update_or_create(
            team_id=team_id,
            defaults={
                'team_name': team['displayName'],
                'short_name': team['abbreviation'],
            })
        print(f'{team}: {created}')


def get_games_from_espn(week=None):
    if week:
        weeks_to_update = [week]
    else:
        weeks_to_update = models.Calendar.objects.filter(end_date__gte=timezone.now())

    for w in weeks_to_update:
        url = f'{BASE_URL}/nfl/seasons/{w.season}/types/{w.season_type_id}/weeks/{w.week_num}/events'
        logger.info(f"Fetching games from {url}")
        games = session.get(url).json()
        for x in games['items']:
            event_id = h.extract_int(x['$ref'], 'events')
            url = f'{BASE_URL}/nfl/events/{event_id}'
            logger.info(f"Fetching event from {url}")
            event = session.get(url).json()
            short_name = event['shortName']
            if event['competitions'][0]['competitors'][0]['homeAway'] == 'home':
                home_team_url = event['competitions'][0]['competitors'][0]['team']['$ref']
                away_team_url = event['competitions'][0]['competitors'][1]['team']['$ref']
            else:
                away_team_url = event['competitions'][0]['competitors'][0]['team']['$ref']
                home_team_url = event['competitions'][0]['competitors'][1]['team']['$ref']

            home_team_id = h.extract_int(home_team_url, 'teams')
            away_team_id = h.extract_int(away_team_url, 'teams')

            models.Game.objects.update_or_create(
                event_id=event_id,
                defaults={
                    'week_num': w.week_num,
                    'season': w.season,
                    'season_type_id': w.season_type_id,
                    'week': w,
                    'game_datetime': event['date'],
                    'short_name': short_name,
                    'home_team': get_team_for_game(home_team_id),
                    'away_team': get_team_for_game(away_team_id),
                })

            print(f'Updated/Created data for {short_name}; {w.name} in {w.season_type_name}')


#update a game object with latest info (kickoff, teams, score, status)
def update_game(game):
    try:
        url = f'https://cdn.espn.com/core/nfl/game?xhr=1&gameId={game.event_id}'
        logger.info(f"Fetching game data from {url}")
        response = session.get(url)
        data = response.json()
        data = data.get('gamepackageJSON')
        competition = data['header']['competitions'][0]
        game.game_datetime = competition['date']
        if competition['competitors'][0]['homeAway'] == 'home':
            home, away = competition['competitors'][0], competition['competitors'][1]
        else:
            away, home = competition['competitors'][0], competition['competitors'][1]
        game.home_team = get_team_for_game(home['id'])
        game.away_team = get_team_for_game(away['id'])
        status_type = competition.get('status', {}).get('type', {})
        game.status = map_game_status(status_type.get('state'), status_type.get('completed', False))
        if home.get('score') not in (None, ''):
            game.home_score = int(home['score'])
        if away.get('score') not in (None, ''):
            game.away_score = int(away['score'])
        print(f'Updated {game}, {game.game_datetime} [{game.status}]')
        game.save()
    except Exception as e:
        logger.error(f"An error occurred during update_game for game {game.event_id}: {e}")


def update_upcoming_games():
    """Refresh games in a window around now: upcoming games (kickoff moves,
    TBD resolution) plus recent/unfinished games so final scores land."""
    now_dt = timezone.now()
    games = models.Game.objects.filter(
        Q(game_datetime__gt=now_dt - timedelta(days=3), game_datetime__lt=now_dt + timedelta(days=15)) |
        Q(game_datetime__lte=now_dt, game_datetime__gt=now_dt - timedelta(days=30),
          status__in=[models.Game.STATUS_SCHEDULED, models.Game.STATUS_IN])
    )
    [update_game(x) for x in games]





def week_num_odds(week_num=None):
    if not week_num:
        week_num = h.current_week().week_num
    games = models.Game.objects.filter(week_num=week_num)
    num = 0
    for x in games:
        url = f'{BASE_URL}/nfl/events/{x.event_id}/competitions/{x.event_id}/odds'
        logger.info(f"Fetching odds from {url}")
        data = session.get(url).json()
        if len(data['items']) > 0:
            if data['items'][0].get('details'):
                spread_display = data['items'][0]['details']
                spread = int(data['items'][0]['spread'])
                odds, created = models.Outcome.objects.update_or_create(
                            event_id=x,
                            defaults={
                                'spread_display': spread_display,
                                'spread': spread,
                                'last_updated': timezone.now()
                            }
                        )
                num += 1

        url = f'{BASE_URL}/nfl/events/{x.event_id}/competitions/{x.event_id}/powerindex/{x.home_team.team_id}'
        logger.info(f"Fetching power index from {url}")
        data = session.get(url).json()
        if data.get('stats'):
            pred_diff = float(data['stats'][0]['value'])
            home_win_prob = float(data['stats'][1]['value'])
            away_win_prob = 100-home_win_prob
            odds, created = models.Outcome.objects.update_or_create(
                            event_id=x,
                            defaults={
                                'pred_diff': pred_diff,
                                'home_win_prob': home_win_prob,
                                'away_win_prob': away_win_prob,
                                'last_updated': timezone.now()
                            }
                        )

    print(f'Updated {num} odds for week {week_num}')


def single_game_odds(game):
    try:
        url = f'{BASE_URL}/nfl/events/{game.event_id}/competitions/{game.event_id}/odds'
        logger.info(f"Fetching odds from {url}")
        response = session.get(url)
        logger.info(f"Response status code: {response.status_code}")
        data = response.json()
        if len(data['items']) > 0:
            if data['items'][0].get('details'):
                spread_display = data['items'][0]['details']
                spread = int(data['items'][0]['spread'])
                odds, created = models.Outcome.objects.update_or_create(
                                event_id=game,
                                defaults={
                                    'spread_display': spread_display,
                                    'spread': spread,
                                    'last_updated': timezone.now()
                                }
                            )
                print(f'Updated odds for {game.short_name}')
    except Exception as e:
        logger.error(f"An error occurred during single_game_odds for game {game.event_id}: {e}")


def single_game_probs(game):
    url = f'{BASE_URL}/nfl/events/{game.event_id}/competitions/{game.event_id}/powerindex/{game.home_team.team_id}'
    logger.info(f"Fetching power index from {url}")
    response = session.get(url)
    logger.info(f"Response status code: {response.status_code}")
    logger.info(f"Response content: {response.text}")
    data = response.json()
    if data.get('stats'):
        pred_diff = float(data['stats'][0]['value'])
        home_win_prob = float(data['stats'][1]['value'])
        away_win_prob = 100-home_win_prob
        odds, created = models.Outcome.objects.update_or_create(
                            event_id=game,
                            defaults={
                                'pred_diff': pred_diff,
                                'home_win_prob': home_win_prob,
                                'away_win_prob': away_win_prob,
                                'last_updated': timezone.now()
                            }
                        )


def get_athletes_from_espn(team_id):
    team = models.Team.objects.get(pk=team_id)
    url = f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster?limit=200'
    logger.info(f"Fetching athletes from {url}")
    data = session.get(url).json()
    for group in data['athletes']:
        for a in group['items']:
            player = models.Athlete.objects.update_or_create(
                athlete_id =a['id'],
                defaults = {
                    'first_name': a['firstName'],
                    'last_name': a['lastName'],
                    'display_name': a.get('displayName'),
                    'team': team,
                    'jersey': a.get('jersey', None),
                    'position': a['position']['name'],
                    'position_id': a['position']['id'],
                    'position_abbreviation': a['position'].get('abbreviation'),
                    'age': a.get('age', None),
                    'weight': a.get('weight', None) ,
                    'height': a.get('height', None) ,
                    'injuries': a['injuries'],
                    'status': a['status']['name'],
                    'status_id': a['status']['id'],
                    'debut_year': a.get('debutYear', None)})
            print(player[0])


def format_datetime_to_est(dt):
    est_tz = pytz.timezone('America/New_York')

    # Check if dt is a string and try to parse it
    if isinstance(dt, str):
        try:
            # First attempt to parse in the format you expect
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # If that fails, try another format (e.g., 'Sep 15, 1:00 PM')
            try:
                dt = datetime.strptime(dt, '%b %d, %I:%M %p')
            except ValueError as e:
                raise ValueError(f"Date format not recognized: {dt}") from e

    # If no timezone info is provided, assume UTC
    if dt.tzinfo is None:
        utc_tz = pytz.utc
        dt = utc_tz.localize(dt)

    # Convert to EST timezone
    est_dt = dt.astimezone(est_tz)
    # Format the date as needed
    formatted_date = est_dt.strftime('%b %d, %-I:%M %p')

    return formatted_date


def should_update(game):
    one_day_ago = timezone.now() - timedelta(days=1)
    if game.outcome is None or game.outcome.last_updated is None or game.outcome.last_updated < one_day_ago:
        return True
    elif game.game_datetime.date() == datetime.today().date():
        return True
    else:
        return False


def team_stats(team_id, season=None):
    season = season or h.current_season()
    url = f'{BASE_URL}/nfl/seasons/{season}/types/2/teams/{team_id}/statistics'
    logger.info(f"Fetching team stats from {url}")
    data = session.get(url).json()
    if not data.get('splits') or data.get('splits').get('category'):
            return
    data = data['splits']['categories']
    team = models.Team.objects.get(pk=team_id)
    for category in data:
        if category.get('stats') and category.get('name'):
            cat = category['name']
            for stat in category['stats']:
                if stat.get('name'):
                    models.StatTeam.objects.update_or_create(
                        team_id = team,
                        season = season,
                        stat_name = stat['name'],
                        category = cat,
                        defaults = {
                        'value': stat['value'],
                        'rank': stat.get('rank', None),
                        'display_rank': stat.get('rankDisplayValue', 'n/a'),
                        'description': stat['description']

                    })
    print(f'Updated {season} stats for {team}')


def get_team_records(season=None):
    season = season or h.current_season()
    teams = models.Team.objects.all()
    for x in teams:
        url = f'{BASE_URL}/nfl/seasons/{season}/types/2/teams/{x.team_id}/record'
        logger.info(f"Fetching team records from {url}")
        data = session.get(url).json()
        if data.get('items'):
            record = data['items'][0].get('displayValue', '-')
            x.record = record
            x.last_updated = timezone.now()
            print(x.short_name, x.record)
            x.save()



def update_odds_cron():
    future_games = models.Game.objects.filter(game_datetime__gt=timezone.now())
    for game in future_games:
        single_game_odds(game)
        single_game_probs(game)
        print(f'Updated odds and probabilities for {game}')


def update_probs_cron():
    week = h.current_week()
    probs_to_update = models.Game.objects.filter(
        season=week.season, week_num__gte=week.week_num)
    for x in probs_to_update:
        single_game_probs(x)


def current_schedule(season=None):
    """Fetch a season's calendar and upsert it keyed on
    (season, season_type_id, week_num) — never on week name, which collides
    across seasons and season types."""
    season = season or h.current_season()
    url = f'https://cdn.espn.com/core/nfl/schedule?xhr=1&year={season}'
    logger.info(f"Fetching schedule calendar from {url}")
    calendar = (session.get(url).json())['content']['calendar']
    for x in calendar:
        if int(x['value']) in (2, 3):
            season_type = x['label']
            for y in x['entries']:
                models.Calendar.objects.update_or_create(
                    season = season,
                    season_type_id = int(x['value']),
                    week_num = int(y['value']),
                    defaults = {
                        'name': y['alternateLabel'],
                        'details': y['detail'],
                        'season_type_name': season_type,
                        'start_date': y['startDate'],
                        'end_date': y['endDate'],
                    }
                )