import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from nfl.models import Game
from utils import boxscore


class Command(BaseCommand):
    help = ("Ingest player boxscores (GameStatistic) for recently completed "
            "games. Intended to run every ~6 hours during the season; no-ops "
            "when there are no recent finals.")

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=3,
                            help='Look-back window in days (default 3)')
        parser.add_argument('--sleep', type=float, default=0.3)

    def handle(self, *args, **options):
        now = timezone.now()
        games = Game.objects.filter(
            status=Game.STATUS_FINAL,
            game_datetime__gte=now - timedelta(days=options['days']),
            game_datetime__lte=now,
        ).order_by('game_datetime')

        if not games.exists():
            self.stdout.write("No recently completed games; nothing to do.")
            return

        total_stats = total_athletes = 0
        for game in games:
            try:
                n_stats, n_ath = boxscore.ingest_boxscore(game)
                total_stats += n_stats
                total_athletes += n_ath
                self.stdout.write(f"{game.short_name} ({game.event_id}): {n_stats} stat rows")
            except Exception as e:
                self.stderr.write(self.style.WARNING(
                    f"Boxscore failed for {game.event_id}: {e}"))
            time.sleep(options['sleep'])

        self.stdout.write(self.style.SUCCESS(
            f"Updated {games.count()} games: {total_stats} stat rows, "
            f"{total_athletes} new athletes"))
