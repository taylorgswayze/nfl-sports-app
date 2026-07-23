from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

from django_cron.models import CronJobLog
from nfl.models import Calendar, Game, Team, Athlete, StatTeam
from utils import get_data


class Command(BaseCommand):
    help = (
        "Repair the calendar corruption caused by the old name-keyed upsert: "
        "re-fetch the given season's calendar from ESPN, repoint that season's "
        "games at the correct Calendar rows (separating playoff weeks), set "
        "season_type_id on all games, and remove junk Team rows."
    )

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, default=2025,
                            help='Season whose calendar/games to repair (default: 2025)')

    def handle(self, *args, **options):
        season = options['season']

        # 1. Re-fetch the season's calendar from ESPN. current_schedule() is
        # keyed on (season, season_type_id, week_num), so this recreates the
        # destroyed rows without touching other seasons.
        self.stdout.write(f"Re-fetching {season} calendar from ESPN...")
        get_data.current_schedule(season)
        cal_count = Calendar.objects.filter(season=season).count()
        self.stdout.write(f"Calendar rows for {season}: {cal_count}")

        # 2. Repoint games of that season at the correct calendar rows.
        # Their current week FK (possibly a row rewritten to a later season)
        # still carries the correct (season_type_id, week_num) pair.
        repointed = 0
        unmatched = []
        with transaction.atomic():
            for game in Game.objects.filter(season=season).select_related('week'):
                if game.week is not None:
                    type_id = game.week.season_type_id
                    week_num = game.week.week_num
                else:
                    # No week FK: assume regular season, match by week_num.
                    type_id = game.season_type_id or 2
                    week_num = game.week_num
                target = Calendar.objects.filter(
                    season=season, season_type_id=type_id, week_num=week_num
                ).first()
                if target is None:
                    unmatched.append(game.event_id)
                    continue
                changed = (game.week_id != target.id or
                           game.season_type_id != type_id or
                           game.week_num != week_num)
                if changed:
                    game.week = target
                    game.season_type_id = type_id
                    game.week_num = week_num
                    game.save(update_fields=['week', 'season_type_id', 'week_num'])
                    repointed += 1
        self.stdout.write(f"Repointed {repointed} games to {season} calendar rows "
                          f"({len(unmatched)} unmatched: {unmatched or 'none'})")

        # 3. Junk team cleanup: negative-id Unknown rows and duplicate TBD
        # placeholders. Keep a single TBD row (ESPN placeholder id 31);
        # reassign any references to it, then delete unreferenced junk.
        canonical_tbd, _ = Team.objects.update_or_create(
            team_id=31, defaults={'team_name': 'TBD', 'short_name': 'TBD'})
        junk_ids = [-1, -2, 32]
        deleted, kept = [], []
        for team_id in junk_ids:
            team = Team.objects.filter(team_id=team_id).first()
            if team is None:
                continue
            Athlete.objects.filter(team=team).update(team=canonical_tbd)
            StatTeam.objects.filter(team_id=team).delete()
            game_refs = Game.objects.filter(Q(home_team=team) | Q(away_team=team))
            if game_refs.exists():
                # Never delete a team a game still points at; repoint to TBD.
                game_refs.filter(home_team=team).update(home_team=canonical_tbd)
                game_refs.filter(away_team=team).update(away_team=canonical_tbd)
            team.delete()
            deleted.append(team_id)
        self.stdout.write(f"Deleted junk teams: {deleted or 'none'}")

        # 4. Purge the cron-log spam (keep two weeks).
        cutoff = timezone.now() - timedelta(days=14)
        purged, _ = CronJobLog.objects.filter(end_time__lt=cutoff).delete()
        self.stdout.write(f"Purged {purged} old cron log rows")

        # 5. Verification summary.
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Verification summary ==="))
        for row in (Calendar.objects.values('season', 'season_type_id')
                    .annotate(n=Count('id')).order_by('season', 'season_type_id')):
            self.stdout.write(f"Calendar {row['season']} type {row['season_type_id']}: {row['n']} weeks")
        for row in (Game.objects.values('season', 'season_type_id')
                    .annotate(n=Count('event_id')).order_by('season', 'season_type_id')):
            self.stdout.write(f"Games {row['season']} type {row['season_type_id']}: {row['n']}")

        mismatched = [
            g.event_id for g in Game.objects.select_related('week')
            if g.week is not None and g.week.season != g.season
        ]
        orphans = Game.objects.filter(week__isnull=True).count()
        junk_left = Team.objects.filter(
            Q(team_id__lt=0) | Q(team_name__in=['Unknown', 'TBD'])
        ).exclude(team_id=31).count()
        self.stdout.write(f"Games whose week FK season mismatches game.season: {len(mismatched)}")
        self.stdout.write(f"Games with no week FK: {orphans}")
        self.stdout.write(f"Junk team rows remaining (excluding canonical TBD id 31): {junk_left}")
        self.stdout.write(f"Team rows total: {Team.objects.count()}")

        ok = not mismatched and not unmatched and junk_left == 0
        if ok:
            self.stdout.write(self.style.SUCCESS("Repair complete: verification clean."))
        else:
            self.stdout.write(self.style.ERROR(
                f"Repair finished with issues: mismatched={mismatched}, unmatched={unmatched}, junk_left={junk_left}"))
