"""Per-game boxscore ingestion from ESPN's summary API.

Fills GameStatistic with REAL stat names (the summary payload labels every
column via ``keys``) and creates Athlete rows for players not on a current
roster (historical players), with their then-team when derivable.

Shared by the backfill commands and the recurring player-stats cron job.
"""
import logging

from nfl import models
from utils import get_data

logger = logging.getLogger(__name__)

SUMMARY_URL = ('https://site.api.espn.com/apis/site/v2/sports/football/nfl/'
               'summary?event={event_id}')


def split_stat(key, value):
    """Yield (stat_name, display_value) pairs for one boxscore column.

    ESPN uses compound columns such as key 'completions/passingAttempts'
    with value '21/34' or 'sacks-sackYardsLost' with value '2-13'. Those are
    split into their real component stats; anything unsplittable is stored
    under the compound key as-is.
    """
    for sep in ('/', '-'):
        if sep in key:
            names = key.split(sep)
            parts = str(value).split(sep)
            if len(names) == len(parts):
                return list(zip(names, parts))
            return [(key, str(value))]
    return [(key, str(value))]


def to_number(display_value):
    try:
        return float(str(display_value).replace(',', ''))
    except (ValueError, TypeError):
        return None


def get_or_create_athlete(payload, team):
    """Return the Athlete for a boxscore entry, creating a minimal row
    (with their then-team) for players we have never seen."""
    athlete_id = int(payload['id'])
    athlete = models.Athlete.objects.filter(pk=athlete_id).first()
    if athlete is not None:
        return athlete, False
    jersey = payload.get('jersey')
    try:
        jersey = int(jersey)
    except (ValueError, TypeError):
        jersey = None
    display_name = payload.get('displayName')
    first = payload.get('firstName')
    last = payload.get('lastName')
    if (not first or not last) and display_name and ' ' in display_name:
        first, last = display_name.split(' ', 1)
    athlete = models.Athlete.objects.create(
        athlete_id=athlete_id,
        display_name=display_name,
        first_name=first,
        last_name=last,
        jersey=jersey,
        team=team,
    )
    return athlete, True


def ingest_boxscore(game):
    """Fetch and store the full player boxscore for one game.

    Returns (stat_rows_written, athletes_created). Raises on network/parse
    failure so callers can decide whether to continue.
    """
    url = SUMMARY_URL.format(event_id=game.event_id)
    logger.info(f"Fetching boxscore from {url}")
    data = get_data.session.get(url, timeout=30).json()
    team_blocks = (data.get('boxscore') or {}).get('players') or []

    stats_written = 0
    athletes_created = 0

    for block in team_blocks:
        team_id = int(block['team']['id'])
        team = models.Team.objects.filter(pk=team_id).first()
        if game.home_team_id == team_id:
            opponent = game.away_team.short_name
        elif game.away_team_id == team_id:
            opponent = game.home_team.short_name
        else:
            opponent = None

        for category in block.get('statistics', []):
            cat_name = category.get('name', 'general')
            keys = category.get('keys') or []
            for entry in category.get('athletes', []):
                stats = entry.get('stats') or []
                if not stats or 'athlete' not in entry:
                    continue
                athlete, created = get_or_create_athlete(entry['athlete'], team)
                athletes_created += int(created)
                for key, value in zip(keys, stats):
                    for stat_name, display in split_stat(key, value):
                        models.GameStatistic.objects.update_or_create(
                            athlete=athlete,
                            event_id=str(game.event_id),
                            category_name=cat_name,
                            stat_name=stat_name,
                            defaults={
                                'stat_value': to_number(display),
                                'stat_display_value': display,
                                'game_date': game.game_datetime.date(),
                                'opponent': opponent,
                            }
                        )
                        stats_written += 1

    return stats_written, athletes_created
