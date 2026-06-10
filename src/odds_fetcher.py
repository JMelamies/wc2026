import json
import requests
from datetime import datetime
from pathlib import Path
from config import ODDS_API_KEY, TEAM_ALIASES

API_URL = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/"
CACHE_FILE = Path(__file__).parent.parent / 'odds_cache.json'


def normalize(name):
    return TEAM_ALIASES.get(name, name)


def fetch_odds():
    """
    Fetch odds from The Odds API, save to odds_cache.json, and return
    (odds_dict, credits_info) where credits_info is a dict with 'used' and 'remaining'.
    """
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': 'eu',
        'markets': 'h2h',
        'oddsFormat': 'decimal',
    }

    resp = requests.get(API_URL, params=params, timeout=15)
    resp.raise_for_status()
    credits_info = {
        'this_request': resp.headers.get('x-requests-last', '?'),
        'used_total':   resp.headers.get('x-requests-used', '?'),
        'remaining':    resp.headers.get('x-requests-remaining', '?'),
    }
    events = resp.json()

    odds_dict = {}
    schedule = {}  # {(home, away): commence_time_iso}

    for event in events:
        raw_home = event['home_team']
        raw_away = event['away_team']
        home = normalize(raw_home)
        away = normalize(raw_away)

        schedule[(home, away)] = event.get('commence_time', '')

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

    _save_cache(odds_dict, schedule)
    return odds_dict, credits_info


def load_cached_odds():
    """
    Load odds from odds_cache.json.
    Returns (odds_dict, fetched_timestamp) or (None, None) if no cache exists.
    """
    if not CACHE_FILE.exists():
        return None, None
    with open(CACHE_FILE, encoding='utf-8') as f:
        data = json.load(f)
    odds_dict = {
        tuple(key.split('|', 1)): tuple(probs)
        for key, probs in data['odds'].items()
    }
    return odds_dict, data.get('fetched', 'unknown')


def load_schedule():
    """
    Load match schedule from odds_cache.json.
    Returns dict: {(home, away): commence_time_iso_str}
    """
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE, encoding='utf-8') as f:
        data = json.load(f)
    return {
        tuple(key.split('|', 1)): dt
        for key, dt in data.get('schedule', {}).items()
    }


def _save_cache(odds_dict, schedule):
    payload = {
        'fetched': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'odds': {
            f"{home}|{away}": list(probs)
            for (home, away), probs in odds_dict.items()
        },
        'schedule': {
            f"{home}|{away}": dt
            for (home, away), dt in schedule.items()
        },
    }
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
