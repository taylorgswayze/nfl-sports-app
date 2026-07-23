import utils.get_data as g
import utils.helpers as h
from django.core.management.base import BaseCommand
from django.core.management import call_command
from nfl.models import Team, Calendar, Game, Athlete

class Command(BaseCommand):
    def handle (self, *args, **kwargs):
        season = h.current_season()
        confirmation = input(f"Are you sure you want to fetch all {season} data? (yes/no): ")
        if confirmation == 'yes':

        #Step 1: Get current season team data
            g.get_teams_from_espn(season)
            g.get_team_records(season)

        #Step 2: Get season schedule
            call_command('update_calendar', season=season)

        #Step 3: Get all current season games
            schedule_weeks = Calendar.objects.filter(season=season)
            [g.get_games_from_espn(x) for x in schedule_weeks]

        #Step 4: Get/update roster data
            teams = Team.objects.all()
            [g.get_athletes_from_espn(x.team_id) for x in teams]

        #Step 5: Get/update statistics
            [g.team_stats(x.team_id) for x in teams]

        else:
            print("Cancelling...")
