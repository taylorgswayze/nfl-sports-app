"""Refresh every team's roster and depth chart from ESPN.

Players missing from their team's payload are detached (team, status and
depth cleared) so trades and cuts self-heal; the acquiring team's fetch
reassigns them. A failed fetch leaves that team untouched rather than
wiping its roster.
"""

from django.core.management.base import BaseCommand

import utils.get_data as get_data
from nfl.models import Athlete, Team


class Command(BaseCommand):
    help = 'Refresh rosters and depth charts for all teams from ESPN'

    def handle(self, *args, **options):
        teams = Team.objects.exclude(team_id__in=get_data.TBD_TEAM_IDS)
        for team in teams:
            try:
                seen = get_data.get_athletes_from_espn(team.team_id)
                if seen:
                    departed = (Athlete.objects.filter(team=team)
                                .exclude(athlete_id__in=seen)
                                .update(team=None, status=None, status_id=None,
                                        depth_rank=None, depth_slot=None))
                else:
                    departed = 0
                get_data.apply_depth_chart(team.team_id)
                self.stdout.write(
                    f'{team.short_name}: {len(seen)} on roster, {departed} detached')
            except Exception as e:
                self.stderr.write(f'{team.short_name}: failed, left untouched: {e}')
