import re
from nfl import models
from datetime import timedelta
from django.utils.timezone import now


def get_espn_api_url(endpoint):
    return f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/{endpoint}"


def current_season():
    """Return the current NFL season year, computed AT CALL TIME.

    Prefers the Calendar table (a week covering "now", or the most recently
    started week). Falls back to date math: a season is labeled by its
    starting year and we treat June 1 as the rollover point, so e.g.
    Feb 2026 still belongs to the 2025 season.
    """
    now_dt = now()
    week = models.Calendar.objects.filter(
        start_date__lte=now_dt, end_date__gte=now_dt, season__isnull=False
    ).order_by('-start_date').first()
    if week:
        return week.season
    # Date-math fallback (also decides between seasons when the calendar
    # only covers other years): season year flips on ~June 1.
    return (now_dt - timedelta(days=151)).year


def current_week(season=None):
    """Return the Calendar row for the current week, computed AT CALL TIME."""
    season = season or current_season()
    # Add a 2-day offset to handle week turnover
    now_offset = now() + timedelta(days=2)

    try:
        # Try to find the current week with the offset
        return models.Calendar.objects.filter(
            season=season,
            start_date__lte=now_offset,
            end_date__gte=now_offset
        ).latest('start_date')

    except models.Calendar.DoesNotExist:
        # Off-season: fall back to the last week of the season that most
        # recently started, else the first upcoming week.
        last_started = models.Calendar.objects.filter(
            start_date__lte=now_offset
        ).order_by('-start_date').first()
        if last_started:
            return last_started
        return models.Calendar.objects.order_by('start_date').first()



def extract_int(string, kw):
    # Adjust the pattern to match optional negative integers
    pattern = rf'{kw}/(-?\d+)'  # -? matches an optional negative sign
    match = re.search(pattern, string)

    if match:
        return int(match.group(1))  # Convert matched group to integer
    else:
        raise ValueError(f"No match found for keyword '{kw}' in string: {string}")

def get_team_logo(team_id):
    team_logos = {
        1: 'nfl-atlanta-falcons-team-logo-2-300x300.png',  # Atlanta Falcons
        2: 'nfl-buffalo-bills-team-logo-2-300x300.png',  # Buffalo Bills
        3: 'nfl-chicago-bears-team-logo-2-300x300.png',  # Chicago Bears
        4: 'nfl-cincinnati-bengals-team-logo-300x300.png',  # Cincinnati Bengals
        5: 'nfl-cleveland-browns-team-logo-2-300x300.png',  # Cleveland Browns
        6: 'nfl-dallas-cowboys-team-logo-2-300x300.png',  # Dallas Cowboys
        7: 'nfl-denver-broncos-team-logo-2-300x300.png',  # Denver Broncos
        8: 'nfl-detroit-lions-team-logo-2-300x300.png',  # Detroit Lions
        9: 'nfl-green-bay-packers-team-logo-2-300x300.png',  # Green Bay Packers
        10: 'nfl-tennessee-titans-team-logo-2-300x300.png',  # Tennessee Titans
        11: 'nfl-indianapolis-colts-team-logo-2-300x300.png',  # Indianapolis Colts
        12: 'nfl-kansas-city-chiefs-team-logo-2-300x300.png',  # Kansas City Chiefs
        13: 'nfl-oakland-raiders-team-logo-300x300.png',  # Las Vegas Raiders (formerly Oakland)
        14: 'los-angeles-rams-2020-logo-300x300.png',  # Los Angeles Rams
        15: 'Miami-Dolphins-Logo-300x300.png',  # Miami Dolphins
        16: 'nfl-minnesota-vikings-team-logo-2-300x300.png',  # Minnesota Vikings
        17: 'nfl-new-england-patriots-team-logo-2-300x300.png',  # New England Patriots
        18: 'nfl-new-orleans-saints-team-logo-2-300x300.png',  # New Orleans Saints
        19: 'nfl-new-york-giants-team-logo-2-300x300.png',  # New York Giants
        20: 'New-York-Jets-logo-2024-300x300.png',  # New York Jets
        21: 'nfl-philadelphia-eagles-team-logo-2-300x300.png',  # Philadelphia Eagles
        22: 'nfl-arizona-cardinals-team-logo-2-300x300.png',  # Arizona Cardinals
        23: 'nfl-pittsburgh-steelers-team-logo-2-300x300.png',  # Pittsburgh Steelers
        24: 'nfl-los-angeles-chargers-team-logo-2-300x300.png',  # Los Angeles Chargers
        25: 'nfl-san-francisco-49ers-team-logo-2-300x300.png',  # San Francisco 49ers
        26: 'nfl-seattle-seahawks-team-logo-2-300x300.png',  # Seattle Seahawks
        27: 'tampa-bay-buccaneers-2020-logo-300x300.png',  # Tampa Bay Buccaneers
        28: 'washington-commanders-logo-300x300.png',  # Washington Commanders
        29: 'nfl-carolina-panthers-team-logo-2-300x300.png',  # Carolina Panthers
        30: 'nfl-jacksonville-jaguars-team-logo-2-300x300.png',  # Jacksonville Jaguars
        33: 'nfl-baltimore-ravens-team-logo-2-300x300.png',  # Baltimore Ravens
        34: 'nfl-houston-texans-team-logo-2-300x300.png'  # Houston Texans
    }
    return team_logos.get(team_id)