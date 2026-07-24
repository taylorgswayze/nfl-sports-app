from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command


class Command(BaseCommand):
    help = "Backfill a range of NFL seasons (oldest first) via backfill_season."

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='start', type=int, required=True)
        parser.add_argument('--to', dest='end', type=int, required=True)
        parser.add_argument('--types', type=str, default='2,3')
        parser.add_argument('--skip-game-stats', action='store_true')
        parser.add_argument('--sleep', type=float, default=0.3)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        start, end = options['start'], options['end']
        if start > end:
            raise CommandError('--from must be <= --to')
        for season in range(start, end + 1):
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"===== Backfilling season {season} ====="))
            try:
                call_command(
                    'backfill_season',
                    season=season,
                    types=options['types'],
                    skip_game_stats=options['skip_game_stats'],
                    sleep=options['sleep'],
                    dry_run=options['dry_run'],
                )
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f"Season {season} backfill failed: {e} — continuing with next season"))
        self.stdout.write(self.style.SUCCESS(f"Backfill range {start}-{end} finished."))
