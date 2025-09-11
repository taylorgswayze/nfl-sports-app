from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from nfl.models import Game, Athlete, SeasonStatistic
from nfl.management.commands.fetch_player_stats import Command as FetchStatsCommand

class Command(BaseCommand):
    help = "Update player stats for active/recent games"

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force update all players')

    def handle(self, *args, **options):
        now = timezone.now()
        
        if options['force']:
            # Update all athletes
            athletes = Athlete.objects.all()
            self.stdout.write(f"Force updating all {athletes.count()} athletes")
        else:
            # Find games that are currently active or recently finished
            active_window_start = now - timedelta(minutes=10)
            recent_window_end = now + timedelta(hours=4)
            
            active_games = Game.objects.filter(
                game_datetime__gte=active_window_start,
                game_datetime__lte=recent_window_end
            )
            
            if not active_games.exists():
                self.stdout.write("No active or recent games found")
                return
            
            # Get athletes from teams in active/recent games
            team_ids = []
            for game in active_games:
                team_ids.extend([game.home_team.team_id, game.away_team.team_id])
            
            athletes = Athlete.objects.filter(team__team_id__in=team_ids)
            self.stdout.write(f"Updating {athletes.count()} athletes from {len(active_games)} active/recent games")
        
        # Use the fetch stats command logic
        fetch_command = FetchStatsCommand()
        updated_count = 0
        
        for athlete in athletes:
            try:
                if fetch_command.fetch_athlete_stats(athlete, 2025):  # Current season
                    updated_count += 1
                    self.stdout.write(f"✓ {athlete.display_name or f'{athlete.first_name} {athlete.last_name}'}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed {athlete}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(f"Updated stats for {updated_count} athletes"))
