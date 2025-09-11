import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from nfl import models

CURRENT_YEAR = int(str(datetime.today() - timedelta(days=140))[:4])

def current_schedule():
    url = f'https://cdn.espn.com/core/nfl/schedule?xhr=1&year={CURRENT_YEAR}'
    calendar = (requests.get(url).json())['content']['calendar']
    for x in calendar:
        if int(x['value']) == 2 or int(x['value']) == 3:
            season_type = x['label']
            for y in x['entries']:
                models.Calendar.objects.update_or_create(
                    name = y['alternateLabel'],
                    defaults = {
                        'details': y['detail'],
                        'week_num': y['value'],
                        'season': CURRENT_YEAR,
                        'season_type_id': x['value'],
                        'season_type_name': season_type,
                        'start_date': y['startDate'],
                        'end_date': y['endDate'],
                    }
                )
