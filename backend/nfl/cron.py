from utils.get_data import update_game
from django_cron import CronJobBase, Schedule
import utils.get_date as g
from django.utils import timezone
from datetime import timedelta, datetime
from nfl.models import Game
from django.core.management import call_command


class RefreshEveryDay(CronJobBase):
    schedule = Schedule(run_every_mins=1440)
    code = 'nfl.refresh_every_day'  # This is a unique code for your cron job.
    def do(self):
        g.current_schedule()


class RefreshEveryHour(CronJobBase):
    schedule = Schedule(run_every_mins=60)
    code = 'nfl.refresh_every_hour'  # This is a unique code for your cron job.
    def do(self):
        g.get_team_records()
        g.update_odds_cron()
        g.update_probs_cron()
        g.update_upcoming_games()


class RefreshEveryMinute(CronJobBase):
    schedule = Schedule(run_every_mins=1)
    code = 'nfl.refresh_every_minute'  # This is a unique code for your cron job.
    def do(self):
        now = timezone.now()
        bt_a, bt_b = now - timedelta(hours=4), now + timedelta(hours=5)
        live_games = Game.objects.filter(game_datetime__gte=bt_a, game_datetime__lte=bt_b)
        [g.update_game(x) for x in live_games]
        [g.single_game_odds(x) for x in live_games]


class UpdatePlayerStatsEvery10Minutes(CronJobBase):
    schedule = Schedule(run_every_mins=10)
    code = 'nfl.update_player_stats_10min'
    
    def do(self):
        """Update player stats for active games every 10 minutes"""
        now = timezone.now()
        
        # Find games that are currently active (started within last 4 hours, not finished)
        active_window_start = now - timedelta(hours=4)
        active_window_end = now + timedelta(minutes=30)  # Include games starting soon
        
        active_games = Game.objects.filter(
            game_datetime__gte=active_window_start,
            game_datetime__lte=active_window_end
        )
        
        if active_games.exists():
            call_command('update_player_stats')


class UpdatePlayerStatsPostGame(CronJobBase):
    schedule = Schedule(run_every_mins=60)  # Check hourly for post-game updates
    code = 'nfl.update_player_stats_postgame'
    
    def do(self):
        """Final update 4 hours after game start"""
        now = timezone.now()
        
        # Find games that finished approximately 4 hours ago (±30 min window)
        postgame_window_start = now - timedelta(hours=4, minutes=30)
        postgame_window_end = now - timedelta(hours=3, minutes=30)
        
        recent_games = Game.objects.filter(
            game_datetime__gte=postgame_window_start,
            game_datetime__lte=postgame_window_end
        )
        
        if recent_games.exists():
            call_command('update_player_stats')
