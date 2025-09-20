from django.core.management.base import BaseCommand
from nfl.models import Team
from utils import get_data

class Command(BaseCommand):
    help = "Update team stats for all teams"

    def handle(self, *args, **kwargs):
        self.stdout.write("Updating team stats...")
        teams = Team.objects.all()
        for team in teams:
            try:
                self.stdout.write(f"Updating stats for {team.team_name}...")
                get_data.team_stats(team.team_id)
                self.stdout.write(self.style.SUCCESS(f"Successfully updated stats for {team.team_name}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error updating stats for {team.team_name}: {e}"))
        self.stdout.write(self.style.SUCCESS("All team stats have been updated."))
