import json
import os
import requests
from pathlib import Path
from config import ODDS_API_KEY, TEAM_ALIASES

SCORES_URL = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/scores/"
CACHE_FILE = Path(__file__).parent.parent / 'results_cache.json'

OUTCOME_PROBS = {
    'home': (1.0, 0.0, 0.0),
    'draw': (0.0, 1.0, 0.0),
    'away': (0.0, 0.0, 1.0),
}


def _normalize(name):
    return TEAM_ALIASES.get(name, name)


def _load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def fetch_results():
    """
    Returns (completed, live_scores):
    - completed:   {(home, away): (p_home, p_draw, p_away)}  certainty values for finished matches
    - live_scores: {(home, away): (score_home, score_away)}  current score for in-progress matches

    Merges fresh API data (last 3 days) into results_cache.json so completed matches
    older than the API window are not lost between runs.
    """
    cache = _load_cache()  # keyed as "HomeTeam|AwayTeam" -> 'home'/'draw'/'away'
    live_scores = {}

    try:
        params = {'apiKey': ODDS_API_KEY, 'daysFrom': 3}
        resp = requests.get(SCORES_URL, params=params, timeout=15)
        resp.raise_for_status()
        events = resp.json()

        new_count = 0
        for event in events:
            raw_home = event['home_team']
            raw_away = event['away_team']
            home = _normalize(raw_home)
            away = _normalize(raw_away)
            scores_data = event.get('scores') or []
            scores = {s['name']: int(s['score']) for s in scores_data}

            if event.get('completed'):
                hs  = scores.get(raw_home, 0)
                as_ = scores.get(raw_away, 0)
                outcome = 'home' if hs > as_ else ('draw' if hs == as_ else 'away')
                key = f"{home}|{away}"
                if cache.get(key) != outcome:
                    cache[key] = outcome
                    new_count += 1
            elif scores_data:
                sh = scores.get(raw_home)
                sa = scores.get(raw_away)
                if sh is not None and sa is not None:
                    live_scores[(home, away)] = (sh, sa)

        _save_cache(cache)
        live_str = f", {len(live_scores)} live" if live_scores else ""
        print(f"  Scores API: {new_count} new result(s) cached "
              f"({len(cache)} total in results_cache.json{live_str}).")

    except Exception as exc:
        print(f"  Warning: could not fetch scores ({exc}). Using cached results only.")

    completed = {
        tuple(key.split('|', 1)): OUTCOME_PROBS[outcome]
        for key, outcome in cache.items()
    }
    return completed, live_scores
