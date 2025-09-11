import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from nfl.models import Athlete, SeasonStatistic
import utils.get_data as get_data

class Command(BaseCommand):
    help = "Fetch season statistics for all athletes"

    # Common stat mappings for different positions
    STAT_MAPPINGS = {
        'passing': ['completions', 'attempts', 'yards', 'completion_pct', 'yards_per_attempt', 
                   'touchdowns', 'interceptions', 'sacks', 'sack_yards', 'rating', 
                   'qbr', 'longest', 'rushing_attempts', 'rushing_yards', 'rushing_avg'],
        'rushing': ['attempts', 'yards', 'avg', 'longest', 'touchdowns'],
        'receiving': ['receptions', 'yards', 'avg', 'longest', 'touchdowns', 'targets'],
        'defense': ['tackles', 'solo', 'assists', 'sacks', 'sack_yards', 'tackles_for_loss', 
                   'passes_defended', 'interceptions', 'int_yards', 'int_touchdowns'],
        'kicking': ['field_goals_made', 'field_goals_attempted', 'field_goal_pct', 'longest_fg',
                   'extra_points_made', 'extra_points_attempted', 'points']
    }

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, help='Season year (default: current)')
        parser.add_argument('--athlete-id', type=int, help='Specific athlete ID')

    def handle(self, *args, **options):
        season = options['season'] or get_data.CURRENT_YEAR
        athlete_id = options['athlete_id']
        
        if athlete_id:
            athletes = Athlete.objects.filter(athlete_id=athlete_id)
        else:
            athletes = Athlete.objects.all()
        
        self.stdout.write(f"Fetching stats for {athletes.count()} athletes (season {season})")
        
        updated_count = 0
        for athlete in athletes:
            try:
                if self.fetch_athlete_stats(athlete, season):
                    updated_count += 1
                    self.stdout.write(f"✓ {athlete.display_name or f'{athlete.first_name} {athlete.last_name}'}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed {athlete}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(f"Updated stats for {updated_count} athletes"))

    def fetch_athlete_stats(self, athlete, season):
        """Fetch stats using ESPN gamelog API"""
        url = f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{athlete.athlete_id}/gamelog"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return False
                
            data = response.json()
            
            # Update athlete display name if missing
            if not athlete.display_name and 'athlete' in data:
                athlete.display_name = data['athlete'].get('displayName')
                athlete.save()
            
            stats_saved = False
            
            # Process season types (Regular Season, Playoffs)
            for season_type in data.get('seasonTypes', []):
                season_name = season_type.get('displayName', '')
                if str(season) not in season_name:
                    continue
                    
                # Process categories (passing, rushing, etc.)
                for category in season_type.get('categories', []):
                    category_name = category.get('displayName', 'General').lower()
                    totals = category.get('totals', [])
                    
                    if not totals:
                        continue
                    
                    # Determine stat mapping based on category or position
                    stat_names = self.get_stat_names_for_category(category_name, athlete.position)
                    
                    # Map totals to stat names
                    for i, value in enumerate(totals):
                        if i < len(stat_names) and value and value != '--':
                            try:
                                numeric_value = float(str(value).replace(',', ''))
                            except (ValueError, AttributeError):
                                numeric_value = None
                            
                            SeasonStatistic.objects.update_or_create(
                                athlete=athlete,
                                season_year=season,
                                season_type='Regular Season',
                                category_name=category_name,
                                stat_name=stat_names[i],
                                defaults={
                                    'stat_value': numeric_value,
                                    'stat_display_value': str(value),
                                    'last_updated': timezone.now()
                                }
                            )
                            stats_saved = True
            
            return stats_saved
            
        except requests.RequestException as e:
            self.stdout.write(self.style.WARNING(f"API error for {athlete}: {str(e)}"))
            return False

    def get_stat_names_for_category(self, category_name, position):
        """Get appropriate stat names based on category and position"""
        category_lower = category_name.lower()
        
        if 'passing' in category_lower or (position and 'quarterback' in position.lower()):
            return self.STAT_MAPPINGS['passing']
        elif 'rushing' in category_lower:
            return self.STAT_MAPPINGS['rushing']
        elif 'receiving' in category_lower:
            return self.STAT_MAPPINGS['receiving']
        elif 'defense' in category_lower or 'defensive' in category_lower:
            return self.STAT_MAPPINGS['defense']
        elif 'kicking' in category_lower or (position and 'kicker' in position.lower()):
            return self.STAT_MAPPINGS['kicking']
        else:
            # Generic stat names for unknown categories
            return [f'stat_{i}' for i in range(20)]
