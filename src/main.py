import argparse
import json
import os
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


def write_json(all_sim_results, adv_probs, match_odds, match_results):
    out_path = Path(__file__).parent.parent / 'docs' / 'data' / 'group_rankings.json'
    os.makedirs(out_path.parent, exist_ok=True)

    schedule = load_schedule()

    groups_data = {}
    for group_name in sorted(all_sim_results.keys()):
        teams   = GROUPS[group_name]
        matches = GROUP_MATCHES[group_name]
        positions  = all_sim_results[group_name]['positions']
        pair_probs = all_sim_results[group_name]['pairs']

        teams_list = [
            {
                'name':     t,
                'probs':    [round(p, 4) for p in positions[t]],
                'adv_prob': round(adv_probs.get(t, 0.0), 4),
            }
            for t in sorted(teams, key=lambda t: -positions[t][0])
        ]

        pairs_list = [
            {'first': first, 'second': second, 'prob': round(p, 4)}
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
            matches_list.append({
                'home':   home,
                'away':   away,
                'date':   date,
                'p_home': round(ph, 4),
                'p_draw': round(pd, 4),
                'p_away': round(pa, 4),
                'result': _get_result(home, away, match_results),
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cached', action='store_true',
                        help='Use locally cached odds instead of calling the API')
    args = parser.parse_args()

    if args.cached:
        print("Loading cached odds...")
        match_odds, fetched_at = load_cached_odds()
        if match_odds is None:
            print("  No cache found — fetching from API instead.")
            args.cached = False
        else:
            print(f"  Loaded {len(match_odds)} matches from odds_cache.json (fetched {fetched_at}).")

    if not args.cached:
        print("Fetching odds from The Odds API...")
        try:
            match_odds = fetch_odds()
            print(f"  Got odds for {len(match_odds)} matches. Saved to odds_cache.json.")
        except Exception as exc:
            print(f"  Warning: could not fetch odds ({exc}). Trying cache...")
            match_odds, fetched_at = load_cached_odds()
            if match_odds:
                print(f"  Fell back to cached odds from {fetched_at}.")
            else:
                print("  No cache available. Using 1/3 fallback for all matches.")
                match_odds = {}

    print("Fetching completed match results...")
    match_results = fetch_results()

    match_probs = {**match_odds, **match_results}
    if match_results:
        print(f"  {len(match_results)} completed match(es) will use definitive result.")

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
    write_json(all_sim_results, adv_probs, match_odds, match_results)


if __name__ == '__main__':
    main()
