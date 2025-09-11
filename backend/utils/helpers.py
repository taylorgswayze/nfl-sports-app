import re
from nfl import models
from datetime import datetime, timedelta
from django.utils.timezone import now

CURRENT_YEAR = (datetime.now() - timedelta(days=150)).year
NOW = now()


def current_week():
    try:
        current_week = models.Calendar.objects.filter(
            season=CURRENT_YEAR,
            start_date__lte=NOW,
            end_date__gte=NOW
        )[0]

        # Output the result
        print(f"Current schedule week is {current_week.name} of the {current_week.season_type_name}")
        return current_week

    except IndexError:
        print("No current week found for the specified season and date range.")



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
