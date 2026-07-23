import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from nfl.models import Athlete, SeasonStatistic
import utils.helpers as h


class Command(BaseCommand):
    help = "Fetch season statistics for athletes from the ESPN gamelog API"

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, help='Season year (default: current)')
        parser.add_argument('--athlete-id', type=int, help='Specific athlete ID')

    def handle(self, *args, **options):
        season = options['season'] or h.current_season()
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
                    self.stdout.write(f"+ {athlete.display_name or f'{athlete.first_name} {athlete.last_name}'}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed {athlete}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"Updated stats for {updated_count} athletes"))

    def fetch_athlete_stats(self, athlete, season):
        """Fetch season totals from the ESPN gamelog API.

        The payload carries a top-level ``names`` list (real ESPN stat names,
        e.g. passingYards) and a ``categories`` list giving how many of those
        names belong to each category (passing, rushing, ...). Season-type
        blocks then carry ``totals`` aligned 1:1 with ``names``.
        """
        url = (f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/"
               f"athletes/{athlete.athlete_id}/gamelog?season={season}")

        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return False

        data = response.json()

        # Update athlete display name if missing
        if not athlete.display_name and 'athlete' in data:
            athlete.display_name = data['athlete'].get('displayName')
            athlete.save()

        names = data.get('names') or []
        categories = data.get('categories') or []
        if not names or not categories:
            return False

        # Map each index in `names`/`totals` to its category name.
        index_category = []
        for cat in categories:
            index_category.extend([cat.get('name', 'general')] * int(cat.get('count', 0)))

        stats_saved = False
        for season_type in data.get('seasonTypes', []):
            type_name = season_type.get('displayName', '')
            if str(season) not in type_name:
                continue
            season_type_label = 'Postseason' if 'postseason' in type_name.lower() else 'Regular Season'

            for block in season_type.get('categories', []):
                totals = block.get('totals', [])
                if not totals or len(totals) != len(names):
                    continue

                for i, value in enumerate(totals):
                    if value in (None, '', '--'):
                        continue
                    try:
                        numeric_value = float(str(value).replace(',', ''))
                    except (ValueError, AttributeError):
                        numeric_value = None

                    SeasonStatistic.objects.update_or_create(
                        athlete=athlete,
                        season_year=season,
                        season_type=season_type_label,
                        category_name=index_category[i] if i < len(index_category) else 'general',
                        stat_name=names[i],
                        defaults={
                            'stat_value': numeric_value,
                            'stat_display_value': str(value),
                            'last_updated': timezone.now()
                        }
                    )
                    stats_saved = True

        return stats_saved
