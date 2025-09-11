from django.http import HttpResponse
from django.db.models import Q
import requests
import json
import pytz
from django.utils import timezone
from datetime import timedelta, datetime
import sys
import os
from nfl import models
import utils.helpers as h

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

CURRENT_YEAR = int(str(datetime.today() - timedelta(days=140))[:4])
CUREENT_WEEK = h.current_week()
NOW = datetime.today()
BASE_URL = 'https://sports.core.api.espn.com/v2/sports/football/leagues'


def get_teams_from_espn(season=None):
    if season:
        season = season
    else:
        season = CURRENT_YEAR
    [models.Team.objects.update_or_create(team_id=x, team_name='TBD', short_name='TBD') for x in [31,32]]
    data = requests.get(f'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{season}/teams?limit=50').json()
    for x in data['items']:
        team_id = h.extract_int(x['$ref'], 'teams')
        team = requests.get(f'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{season}/teams/{team_id}').json()
        team_name = team['displayName']
        short_name = team['abbreviation']
        team, created = models.Team.objects.update_or_create(team_id=team_id, team_name=team_name, short_name=short_name)
        print(f'{team}: {created}')

    return HttpResponse(models.Team.objects.all())


def get_games_from_espn(week=None):
    if week:
        weeks_to_update = [week]
    else:
        weeks_to_update = models.Calendar.objects.filter(end_date__gte=NOW)

    for w in weeks_to_update:
        games = requests.get(f'{BASE_URL}/nfl/seasons/{w.season}/types/{w.season_type_id}/weeks/{w.week_num}/events').json()
        for x in games['items']:
            event_id = h.extract_int(x['$ref'], 'events')
            event = requests.get(f'http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{event_id}').json()
            short_name = event['shortName']
            if event['competitions'][0]['competitors'][0]['homeAway'] == 'home':
                home_team_url = event['competitions'][0]['competitors'][0]['team']['$ref']
                away_team_url = event['competitions'][0]['competitors'][1]['team']['$ref']
            else:
                away_team_url = event['competitions'][0]['competitors'][0]['team']['$ref']
                home_team_url = event['competitions'][0]['competitors'][1]['team']['$ref']

            home_team_id = h.extract_int(home_team_url, 'teams')
            away_team_id = h.extract_int(away_team_url, 'teams')

            print(home_team_id, away_team_id)
            models.Game.objects.update_or_create(
                event_id = event_id,
                week_num = w.week_num,
                season = w.season,
                game_datetime = event['date'],
                short_name = short_name,
                home_team = models.Team.objects.get(pk=home_team_id),
                away_team = models.Team.objects.get(pk=away_team_id)
        )

            print(f'Updated/Created data for {short_name}; {w.name} in {w.season_type_name}')

#update a game object with latest info
def update_game(game):
    url = f'https://cdn.espn.com/core/nfl/game?xhr=1&gameId={game.event_id}'
    data = requests.get(url).json()
    data = data.get('gamepackageJSON')
    competition = data['header']['competitions'][0]
    game.game_datetime = competition['date']
    if competition['competitors'][0]['homeAway'] == 'home':
        home_id =  competition['competitors'][0]['id']
        away_id =  competition['competitors'][1]['id']
    else:
        away_id =  competition['competitors'][0]['id']
        home_id =  competition['competitors'][1]['id']
    game.home_team = models.Team.objects.get(team_id=home_id)
    game.away_team = models.Team.objects.get(team_id=away_id)
    print(f'Updated {game}, {game.game_datetime}')
    game.save()


#pass games
def update_upcoming_games():
    upcoming_comes = models.Game.obnjects.filter(game_datetime__gt=NOW, game_datetime__lt=NOW + timedelta(days=15))
    [update_game(x) for x in upcoming_comes]





def week_num_odds(week_num=None):
    if week_num:
        week_num = week_num
    else:
        week_num = current_week
    ganes = Game.objects.filter(week_num=week_num)
    num = 0
    for x in ganes:
        data = requests.get(f'{base_url}/nfl/events/{x.event_id}/competitions/{x.event_id}/odds').json()
        if len(data['items']) > 0:
            if data['items'][0].get('details'):
                spread_display = data['items'][0]['details']
                spread = int(data['items'][0]['spread'])
                odds, created = Outcome.objects.update_or_create(
                            event_id=x,
                            defaults={
                                'spread_display': spread_display,
                                'spread': spread,
                                'last_updated': timezone.make_aware(NOW)
                            }
                        )
                num += 1

        data = requests.get(f'{base_url}/nfl/events/{x.event_id}/competitions/{x.event_id}/powerindex/{x.home_team.team_id}').json()
        if data.get('stats'):
            pred_diff = float(data['stats'][0]['value'])
            home_win_prob = float(data['stats'][1]['value'])
            away_win_prob = 100-home_win_prob
            odds, created = Outcome.objects.update_or_create(
                            event_id=x,
                            defaults={
                                'pred_diff': pred_diff,
                                'home_win_prob': home_win_prob,
                                'away_win_prob': away_win_prob,
                            }
                        )

    h.console_flag(f'Updated {num} odds for week {week_num}')


def single_game_odds(game):
    data = requests.get(f'{BASE_URL}/nfl/events/{game.event_id}/competitions/{game.event_id}/odds').json()
    if len(data['items']) > 0:
        if data['items'][0].get('details'):
            spread_display = data['items'][0]['details']
            spread = int(data['items'][0]['spread'])
            odds, created = models.Outcome.objects.update_or_create(
                            event_id=game,
                            defaults={
                                'spread_display': spread_display,
                                'spread': spread,
                                'last_updated': timezone.make_aware(NOW)
                            }
                        )
            print(f'Updated odds for {game.short_name}')


def single_game_probs(game):
    data = requests.get(f'{BASE_URL}/nfl/events/{game.event_id}/competitions/{game.event_id}/powerindex/{game.home_team.team_id}').json()
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
                                'last_updated': timezone.make_aware(NOW)
                            }
                        )



def get_athletes_from_espn(team_id):
    team = models.Team.objects.get(pk=team_id)
    url = f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster?limit=200'
    data = requests.get(url).json()
    for group in data['athletes']:
        for a in group['items']:
            player = models.Athlete.objects.update_or_create(
                athlete_id =a['id'],
                defaults = {
                    'first_name': a['firstName'],
                    'last_name': a['lastName'],
                    'team': team,
                    'jersey': a.get('jersey', None),
                    'position': a['position']['name'],
                    'position_id': a['position']['id'],
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


def team_stats(team_id):
    base_url = f'{BASE_URL}/nfl/seasons/{CURRENT_YEAR}/types/2/teams'
    data = requests.get(f'{base_url}/{team_id}/statistics').json()
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
                        stat_name = stat['name'],
                        category = cat,
                        defaults = {
                        'team_id': team,
                        'value': stat['value'],
                        'rank': stat.get('rank', None),
                        'display_rank': stat.get('rankDisplayValue', 'n/a'),
                        'description': stat['description']

                    })
                    print(team, stat['name'], stat['value'])


def get_team_records():
    teams = models.Team.objects.all()
    for x in teams:
        data = requests.get(f'{BASE_URL}/nfl/seasons/{CURRENT_YEAR}/types/2/teams/{x.team_id}/record').json()
        if data['items']:
            record = data['items'][0].get('displayValue', '-')
            x.record = record
            x.last_updated = timezone.now()
            print(x.short_name, x.record)
            x.save()



def update_odds_cron():
    odds_to_update = models.Game.objects.filter(week_num=CUREENT_WEEK)
    for x in odds_to_update:
        single_game_odds(x)
        print(f'Updated {x}')


def update_probs_cron():
    probs_to_update = Game.objects.filter(week_num__gte=CUREENT_WEEK)
    for x in probs_to_update:
        single_game_probs(x)


def current_schedule():
    url = f'https://cdn.espn.com/core/nfl/schedule?xhr=1&year={CURRENT_YEAR}'
    calendar = (requests.get(url).json())['content']['calendar']
    for x in calendar:
        if int(x['value']) == 2 or int(x['value']) == 3:
            season_type = x['label']
            for y in x['entries']:
                models.Calendar.objects.update_or_create(
                    name = y['alternateLabel'],
                    defaults = {
                        'details': y['detail'],
                        'week_num': y['value'],
                        'season': CURRENT_YEAR,
                        'season_type_id': x['value'],
                        'season_type_name': season_type,
                        'start_date': y['startDate'],
                        'end_date': y['endDate'],
                    }
                )
