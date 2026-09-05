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


class UpdateRosters(CronJobBase):
    """Daily: every team's current roster and depth chart; players who left
    a team are detached so stale entries cannot linger."""
    schedule = Schedule(run_every_mins=1440)
    code = 'nfl.update_rosters'

    def do(self):
        call_command('update_rosters')


class UpdatePlayerStats(CronJobBase):
    """Every 6 hours: boxscore-based player stats for recently completed
    games. No-ops out of season (no recent finals)."""
    schedule = Schedule(run_every_mins=360)
    code = 'nfl.update_player_stats'

    def do(self):
        call_command('update_recent_player_stats')


class WeekRoomRefresh(CronJobBase):
    """Every 12 hours: rebuild the Week Room (lineup, waiver and trade
    advice) for every Sleeper user the Desk knows: signed-in accounts with
    a saved handle plus any handle that has loaded the page."""
    schedule = Schedule(run_every_mins=720)
    code = 'nfl.week_room_refresh'

    def do(self):
        call_command('fantasy_insights', '--all')
