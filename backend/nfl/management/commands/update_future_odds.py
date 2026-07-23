from django.core.management.base import BaseCommand
from utils import get_data

class Command(BaseCommand):
    help = "Update odds and win probabilities for all future games."

    def handle(self, *args, **kwargs):
        self.stdout.write("Updating odds and win probabilities for all future games...")
        get_data.update_future_game_odds_and_probs()
        self.stdout.write(self.style.SUCCESS("Successfully updated odds and win probabilities for all future games."))
