import requests
from config import ODDS_API_KEY, TEAM_ALIASES

API_URL = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/"


def normalize(name):
    return TEAM_ALIASES.get(name, name)


def fetch_odds():
    """
    Returns dict: {(home_team, away_team): (p_home, p_draw, p_away)}
    Keys use canonical team names matching groups.py.
    """
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': 'eu',
        'markets': 'h2h',
        'oddsFormat': 'decimal',
    }

    resp = requests.get(API_URL, params=params, timeout=15)
    resp.raise_for_status()
    events = resp.json()

    odds_dict = {}
    for event in events:
        raw_home = event['home_team']
        raw_away = event['away_team']
        home = normalize(raw_home)
        away = normalize(raw_away)

        probs = None
        for bookmaker in event.get('bookmakers', []):
            for market in bookmaker.get('markets', []):
                if market['key'] == 'h2h':
                    prices = {o['name']: o['price'] for o in market['outcomes']}
                    ph_raw = prices.get(raw_home, 0)
                    pd_raw = prices.get('Draw', 0)
                    pa_raw = prices.get(raw_away, 0)
                    if ph_raw > 0 and pd_raw > 0 and pa_raw > 0:
                        ph = 1.0 / ph_raw
                        pd = 1.0 / pd_raw
                        pa = 1.0 / pa_raw
                        total = ph + pd + pa
                        probs = (ph / total, pd / total, pa / total)
                    break
            if probs:
                break

        if probs:
            odds_dict[(home, away)] = probs

    return odds_dict
