import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from groups import GROUPS, GROUP_MATCHES
from odds_fetcher import fetch_odds, load_cached_odds, load_schedule
from results_fetcher import fetch_results
from simulator import simulate_group
from qualification import compute_advancement_probs
from betfair_fetcher import fetch_betfair, load_betfair_cache, get_inplay_matches
from unibet_scraper import load_unibet_cache

_RESULT_LABEL = {
    (1.0, 0.0, 0.0): 'Home win',
    (0.0, 1.0, 0.0): 'Draw',
    (0.0, 0.0, 1.0): 'Away win',
}

_PROBS_TO_OUTCOME = {
    (1.0, 0.0, 0.0): 'home',
    (0.0, 1.0, 0.0): 'draw',
    (0.0, 0.0, 1.0): 'away',
}

_OUTCOME_PROBS = {
    'home': (1.0, 0.0, 0.0),
    'draw': (0.0, 1.0, 0.0),
    'away': (0.0, 0.0, 1.0),
}


def resolve_probs(home, away, match_probs):
    if (home, away) in match_probs:
        return match_probs[(home, away)]
    if (away, home) in match_probs:
        pa, pd, ph = match_probs[(away, home)]
        return (ph, pd, pa)
    return (1 / 3, 1 / 3, 1 / 3)


def _get_result(home, away, match_results):
    if (home, away) in match_results:
        return _PROBS_TO_OUTCOME.get(match_results[(home, away)])
    if (away, home) in match_results:
        raw = match_results[(away, home)]
        return _PROBS_TO_OUTCOME.get((raw[2], raw[1], raw[0]))
    return None


def _load_results_cache():
    cache_path = Path(__file__).parent.parent / 'results_cache.json'
    if cache_path.exists():
        with open(cache_path, encoding='utf-8') as f:
            cache = json.load(f)
        return {tuple(k.split('|', 1)): _OUTCOME_PROBS[v] for k, v in cache.items()}
    return {}


def print_group(group_name, teams, matches, match_probs, positions, adv_probs):
    print(f"\nGroup {group_name}:")
    print("  Matches:")
    covered = 0
    for home, away in matches:
        ph, pd, pa = resolve_probs(home, away, match_probs)
        result_label = _RESULT_LABEL.get((ph, pd, pa))
        if result_label:
            print(f"    {home} vs {away}: [FT: {result_label}]")
            covered += 1
        elif (home, away) in match_probs or (away, home) in match_probs:
            print(f"    {home} vs {away}: {ph:.1%} / {pd:.1%} / {pa:.1%}")
            covered += 1
        else:
            print(f"    {home} vs {away}: {ph:.1%} / {pd:.1%} / {pa:.1%}  [fallback 1/3]")

    print()
    print(f"  {'Team':<22} {'1st':>7} {'2nd':>7} {'3rd':>7} {'4th':>7} {'Adv':>7}")
    print(f"  {'-'*22} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
    for team in sorted(teams, key=lambda t: -positions[t][0]):
        p = positions[team]
        adv = adv_probs.get(team, 0.0)
        print(f"  {team:<22} {p[0]:>6.1%} {p[1]:>6.1%} {p[2]:>6.1%} {p[3]:>6.1%} {adv:>6.1%}")
    return covered


def write_json(all_sim_results, adv_probs, match_odds, match_results, betfair_data, inplay_matches, live_scores=None):
    out_path = Path(__file__).parent.parent / 'docs' / 'data' / 'group_rankings.json'
    os.makedirs(out_path.parent, exist_ok=True)

    schedule = load_schedule()

    unibet_data = load_unibet_cache()

    groups_data = {}
    for group_name in sorted(all_sim_results.keys()):
        teams      = GROUPS[group_name]
        matches    = GROUP_MATCHES[group_name]
        positions  = all_sim_results[group_name]['positions']
        pair_probs = all_sim_results[group_name]['pairs']

        gw = betfair_data["group_winner"].get(group_name, {})
        tq = betfair_data["to_qualify"].get(group_name, {})
        ub_gw = unibet_data["group_winner"].get(group_name, {})
        ub_fp = unibet_data["fourth_place"].get(group_name, {})
        ub_pairs = unibet_data["pairs"].get(group_name, {})

        teams_list = [
            {
                'name':     t,
                'probs':    [round(p, 4) for p in positions[t]],
                'adv_prob': round(adv_probs.get(t, 0.0), 4),
                'bf_group_winner_odds':  round(gw[t], 4)    if gw.get(t)    else None,
                'bf_to_qualify_odds':    round(tq[t], 4)    if tq.get(t)    else None,
                'ub_group_winner_odds':  round(ub_gw[t], 4) if ub_gw.get(t) else None,
                'ub_fourth_place_odds':  round(ub_fp[t], 4) if ub_fp.get(t) else None,
            }
            for t in sorted(teams, key=lambda t: -positions[t][0])
        ]

        pairs_list = [
            {
                'first':   first,
                'second':  second,
                'prob':    round(p, 4),
                'ub_odds': round(ub_pairs[f"{first}|{second}"], 4)
                           if ub_pairs.get(f"{first}|{second}") else None,
            }
            for (first, second), p in sorted(pair_probs.items(), key=lambda x: -x[1])
        ]

        matches_list = []
        for team_a, team_b in matches:
            if (team_a, team_b) in schedule:
                home, away, date = team_a, team_b, schedule[(team_a, team_b)]
            elif (team_b, team_a) in schedule:
                home, away, date = team_b, team_a, schedule[(team_b, team_a)]
            else:
                home, away, date = team_a, team_b, None

            ph, pd, pa = resolve_probs(home, away, match_odds)
            is_live = (home, away) in inplay_matches or (away, home) in inplay_matches
            ls = live_scores or {}
            score = ls.get((home, away)) or (
                (ls[away, home][1], ls[away, home][0]) if (away, home) in ls else None
            )
            matches_list.append({
                'home':        home,
                'away':        away,
                'date':        date,
                'p_home':      round(ph, 4),
                'p_draw':      round(pd, 4),
                'p_away':      round(pa, 4),
                'result':      _get_result(home, away, match_results),
                'inplay':      is_live,
                'score_home':  score[0] if score else None,
                'score_away':  score[1] if score else None,
            })

        matches_list.sort(key=lambda m: m['date'] or 'z')

        groups_data[group_name] = {
            'teams':   teams_list,
            'pairs':   pairs_list,
            'matches': matches_list,
        }

    payload = {
        'generated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'groups':    groups_data,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"  JSON written → docs/data/group_rankings.json")

    bf_src = Path(__file__).parent.parent / 'betfair_cache.json'
    bf_dst = Path(__file__).parent.parent / 'docs' / 'data' / 'betfair_cache.json'
    if bf_src.exists():
        shutil.copy2(bf_src, bf_dst)
        print("  Betfair cache copied → docs/data/betfair_cache.json")

    ub_src = Path(__file__).parent.parent / 'unibet_cache.json'
    ub_dst = Path(__file__).parent.parent / 'docs' / 'data' / 'unibet_cache.json'
    if ub_src.exists():
        shutil.copy2(ub_src, ub_dst)
        print("  Unibet cache copied → docs/data/unibet_cache.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--mode',
        choices=['cached', 'normal', 'live', 'betfair-group'],
        default='normal',
    )
    parser.add_argument('--group', type=str,
                        help='Group letter, required for betfair-group mode')
    args = parser.parse_args()

    print(f"Mode: {args.mode}")

    # --- Fetch odds ---
    if args.mode == 'cached':
        print("Loading cached odds...")
        match_odds, fetched_at = load_cached_odds()
        if match_odds is None:
            print("  No cache found — using empty odds.")
            match_odds = {}
        else:
            print(f"  Loaded {len(match_odds)} matches from odds_cache.json (fetched {fetched_at}).")
    elif args.mode == 'normal':
        print("Fetching odds from The Odds API...")
        try:
            match_odds, credits = fetch_odds()
            print(f"  Got odds for {len(match_odds)} matches. Saved to odds_cache.json.")
            print(f"  API credits — this request: {credits['this_request']}"
                  f" | total used: {credits['used_total']} | remaining: {credits['remaining']}")
        except Exception as exc:
            print(f"  Warning: could not fetch odds ({exc}). Trying cache...")
            match_odds, fetched_at = load_cached_odds()
            if match_odds:
                print(f"  Fell back to cached odds from {fetched_at}.")
            else:
                print("  No cache available. Using 1/3 fallback for all matches.")
                match_odds = {}
    elif args.mode == 'live':
        print("Loading cached odds...")
        match_odds, fetched_at = load_cached_odds()
        if match_odds is None:
            print("  No cache found — using 1/3 fallback for non-live matches.")
            match_odds = {}
        else:
            print(f"  Loaded {len(match_odds)} matches from odds_cache.json (fetched {fetched_at}).")
    else:  # betfair-group
        print("Loading cached odds...")
        match_odds, fetched_at = load_cached_odds()
        if match_odds is None:
            print("  No cache found — using 1/3 fallback for non-group matches.")
            match_odds = {}
        else:
            print(f"  Loaded {len(match_odds)} matches from odds_cache.json (fetched {fetched_at}).")

    # --- Fetch results ---
    if args.mode == 'cached':
        print("Loading cached results...")
        match_results = _load_results_cache()
        print(f"  Loaded {len(match_results)} result(s) from results_cache.json.")
        live_scores = {}
    else:
        print("Fetching completed match results...")
        match_results, live_scores = fetch_results()

    # --- Fetch Betfair ---
    if args.mode == 'betfair-group':
        if not args.group:
            print("  Error: --group is required for betfair-group mode")
            sys.exit(1)
        print(f"Fetching Betfair markets for Group {args.group}...")
        betfair_data = fetch_betfair(groups_filter=[args.group.upper()])
    else:
        print("Fetching Betfair markets...")
        betfair_data = fetch_betfair()

    # --- Assemble match probabilities ---
    match_probs = {**match_odds, **match_results}
    if match_results:
        print(f"  {len(match_results)} completed match(es) will use definitive result.")

    # --- Apply Betfair overrides ---
    inplay_matches = get_inplay_matches(betfair_data)
    if inplay_matches:
        for (home, away) in inplay_matches:
            key = f"{home}|{away}"
            if key in betfair_data["match_odds"]:
                bf = betfair_data["match_odds"][key]
                if bf["home"] and bf["draw"] and bf["away"]:
                    ph = 1 / bf["home"]; pd = 1 / bf["draw"]; pa = 1 / bf["away"]
                    total = ph + pd + pa
                    match_probs[(home, away)] = (ph / total, pd / total, pa / total)
                    print(f"  Betfair inplay override: {home} vs {away}")
    if args.mode == 'betfair-group':
        for home, away in GROUP_MATCHES.get(args.group.upper(), []):
            if (home, away) in match_results or (away, home) in match_results:
                continue
            key = f"{home}|{away}"
            if key in betfair_data["match_odds"]:
                bf = betfair_data["match_odds"][key]
                if bf["home"] and bf["draw"] and bf["away"]:
                    ph = 1 / bf["home"]; pd = 1 / bf["draw"]; pa = 1 / bf["away"]
                    total = ph + pd + pa
                    match_probs[(home, away)] = (ph / total, pd / total, pa / total)

    # --- Simulate all groups ---
    print("\nSimulating groups...")
    all_sim_results = {}
    for group_name in sorted(GROUPS.keys()):
        teams   = GROUPS[group_name]
        matches = GROUP_MATCHES[group_name]
        all_sim_results[group_name] = simulate_group(teams, matches, match_probs)

    # --- Qualification (3rd-place advancement) ---
    adv_probs = compute_advancement_probs(all_sim_results)

    # --- Print results ---
    total_covered = 0
    total_matches = 0
    for group_name in sorted(GROUPS.keys()):
        teams   = GROUPS[group_name]
        matches = GROUP_MATCHES[group_name]
        covered = print_group(
            group_name, teams, matches, match_probs,
            all_sim_results[group_name]['positions'],
            adv_probs,
        )
        total_covered += covered
        total_matches += len(matches)

    print(f"\n--- Summary ---")
    print(f"  Odds found for {total_covered}/{total_matches} group-stage matches.")

    # --- Sanity checks ---
    print("\n--- Sanity checks ---")
    warnings = []
    for group_name, result in all_sim_results.items():
        teams     = GROUPS[group_name]
        positions = result['positions']
        pairs     = result['pairs']

        for pos in range(4):
            total = sum(positions[t][pos] for t in teams)
            if abs(total - 1.0) > 1e-6:
                warnings.append(f"  Group {group_name} pos {pos+1} column sum = {total:.8f}")
        for team in teams:
            total = sum(positions[team])
            if abs(total - 1.0) > 1e-6:
                warnings.append(f"  Group {group_name} {team} row sum = {total:.8f}")

        pair_sum = sum(pairs.values())
        if abs(pair_sum - 1.0) > 1e-6:
            warnings.append(f"  Group {group_name} pair probs sum = {pair_sum:.8f}")

    if warnings:
        for w in warnings:
            print(w)
    else:
        print("  All checks within tolerance. ✓")

    print("\n--- JSON export ---")
    write_json(all_sim_results, adv_probs, match_probs, match_results, betfair_data, inplay_matches, live_scores)


if __name__ == '__main__':
    main()
