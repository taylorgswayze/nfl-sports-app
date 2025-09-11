from datetime import datetime, timedelta
from django.utils.timezone import now
from django.core.management.base import BaseCommand
from utils import helpers  # Adjusted import

CURRENT_YEAR = (datetime.now() - timedelta(days=150)).year
NOW = now()

class Command(BaseCommand):
    help = "Return current week in season"

    def handle(self, *args, **kwargs):
        # Call the function defined in the helpers module
        current_week = helpers.current_week()
        if current_week:
            self.stdout.write(f"Current schedule week is {current_week.name} of the {current_week.details}")
        else:
            self.stdout.write("No current week found.")
