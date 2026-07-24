import time

from django.core.management.base import BaseCommand, CommandError

from nfl.models import Calendar, Game, Outcome, Team, Athlete, StatTeam, GameStatistic
from utils import get_data, boxscore
import utils.helpers as h

SCOREBOARD_URL = ('https://site.api.espn.com/apis/site/v2/sports/football/nfl/'
                  'scoreboard?dates={season}&seasontype={type_id}&week={week}')

# Pro Bowl (postseason week 4) is not a real game: its "teams" are the AFC/NFC
# all-star squads, which do not exist in the Team table.
SKIP_WEEKS = {(3, 4)}


def parse_types(value):
    return [int(t) for t in value.split(',') if t.strip()]


def parse_weeks(value):
    if not value:
        return None
    if '-' in value:
        a, b = value.split('-', 1)
        return list(range(int(a), int(b) + 1))
    return [int(value)]


class Command(BaseCommand):
    help = ("Backfill one NFL season from ESPN: calendar -> teams -> games with "
            "results -> closing odds -> team season stats/records -> per-game "
            "player boxscores (GameStatistic with real stat names).")

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, required=True)
        parser.add_argument('--types', type=str, default='2,3',
                            help='Season types, comma separated (2=regular, 3=postseason)')
        parser.add_argument('--weeks', type=str, default=None,
                            help='Week range a-b or single week (per season type)')
        parser.add_argument('--skip-game-stats', action='store_true',
                            help='Skip the per-game boxscore/GameStatistic pass')
        parser.add_argument('--sleep', type=float, default=0.3,
                            help='Seconds to sleep between per-event API calls')
        parser.add_argument('--dry-run', action='store_true',
                            help='Print planned request counts; write nothing')

    def handle(self, *args, **options):
        season = options['season']
        types = parse_types(options['types'])
        weeks_filter = parse_weeks(options['weeks'])
        sleep_s = options['sleep']
        skip_game_stats = options['skip_game_stats']

        if options['dry_run']:
            return self.dry_run(season, types, weeks_filter, skip_game_stats)

        before = self.row_counts(season)

        # 1. Calendar
        self.stdout.write(f"[{season}] Fetching calendar...")
        get_data.current_schedule(season)

        # 2. Teams (season-scoped fetch keeps names/abbreviations current)
        self.stdout.write(f"[{season}] Fetching teams...")
        try:
            get_data.get_teams_from_espn(season)
        except Exception as e:
            self.stderr.write(self.style.WARNING(f"Team fetch failed, continuing: {e}"))

        weeks = Calendar.objects.filter(season=season, season_type_id__in=types)
        if weeks_filter:
            weeks = weeks.filter(week_num__in=weeks_filter)
        weeks = weeks.order_by('season_type_id', 'week_num')

        # 3. Games + results via the weekly scoreboard (one call per week,
        # includes final scores and status).
        for week in weeks:
            if (week.season_type_id, week.week_num) in SKIP_WEEKS:
                self.stdout.write(f"[{season}] Skipping {week.name} (Pro Bowl)")
                continue
            try:
                n = self.ingest_week_scoreboard(season, week)
                self.stdout.write(f"[{season}] {week.season_type_name} {week.name}: {n} games")
            except Exception as e:
                self.stderr.write(self.style.WARNING(
                    f"[{season}] scoreboard failed for {week.name}: {e}"))
            time.sleep(sleep_s)

        season_games = Game.objects.filter(season=season).order_by('game_datetime')
        if weeks_filter:
            season_games = season_games.filter(
                season_type_id__in=types, week_num__in=weeks_filter)
        else:
            season_games = season_games.filter(season_type_id__in=types)

        # 4. Closing odds (tolerate 404/missing — history only goes back so far)
        self.stdout.write(f"[{season}] Fetching closing odds for {season_games.count()} games...")
        for game in season_games:
            try:
                get_data.single_game_odds(game)
            except Exception as e:
                logger_msg = f"[{season}] odds failed for {game.event_id}: {e}"
                self.stderr.write(self.style.WARNING(logger_msg))
            time.sleep(sleep_s)

        # 5. Team season stats + records into season-keyed StatTeam
        self.stdout.write(f"[{season}] Fetching team season stats and records...")
        for team in Team.objects.exclude(team_name='TBD'):
            try:
                get_data.team_stats(team.team_id, season)
                self.backfill_team_record(team, season)
            except Exception as e:
                self.stderr.write(self.style.WARNING(
                    f"[{season}] team stats failed for {team.short_name}: {e}"))
            time.sleep(sleep_s)

        # 6. Per-game boxscores -> GameStatistic + historical athletes
        if not skip_game_stats:
            finals = season_games.filter(status=Game.STATUS_FINAL)
            self.stdout.write(f"[{season}] Fetching boxscores for {finals.count()} completed games...")
            total_stats = total_athletes = 0
            for i, game in enumerate(finals, 1):
                try:
                    n_stats, n_ath = boxscore.ingest_boxscore(game)
                    total_stats += n_stats
                    total_athletes += n_ath
                    if i % 25 == 0:
                        self.stdout.write(f"[{season}]   {i} boxscores done "
                                          f"({total_stats} stat rows, {total_athletes} new athletes)")
                except Exception as e:
                    self.stderr.write(self.style.WARNING(
                        f"[{season}] boxscore failed for {game.event_id} ({game.short_name}): {e}"))
                time.sleep(sleep_s)
            self.stdout.write(f"[{season}] Boxscores: {total_stats} stat rows, "
                              f"{total_athletes} new athletes")

        after = self.row_counts(season)
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {season} backfill summary ==="))
        for key in after:
            self.stdout.write(f"{key}: {before[key]} -> {after[key]} (+{after[key] - before[key]})")
        self.stdout.write(self.style.SUCCESS(f"Season {season} backfill complete."))

    # -- helpers ----------------------------------------------------------

    def ingest_week_scoreboard(self, season, week):
        url = SCOREBOARD_URL.format(season=season, type_id=week.season_type_id,
                                    week=week.week_num)
        data = get_data.session.get(url, timeout=30).json()
        count = 0
        for event in data.get('events', []):
            try:
                comp = event['competitions'][0]
                competitors = comp['competitors']
                home = next(c for c in competitors if c['homeAway'] == 'home')
                away = next(c for c in competitors if c['homeAway'] == 'away')
                status_type = comp.get('status', {}).get('type', {})
                Game.objects.update_or_create(
                    event_id=int(event['id']),
                    defaults={
                        'short_name': event.get('shortName'),
                        'game_datetime': event['date'],
                        'season': season,
                        'season_type_id': week.season_type_id,
                        'week_num': week.week_num,
                        'week': week,
                        'home_team': get_data.get_team_for_game(home['team']['id']),
                        'away_team': get_data.get_team_for_game(away['team']['id']),
                        'home_score': int(home['score']) if home.get('score') not in (None, '') else None,
                        'away_score': int(away['score']) if away.get('score') not in (None, '') else None,
                        'status': get_data.map_game_status(
                            status_type.get('state'), status_type.get('completed', False)),
                    })
                count += 1
            except Exception as e:
                self.stderr.write(self.style.WARNING(
                    f"[{season}] event {event.get('id')} failed: {e}"))
        return count

    def backfill_team_record(self, team, season):
        """Store a team's season record in season-keyed StatTeam rows
        (category 'record'), and mirror onto Team.record only for the
        current season."""
        url = (f'{get_data.BASE_URL}/nfl/seasons/{season}/types/2/teams/'
               f'{team.team_id}/record')
        data = get_data.session.get(url, timeout=30).json()
        items = data.get('items') or []
        if not items:
            return
        overall = items[0]
        display = overall.get('displayValue', '-')
        StatTeam.objects.update_or_create(
            team_id=team, season=season, category='record', stat_name='overall',
            defaults={'value': None, 'display_rank': None,
                      'description': display, 'rank': None})
        for stat in overall.get('stats', []):
            if stat.get('name') in ('wins', 'losses', 'ties', 'winPercent',
                                    'pointsFor', 'pointsAgainst'):
                StatTeam.objects.update_or_create(
                    team_id=team, season=season, category='record',
                    stat_name=stat['name'],
                    defaults={'value': stat.get('value'),
                              'description': display})
        if season == h.current_season():
            team.record = display
            team.save(update_fields=['record'])

    def row_counts(self, season):
        return {
            f'Calendar[{season}]': Calendar.objects.filter(season=season).count(),
            f'Game[{season}]': Game.objects.filter(season=season).count(),
            f'Game[{season}] with scores': Game.objects.filter(
                season=season, home_score__isnull=False).count(),
            f'Outcome[{season}]': Outcome.objects.filter(
                event_id__season=season).count(),
            f'StatTeam[{season}]': StatTeam.objects.filter(season=season).count(),
            f'GameStatistic[{season} events]': GameStatistic.objects.filter(
                event_id__in=[str(e) for e in Game.objects.filter(
                    season=season).values_list('event_id', flat=True)]).count(),
            'Athlete[total]': Athlete.objects.count(),
        }

    def dry_run(self, season, types, weeks_filter, skip_game_stats):
        """Print planned request counts without writing to the database."""
        url = f'https://cdn.espn.com/core/nfl/schedule?xhr=1&year={season}'
        calendar = (get_data.session.get(url, timeout=30).json())['content']['calendar']
        weeks = []
        for block in calendar:
            if int(block['value']) not in types:
                continue
            for entry in block.get('entries', []):
                wk = (int(block['value']), int(entry['value']))
                if wk in SKIP_WEEKS:
                    continue
                if weeks_filter and wk[1] not in weeks_filter:
                    continue
                weeks.append(wk)

        n_events = 0
        for type_id, week_num in weeks:
            u = (f'{get_data.BASE_URL}/nfl/seasons/{season}/types/{type_id}/'
                 f'weeks/{week_num}/events')
            try:
                n_events += get_data.session.get(u, timeout=30).json().get('count', 0)
            except Exception:
                n_events += 16  # estimate
            time.sleep(0.1)

        n_teams = 32
        planned = {
            'calendar': 1,
            'team list + details': 1 + n_teams,
            'weekly scoreboards': len(weeks),
            'odds (1/event)': n_events,
            'team stats + records': 2 * n_teams,
            'boxscores (1/event)': 0 if skip_game_stats else n_events,
        }
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== DRY RUN {season} (types {types}, {len(weeks)} weeks, {n_events} events) ==="))
        total = 0
        for k, v in planned.items():
            self.stdout.write(f"{k}: {v}")
            total += v
        self.stdout.write(f"TOTAL planned requests: ~{total}")
        self.stdout.write("No database writes performed.")
