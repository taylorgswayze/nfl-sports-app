from django.core.management.base import BaseCommand
from utils import get_data

class Command(BaseCommand):
    help = "Update odds and win probabilities for a specific week."

    def add_arguments(self, parser):
        parser.add_argument('week_num', type=int, help='The week number to update.')

    def handle(self, *args, **kwargs):
        week_num = kwargs['week_num']
        self.stdout.write(f"Updating odds and win probabilities for week {week_num}...")
        get_data.week_num_odds(week_num)
        self.stdout.write(self.style.SUCCESS(f"Successfully updated odds and win probabilities for week {week_num}."))
