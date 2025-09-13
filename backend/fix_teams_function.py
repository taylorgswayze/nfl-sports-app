import utils.get_data as gd

# Replace the problematic function
def get_teams_from_espn_fixed(season=None):
    import requests
    from nfl import models
    import utils.helpers as h
    from django.http import HttpResponse
    
    if season:
        season = season
    else:
        season = gd.CURRENT_YEAR
    
    # Create TBD teams
    [models.Team.objects.update_or_create(team_id=x, defaults={'team_name': 'TBD', 'short_name': 'TBD'}) for x in [31,32]]
    
    # Get teams list
    data = requests.get(f'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{season}/teams?limit=50').json()
    
    for x in data['items']:
        try:
            team_id = h.extract_int(x['$ref'], 'teams')
            team_response = requests.get(f'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{season}/teams/{team_id}')
            
            if team_response.status_code == 200:
                team = team_response.json()
                team_name = team.get('displayName', 'Unknown Team')
                short_name = team.get('abbreviation', 'UNK')
                team_obj, created = models.Team.objects.update_or_create(
                    team_id=team_id, 
                    defaults={'team_name': team_name, 'short_name': short_name}
                )
                print(f'{team_obj}: {created}')
            else:
                print(f'Failed to get team {team_id}: {team_response.status_code}')
                
        except Exception as e:
            print(f'Error processing team: {e}')
            continue
    
    return HttpResponse('Teams updated')

# Test the fixed function
if __name__ == '__main__':
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sports.settings')
    django.setup()
    
    result = get_teams_from_espn_fixed()
    print('Function completed successfully')
