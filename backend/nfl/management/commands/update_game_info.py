from datetime import datetime, timedelta

from requests import get
from django.utils.timezone import now
from django.core.management.base import BaseCommand
from utils import get_data
from nfl import models

CURRENT_YEAR = (datetime.now() - timedelta(days=150)).year
NOW = now()

class Command(BaseCommand):
    help = "Update game info for games in current and upcoming weeks"

    def handle(self, *args, **kwargs):
        get_data.update_upcoming_games()
