from datetime import datetime, timedelta
from django.utils.timezone import now
from django.core.management.base import BaseCommand
from nfl import models
from utils import get_data

CURRENT_YEAR = (datetime.now() - timedelta(days=150)).year
NOW = now()

class Command(BaseCommand):
    help = "Update game info for games in current and upcoming weeks"

    def handle(self, *args, **kwargs):

        games = models.Game.objects.all()
        [print(f'{x.short_name} {x.game_datetime} {x.event_id}') for x in games]

        print('Created record')
