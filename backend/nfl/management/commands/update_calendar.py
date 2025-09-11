import requests
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from nfl import models  # Import your models here

CURRENT_YEAR = (datetime.now() - timedelta(days=140)).year

class Command(BaseCommand):
    help = "Fetch and update the current NFL schedule."

    def handle(self, *args, **kwargs):
        self.stdout.write(f"Updating schedule for {CURRENT_YEAR}...")
        url = f'https://cdn.espn.com/core/nfl/schedule?xhr=1&year={CURRENT_YEAR}'
        response = requests.get(url)

        if response.status_code != 200:
            self.stderr.write("Failed to fetch schedule data.")
            return

        calendar = response.json().get('content', {}).get('calendar', [])
        for x in calendar:
            if int(x['value']) in {2, 3}:  # Season types
                season_type = x['label']
                for y in x['entries']:
                    models.Calendar.objects.update_or_create(
                        name=y['alternateLabel'],
                        defaults={
                            'details': y['detail'],
                            'week_num': y['value'],
                            'season': CURRENT_YEAR,
                            'season_type_id': x['value'],
                            'season_type_name': season_type,
                            'start_date': y['startDate'],
                            'end_date': y['endDate'],
                        }
                    )
                    self.stdout.write(f"Updated week {y['value']} - {y['alternateLabel']}")

        self.stdout.write("Schedule update completed.")
