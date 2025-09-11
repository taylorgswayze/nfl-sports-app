import requests
from django.core.management.base import BaseCommand
from django.db import models
from nfl.models import Athlete

class Command(BaseCommand):
    help = "Fix missing player names by fetching from ESPN API"

    def handle(self, *args, **options):
        athletes = Athlete.objects.filter(
            models.Q(display_name__isnull=True) | 
            models.Q(display_name='') |
            models.Q(first_name__isnull=True) |
            models.Q(last_name__isnull=True)
        )
        
        self.stdout.write(f"Found {athletes.count()} athletes with missing names")
        
        updated_count = 0
        for athlete in athletes:
            try:
                url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/{athlete.athlete_id}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Update names
                    athlete.display_name = data.get('displayName', '')
                    athlete.first_name = data.get('firstName', '')
                    athlete.last_name = data.get('lastName', '')
                    
                    # Also update position abbreviation if missing
                    if not athlete.position_abbreviation and 'position' in data:
                        athlete.position_abbreviation = data['position'].get('abbreviation', '')
                    
                    athlete.save()
                    updated_count += 1
                    
                    self.stdout.write(f"✓ Updated {athlete.display_name}")
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed to update athlete {athlete.athlete_id}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(f"Updated {updated_count} athlete names"))
