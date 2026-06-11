import json
import re
from datetime import datetime
from pathlib import Path

_CACHE_FILE = Path(__file__).parent.parent / 'betfair_cache.json'

_EMPTY = {"fetched": None, "match_odds": {}, "group_winner": {}, "to_qualify": {}}


def load_betfair_cache():
    if _CACHE_FILE.exists():
        with open(_CACHE_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {k: v.copy() if isinstance(v, dict) else v for k, v in _EMPTY.items()}


def get_inplay_matches(betfair_data):
    from groups import GROUP_MATCHES
    inplay = []
    for matches in GROUP_MATCHES.values():
        for home, away in matches:
            entry = betfair_data["match_odds"].get(f"{home}|{away}")
            if entry and entry.get("inplay"):
                inplay.append((home, away))
    return inplay


def _best_back(book_runner):
    if book_runner and book_runner.ex and book_runner.ex.available_to_back:
        return book_runner.ex.available_to_back[0].price
    return None


def _canonical(name):
    from config import TEAM_ALIASES
    return TEAM_ALIASES.get(name, name)


def _login_no_cert(username, password, app_key):
    """Authenticate via Betfair's non-certificate login endpoint, return session token."""
    import requests as _req
    resp = _req.post(
        'https://identitysso.betfair.com/api/login',
        data={'username': username, 'password': password},
        headers={
            'X-Application': app_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get('status') != 'SUCCESS':
        raise RuntimeError(f"Betfair login failed: {data.get('error', 'unknown')}")
    return data['token']


def fetch_betfair(groups_filter=None, fetch_match_odds=True):
    try:
        import betfairlightweight
        from betfairlightweight import filters as bf_filters
    except ImportError:
        print("  Warning: betfairlightweight not installed.")
        return load_betfair_cache()

    try:
        from config import BETFAIR_APP_KEY, BETFAIR_USERNAME, BETFAIR_PASSWORD
        from groups import GROUPS, GROUP_MATCHES

        client = betfairlightweight.APIClient(
            BETFAIR_USERNAME, BETFAIR_PASSWORD, app_key=BETFAIR_APP_KEY
        )
        client.session_token = _login_no_cert(BETFAIR_USERNAME, BETFAIR_PASSWORD, BETFAIR_APP_KEY)

        # Step 1: resolve WC2026 competition IDs to narrow the catalogue request
        competitions = client.betting.list_competitions(
            filter=bf_filters.market_filter(event_type_ids=['1'])
        )
        comp_ids = [
            c.competition.id for c in competitions
            if c.competition and 'World Cup' in (c.competition.name or '')
        ]

        if not comp_ids:
            print("  Warning: no World Cup competition found on Betfair.")
            return load_betfair_cache()

        # Step 2: fetch only markets in those competitions.
        # Group winner/qualify use per-group type codes: GROUP_A_WINNER_SGX,
        # GROUP_A_TO_QUALIFY, etc. — generate all 24 alongside MATCH_ODDS.
        _gl = 'ABCDEFGHIJKL'
        group_market_types = (
            (['MATCH_ODDS'] if fetch_match_odds else []) +
            ['WINNER', 'TO_QUALIFY'] +
            [f'GROUP_{l}_WINNER'     for l in _gl] +
            [f'GROUP_{l}_WINNER_SGX' for l in _gl] +
            [f'GROUP_{l}_TO_QUALIFY' for l in _gl]
        )

        wc_markets = client.betting.list_market_catalogue(
            filter=bf_filters.market_filter(
                event_type_ids=['1'],
                competition_ids=comp_ids,
                market_type_codes=group_market_types,
            ),
            market_projection=[
                'COMPETITION', 'EVENT', 'MARKET_DESCRIPTION',
                'MARKET_START_TIME', 'RUNNER_DESCRIPTION',
            ],
            max_results=1000,
        )

        if not wc_markets:
            print("  Warning: no World Cup 2026 markets found on Betfair.")
            return load_betfair_cache()

        # Fetch books in batches (Betfair limit: 40 markets with EX_BEST_OFFERS)
        books = {}
        ids = [m.market_id for m in wc_markets]
        for i in range(0, len(ids), 40):
            batch = client.betting.list_market_book(
                market_ids=ids[i:i + 40],
                price_projection=bf_filters.price_projection(
                    price_data=['EX_BEST_OFFERS'],
                    virtualise=False,
                ),
            )
            books.update({b.market_id: b for b in batch})

        team_to_group = {t: g for g, teams in GROUPS.items() for t in teams}

        data = {
            "fetched": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            "match_odds": {},
            "group_winner": {},
            "to_qualify": {},
        }
        mo_count = gw_count = tq_count = 0

        for market in wc_markets:
            book = books.get(market.market_id)
            if not book:
                continue

            mtype = market.description.market_type if market.description else None
            if not mtype:
                continue

            book_runners = {r.selection_id: r for r in book.runners}

            if mtype == 'MATCH_ODDS' and not fetch_match_odds:
                continue

            if mtype == 'MATCH_ODDS':
                cat_sorted = sorted(
                    market.runners or [],
                    key=lambda r: r.sort_priority or 99,
                )
                team_runners = [r for r in cat_sorted if r.runner_name.lower() != 'the draw']
                draw_runners = [r for r in cat_sorted if r.runner_name.lower() == 'the draw']

                if len(team_runners) < 2 or not draw_runners:
                    continue

                home_name = _canonical(team_runners[0].runner_name)
                away_name = _canonical(team_runners[1].runner_name)

                home_grp = team_to_group.get(home_name)
                away_grp = team_to_group.get(away_name)
                if not home_grp or home_grp != away_grp:
                    continue

                if groups_filter and home_grp not in groups_filter:
                    continue

                inplay = bool(getattr(book, 'inplay', False) or book.status == 'IN_PLAY')

                data["match_odds"][f"{home_name}|{away_name}"] = {
                    "home":   _best_back(book_runners.get(team_runners[0].selection_id)),
                    "draw":   _best_back(book_runners.get(draw_runners[0].selection_id)),
                    "away":   _best_back(book_runners.get(team_runners[1].selection_id)),
                    "inplay": inplay,
                }
                mo_count += 1

            else:
                # Group winner: GROUP_A_WINNER_SGX  /  generic WINNER with group name
                # To qualify:   GROUP_A_TO_QUALIFY  /  generic TO_QUALIFY with group name
                type_grp = re.match(r'^GROUP_([A-L])_(WINNER|TO_QUALIFY)', mtype)
                if type_grp:
                    grp       = type_grp.group(1).upper()
                    is_winner = type_grp.group(2) == 'WINNER'
                elif mtype in ('WINNER', 'TO_QUALIFY'):
                    name_grp = re.search(
                        r'\bGroup\s+([A-L])\b', market.market_name or '', re.IGNORECASE
                    )
                    if not name_grp:
                        continue
                    grp       = name_grp.group(1).upper()
                    is_winner = mtype == 'WINNER'
                else:
                    continue

                target = data["group_winner"] if is_winner else data["to_qualify"]
                target.setdefault(grp, {})

                for cat_runner in (market.runners or []):
                    name  = _canonical(cat_runner.runner_name)
                    price = _best_back(book_runners.get(cat_runner.selection_id))
                    if price:
                        target[grp][name] = price

                if is_winner:
                    gw_count += 1
                else:
                    tq_count += 1

        parts = ([f"{mo_count} match odds"] if fetch_match_odds else [])
        parts += [f"{gw_count} group winner", f"{tq_count} to qualify"]
        print(f"  Betfair: {' / '.join(parts)} markets")

        with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return data

    except Exception as exc:
        print(f"  Warning: Betfair fetch failed ({exc}). Falling back to cache.")
        return load_betfair_cache()
