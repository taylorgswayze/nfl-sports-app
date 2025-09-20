from django.core.management import call_command
from django_cron import CronJobBase, Schedule

class RefreshEveryDay(CronJobBase):
    schedule = Schedule(run_every_mins=1440)
    code = 'nfl.refresh_every_day'

    def do(self):
        pass

class RefreshEveryHour(CronJobBase):
    schedule = Schedule(run_every_mins=60)
    code = 'nfl.refresh_every_hour'

    def do(self):
        pass

class RefreshEveryMinute(CronJobBase):
    schedule = Schedule(run_every_mins=1)
    code = 'nfl.refresh_every_minute'

    def do(self):
        pass

class UpdatePlayerStatsEvery10Minutes(CronJobBase):
    schedule = Schedule(run_every_mins=10)
    code = 'nfl.update_player_stats_every_10_minutes'

    def do(self):
        pass

class UpdatePlayerStatsPostGame(CronJobBase):
    schedule = Schedule(run_every_mins=1440)
    code = 'nfl.update_player_stats_post_game'

    def do(self):
        pass

class UpdateSeasonData(CronJobBase):
    schedule = Schedule(run_every_mins=60)
    code = 'nfl.update_season_data'

    def do(self):
        call_command('update_season_data')

class UpdateTeamStats(CronJobBase):
    schedule = Schedule(run_every_mins=60)
    code = 'nfl.update_team_stats'

    def do(self):
        call_command('update_team_stats')