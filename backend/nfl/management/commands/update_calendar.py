from django.core.management.base import BaseCommand
from utils import get_data, helpers


class Command(BaseCommand):
    help = "Fetch and upsert the NFL schedule calendar for a season."

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, help='Season year (default: current)')

    def handle(self, *args, **options):
        season = options.get('season') or helpers.current_season()
        self.stdout.write(f"Updating schedule calendar for {season}...")
        get_data.current_schedule(season)
        self.stdout.write("Schedule update completed.")
