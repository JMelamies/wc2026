import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

ODDS_API_KEY = os.getenv('ODDS_API_KEY')

# Map Odds API team name variants → canonical names used in groups.py
TEAM_ALIASES = {
    'Czech Republic':                   'Czechia',
    'Bosnia and Herzegovina':           'Bosnia-Herzegovina',
    'Bosnia & Herzegovina':             'Bosnia-Herzegovina',
    'Turkey':                           'Türkiye',
    'Democratic Republic of Congo':     'DR Congo',
    'Congo DR':                         'DR Congo',
    "Cote d'Ivoire":                    'Ivory Coast',
    "Côte d'Ivoire":                    'Ivory Coast',
    'Cabo Verde':                       'Cape Verde',
    'Korea Republic':                   'South Korea',
    'Republic of Korea':                'South Korea',
    'USA':                              'United States',
    'United States of America':         'United States',
    'Curacao':                          'Curaçao',
    'DR Congo':                         'DR Congo',
    'Ivory Coast':                      'Ivory Coast',
    'Cape Verde':                       'Cape Verde',
    'South Korea':                      'South Korea',
    'United States':                    'United States',
    'Curaçao':                          'Curaçao',
    'Türkiye':                          'Türkiye',
    'Czechia':                          'Czechia',
    'Bosnia-Herzegovina':               'Bosnia-Herzegovina',
}
