from datetime import datetime, timedelta

from requests import get
from django.utils.timezone import now
from django.core.management.base import BaseCommand
from utils import get_data
from nfl import models
import logging

logger = logging.getLogger(__name__)

CURRENT_YEAR = (datetime.now() - timedelta(days=150)).year
NOW = now()

class Command(BaseCommand):
    help = "Update game info for games in current and upcoming weeks"

    def handle(self, *args, **kwargs):
        try:
            get_data.update_upcoming_games()
        except Exception as e:
            logger.error(f"An error occurred during update_game_info: {e}")
            self.stdout.write(self.style.ERROR(f"An error occurred: {e}"))
