from django.core.management import call_command
from django_cron import CronJobBase, Schedule


class UpdateSeasonData(CronJobBase):
    """Hourly: calendar, team records, game info incl. scores/status, odds."""
    schedule = Schedule(run_every_mins=60)
    code = 'nfl.update_season_data'

    def do(self):
        call_command('update_season_data')


class UpdateTeamStats(CronJobBase):
    """Hourly: season stat lines for every team."""
    schedule = Schedule(run_every_mins=60)
    code = 'nfl.update_team_stats'

    def do(self):
        call_command('update_team_stats')


class UpdatePlayerStats(CronJobBase):
    """Every 6 hours: boxscore-based player stats for recently completed
    games. No-ops out of season (no recent finals)."""
    schedule = Schedule(run_every_mins=360)
    code = 'nfl.update_player_stats'

    def do(self):
        call_command('update_recent_player_stats')
