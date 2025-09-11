import utils.get_data as g
from django.core.management.base import BaseCommand
from nfl.models import Team, Calendar, Game, Athlete
from nfl.management.commands.update_calendar import Command as update_cal

class Command(BaseCommand):
    def handle (self, *args, **kwargs):
        confirmation = input(f"Are you sure you want to fetch all {g.CURRENT_YEAR} data? (yes/no): ")
        if confirmation == 'yes':

        #Step 1: Get current season team data
            g.get_teams_from_espn()
            g.get_team_records()

        #Step 2: Get season schedule
            update = update_cal()
            update.handle()

        #Step 3: Get all current season games
            schedule_weeks = Calendar.objects.filter(season=g.CURRENT_YEAR)
            [g.get_games_from_espn(x) for x in schedule_weeks]

        #Step 4: Get/update roster data
            teams = Team.objects.all()
            [g.get_athletes_from_espn(x.team_id) for x in teams]

        #Step 5: Get/update statistics
            [g.team_stats(x.team_id) for x in teams]

        else:
            print("Cancelling...")
