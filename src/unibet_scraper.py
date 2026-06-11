import argparse
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

_CACHE_FILE = Path(__file__).parent.parent / 'unibet_cache.json'
_DOCS_CACHE  = Path(__file__).parent.parent / 'docs' / 'data' / 'unibet_cache.json'

GROUP_URLS = {
    'A': 'https://fi.unibet.com/betting/sports/event/1025831732',
    'B': 'https://fi.unibet.com/betting/sports/event/1025831733',
    'C': 'https://fi.unibet.com/betting/sports/event/1025831734',
    'F': 'https://fi.unibet.com/betting/sports/event/1025831735',
    'G': 'https://fi.unibet.com/betting/sports/event/1025831736',
    'D': 'https://fi.unibet.com/betting/sports/event/1025831737',
    'E': 'https://fi.unibet.com/betting/sports/event/1025831738',
    'J': 'https://fi.unibet.com/betting/sports/event/1025831739',
    'I': 'https://fi.unibet.com/betting/sports/event/1025831740',
    'K': 'https://fi.unibet.com/betting/sports/event/1025831741',
    'L': 'https://fi.unibet.com/betting/sports/event/1025831742',
    'H': 'https://fi.unibet.com/betting/sports/event/1025831743',
}

FINNISH_NAMES = {
    # Group A
    'Meksiko':                          'Mexico',
    'Etelä-Korea':                      'South Korea',
    'Etelä-Afrikka':                    'South Africa',
    'Tšekki':                           'Czechia',
    # Group B
    'Kanada':                           'Canada',
    'Sveitsi':                          'Switzerland',
    'Qatar':                            'Qatar',
    'Bosnia-Hertsegovina':              'Bosnia-Herzegovina',
    'Bosnia & Hertsegovina':            'Bosnia-Herzegovina',
    'Bosnia ja Hertsegovina':           'Bosnia-Herzegovina',
    # Group C
    'Brasilia':                         'Brazil',
    'Marokko':                          'Morocco',
    'Haiti':                            'Haiti',
    'Skotlanti':                        'Scotland',
    # Group D
    'Yhdysvallat':                      'United States',
    'USA':                              'United States',
    'Paraguay':                         'Paraguay',
    'Australia':                        'Australia',
    'Turkki':                           'Türkiye',
    'Türkiye':                          'Türkiye',
    # Group E
    'Saksa':                            'Germany',
    'Curaçao':                          'Curaçao',
    'Curacao':                          'Curaçao',
    'Norsunluurannikko':                'Ivory Coast',
    "Côte d'Ivoire":                    'Ivory Coast',
    'Ecuador':                          'Ecuador',
    # Group F
    'Alankomaat':                       'Netherlands',
    'Hollanti':                         'Netherlands',
    'Japani':                           'Japan',
    'Ruotsi':                           'Sweden',
    'Tunisia':                          'Tunisia',
    # Group G
    'Belgia':                           'Belgium',
    'Egypti':                           'Egypt',
    'Iran':                             'Iran',
    'Uusi-Seelanti':                    'New Zealand',
    # Group H
    'Espanja':                          'Spain',
    'Kap Verde':                        'Cape Verde',
    'Saudi-Arabia':                     'Saudi Arabia',
    'Uruguay':                          'Uruguay',
    # Group I
    'Ranska':                           'France',
    'Senegal':                          'Senegal',
    'Irak':                             'Iraq',
    'Norja':                            'Norway',
    # Group J
    'Argentiina':                       'Argentina',
    'Algeria':                          'Algeria',
    'Itävalta':                         'Austria',
    'Jordania':                         'Jordan',
    # Group K
    'Portugali':                        'Portugal',
    'DR Kongo':                         'DR Congo',
    'Kongon DT':                        'DR Congo',
    'Kongon demokraattinen tasavalta':  'DR Congo',
    'Uzbekistan':                       'Uzbekistan',
    'Kolumbia':                         'Colombia',
    # Group L
    'Englanti':                         'England',
    'Kroatia':                          'Croatia',
    'Ghana':                            'Ghana',
    'Panama':                           'Panama',
}


# All 48 canonical team names — fallback when Unibet uses English instead of Finnish
_ALL_TEAMS = {
    'Mexico', 'South Korea', 'South Africa', 'Czechia',
    'Canada', 'Switzerland', 'Qatar', 'Bosnia-Herzegovina',
    'Brazil', 'Morocco', 'Haiti', 'Scotland',
    'United States', 'Paraguay', 'Australia', 'Türkiye',
    'Germany', 'Curaçao', 'Ivory Coast', 'Ecuador',
    'Netherlands', 'Japan', 'Sweden', 'Tunisia',
    'Belgium', 'Egypt', 'Iran', 'New Zealand',
    'Spain', 'Cape Verde', 'Saudi Arabia', 'Uruguay',
    'France', 'Senegal', 'Iraq', 'Norway',
    'Argentina', 'Algeria', 'Austria', 'Jordan',
    'Portugal', 'DR Congo', 'Uzbekistan', 'Colombia',
    'England', 'Croatia', 'Ghana', 'Panama',
}


def _canonical(name):
    name = name.strip()
    result = FINNISH_NAMES.get(name)
    if result is not None:
        return result
    if name in _ALL_TEAMS:
        return name
    return None


# Finnish heading keywords for each market type (from actual page observation)
_HEADING_MARKETS = [
    ('group_winner', ['ryhmän lopullinen sijoitus', 'lohkovoittaja', 'ryhmävoittaja']),
    ('fourth_place', ['viimeiseksi sijoittuva',   'neljäs sijoitus']),
    ('pairs',        ['täsmällinen loppujärjestys', 'kilpailun yhdistelmät',
                      '1. ja 2.', 'kaksi parasta']),
]


def _scrape_page(page, group, debug=False):
    """
    Scan the page innerText for market blocks in the format:
      heading line
      name1
      name2
      ...
      Voittaja          ← Finnish "Winner" = column header before odds
      odds1
      odds2
      ...
    """
    result = {'group_winner': {}, 'fourth_place': {}, 'pairs': {}}

    try:
        page.wait_for_load_state('networkidle', timeout=20000)
    except Exception:
        pass

    # Wait until odds column header appears (confirms market data is loaded)
    try:
        page.wait_for_function(
            "() => document.body.innerText.includes('Voittaja')",
            timeout=12000,
        )
    except Exception:
        print(f"  WARNING Group {group}: timed out waiting for page data")
        return result

    time.sleep(1.5)

    # Get full page text and split into lines
    full_text = page.inner_text('body')
    lines = [l.strip() for l in full_text.split('\n') if l.strip()]

    if debug:
        print(f"  DEBUG Group {group}: {len(lines)} text lines")

    found = set()   # market types already extracted (take first occurrence only)
    i = 0

    while i < len(lines):
        line_lower = lines[i].lower()

        # Check if this line is a market heading we care about
        market_type = None
        for mtype, keywords in _HEADING_MARKETS:
            if mtype not in found and any(kw in line_lower for kw in keywords):
                market_type = mtype
                break

        if market_type:
            if debug:
                print(f"  DEBUG Group {group}: heading {lines[i]!r} → {market_type}")

            # Scan forward for 'Voittaja' (max 30 lines), collect name lines
            names = []
            voittaja_pos = None
            for j in range(i + 1, min(i + 30, len(lines))):
                if lines[j].lower() == 'voittaja':
                    voittaja_pos = j
                    break
                # Collect as a name if it doesn't look like a plain number.
                # For pairs: require '/' to skip breadcrumb/heading noise.
                if not re.match(r'^\d+[.,]?\d*$', lines[j]) and len(lines[j]) < 70:
                    if market_type == 'pairs':
                        if '/' in lines[j]:
                            names.append(lines[j])
                    else:
                        names.append(lines[j])

            if voittaja_pos is not None and names:
                # Collect decimal odds after 'Voittaja', stop after len(names) values
                odds = []
                skip = 0
                for k in range(voittaja_pos + 1, len(lines)):
                    if len(odds) >= len(names):
                        break
                    try:
                        v = float(lines[k].replace(',', '.'))
                        if 1.01 < v < 1001:
                            odds.append(v)
                            skip = 0
                    except ValueError:
                        skip += 1
                        if skip > 5:
                            break

                if debug:
                    print(f"    {len(names)} names / {len(odds)} odds")
                    print(f"    names:  {names[:4]}")
                    print(f"    odds:   {odds[:4]}")

                parsed = 0
                for name, odd in zip(names, odds):
                    if market_type in ('group_winner', 'fourth_place'):
                        canonical = _canonical(name)
                        if canonical:
                            result[market_type][canonical] = odd
                            parsed += 1
                        else:
                            print(f"  WARNING Group {group}: unknown name {name!r} in {market_type}")
                    else:  # pairs — format "Team1/Team2"
                        parts = re.split(r'\s*/\s*', name, maxsplit=1)
                        if len(parts) == 2:
                            c1 = _canonical(parts[0])
                            c2 = _canonical(parts[1])
                            if c1 and c2:
                                result['pairs'][f"{c1}|{c2}"] = odd
                                parsed += 1
                            else:
                                if not c1:
                                    print(f"  WARNING Group {group}: unknown {parts[0]!r} in pairs")
                                if not c2:
                                    print(f"  WARNING Group {group}: unknown {parts[1]!r} in pairs")
                        elif debug:
                            print(f"    can't split pair: {name!r}")

                if parsed > 0:
                    found.add(market_type)

        i += 1

    return result


def scrape_unibet(groups=None, debug=False):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  WARNING: playwright not installed. Run: pip install playwright && playwright install chromium")
        return load_unibet_cache()

    target_groups = sorted(groups or GROUP_URLS.keys())
    data = {
        "fetched":      datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        "group_winner": {},
        "fourth_place": {},
        "pairs":        {},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not debug)
        context = browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            )
        )
        page = context.new_page()

        for i, group in enumerate(target_groups):
            url = GROUP_URLS.get(group)
            if not url:
                print(f"  WARNING: no URL configured for group {group}")
                continue

            print(f"  Scraping Group {group}...")
            try:
                page.goto(url, timeout=25000)
                grp_data = _scrape_page(page, group, debug=debug)

                if grp_data['group_winner']:
                    data['group_winner'][group] = grp_data['group_winner']
                if grp_data['fourth_place']:
                    data['fourth_place'][group] = grp_data['fourth_place']
                if grp_data['pairs']:
                    data['pairs'][group] = grp_data['pairs']

                gw = len(grp_data['group_winner'])
                fp = len(grp_data['fourth_place'])
                pr = len(grp_data['pairs'])
                print(f"    winner: {gw} teams, 4th place: {fp} teams, pairs: {pr}")

            except Exception as exc:
                print(f"  WARNING Group {group}: scrape failed ({exc})")

            if i < len(target_groups) - 1:
                time.sleep(1.5)

        browser.close()

    with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    _DOCS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_CACHE_FILE, _DOCS_CACHE)
    print(f"  Unibet cache written → unibet_cache.json + docs/data/unibet_cache.json")

    return data


def load_unibet_cache():
    if _CACHE_FILE.exists():
        with open(_CACHE_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {"fetched": None, "group_winner": {}, "fourth_place": {}, "pairs": {}}


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description='Scrape Unibet group-stage markets')
    parser.add_argument('--group', type=str, help='Scrape a single group (e.g. A)')
    parser.add_argument('--debug', action='store_true', help='Visible browser + verbose output')
    args = parser.parse_args()

    target = [args.group.upper()] if args.group else None
    result = scrape_unibet(groups=target, debug=args.debug)

    print("\nSummary:")
    for grp in sorted(GROUP_URLS.keys()):
        gw = len(result['group_winner'].get(grp, {}))
        fp = len(result['fourth_place'].get(grp, {}))
        pr = len(result['pairs'].get(grp, {}))
        print(f"  Group {grp}: winner={gw}  4th={fp}  pairs={pr}")
