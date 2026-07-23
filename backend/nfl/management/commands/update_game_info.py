from django.core.management.base import BaseCommand
from utils import get_data
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Update game info for games in current and upcoming weeks"

    def handle(self, *args, **kwargs):
        try:
            get_data.update_upcoming_games()
        except Exception as e:
            logger.error(f"An error occurred during update_game_info: {e}")
            self.stdout.write(self.style.ERROR(f"An error occurred: {e}"))
