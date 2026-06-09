import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Allow sibling imports when invoked as  python src/main.py  from the project root
sys.path.insert(0, os.path.dirname(__file__))

# Force UTF-8 output so Unicode team names display correctly on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from groups import GROUPS, GROUP_MATCHES
from odds_fetcher import fetch_odds
from results_fetcher import fetch_results
from simulator import simulate_group

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
    """Return 'home'/'draw'/'away' (relative to our fixture ordering) or None."""
    if (home, away) in match_results:
        return _PROBS_TO_OUTCOME.get(match_results[(home, away)])
    if (away, home) in match_results:
        raw = match_results[(away, home)]
        return _PROBS_TO_OUTCOME.get((raw[2], raw[1], raw[0]))
    return None


def print_group(group_name, teams, matches, match_probs, group_probs):
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
    print(f"  {'Team':<22} {'1st':>7} {'2nd':>7} {'3rd':>7} {'4th':>7}")
    print(f"  {'-'*22} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
    for team in sorted(teams, key=lambda t: -group_probs[t][0]):
        p = group_probs[team]
        print(f"  {team:<22} {p[0]:>6.1%} {p[1]:>6.1%} {p[2]:>6.1%} {p[3]:>6.1%}")
    return covered


def write_json(all_group_probs, match_odds, match_results):
    out_path = Path(__file__).parent.parent / 'docs' / 'data' / 'group_rankings.json'
    os.makedirs(out_path.parent, exist_ok=True)

    groups_data = {}
    for group_name in sorted(all_group_probs.keys()):
        teams = GROUPS[group_name]
        matches = GROUP_MATCHES[group_name]
        group_probs = all_group_probs[group_name]

        teams_list = [
            {'name': t, 'probs': [round(p, 4) for p in group_probs[t]]}
            for t in sorted(teams, key=lambda t: -group_probs[t][0])
        ]

        matches_list = []
        for home, away in matches:
            ph, pd, pa = resolve_probs(home, away, match_odds)
            matches_list.append({
                'home': home,
                'away': away,
                'p_home': round(ph, 4),
                'p_draw': round(pd, 4),
                'p_away': round(pa, 4),
                'result': _get_result(home, away, match_results),
            })

        groups_data[group_name] = {'teams': teams_list, 'matches': matches_list}

    payload = {
        'generated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'groups': groups_data,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"  JSON written → docs/data/group_rankings.json")


def main():
    print("Fetching odds from The Odds API...")
    try:
        match_odds = fetch_odds()
        print(f"  Got odds for {len(match_odds)} matches.")
    except Exception as exc:
        print(f"  Warning: could not fetch odds ({exc}). Using 1/3 fallback for all matches.")
        match_odds = {}

    print("Fetching completed match results...")
    match_results = fetch_results()

    # Results override odds: a finished match has certainty, not a probability estimate
    match_probs = {**match_odds, **match_results}
    if match_results:
        print(f"  {len(match_results)} completed match(es) will use definitive result.")

    total_covered = 0
    total_matches = 0
    all_group_probs = {}

    for group_name in sorted(GROUPS.keys()):
        teams = GROUPS[group_name]
        matches = GROUP_MATCHES[group_name]
        group_probs = simulate_group(teams, matches, match_probs)
        all_group_probs[group_name] = group_probs
        covered = print_group(group_name, teams, matches, match_probs, group_probs)
        total_covered += covered
        total_matches += len(matches)

    print(f"\n--- Summary ---")
    print(f"  Odds found for {total_covered}/{total_matches} group-stage matches.")

    print("\n--- Sanity checks ---")
    warnings = []
    for group_name, group_probs in all_group_probs.items():
        teams = GROUPS[group_name]
        for pos in range(4):
            total = sum(group_probs[t][pos] for t in teams)
            if abs(total - 1.0) > 1e-6:
                warnings.append(f"  Group {group_name} position {pos + 1}: column sum = {total:.8f}")
        for team in teams:
            total = sum(group_probs[team])
            if abs(total - 1.0) > 1e-6:
                warnings.append(f"  Group {group_name} {team}: row sum = {total:.8f}")
    if warnings:
        for w in warnings:
            print(w)
    else:
        print("  All column and row sums within tolerance. ✓")

    print("\n--- JSON export ---")
    write_json(all_group_probs, match_odds, match_results)


if __name__ == '__main__':
    main()
