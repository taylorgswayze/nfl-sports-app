from django.core.management.base import BaseCommand
from django.core.management import call_command
from utils import get_data

class Command(BaseCommand):
    help = "Update all current season game info (schedule, team records, and odds)"

    def handle(self, *args, **kwargs):
        self.stdout.write("Updating calendar...")
        call_command('update_calendar')
        self.stdout.write(self.style.SUCCESS("Successfully updated calendar."))

        self.stdout.write("Updating team records...")
        get_data.get_team_records()
        self.stdout.write(self.style.SUCCESS("Successfully updated team records."))

        self.stdout.write("Updating game info...")
        call_command('update_game_info')
        self.stdout.write(self.style.SUCCESS("Successfully updated game info."))

        self.stdout.write("Updating odds...")
        get_data.update_odds_cron()
        self.stdout.write(self.style.SUCCESS("Successfully updated odds."))

        self.stdout.write(self.style.SUCCESS("All current season data has been updated."))
