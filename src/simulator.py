import itertools
from ranking_rules import compute_position_shares

OUTCOME_LABELS = ['home', 'draw', 'away']


def simulate_group(teams, matches, match_odds):
    """
    Enumerate all 3^6 = 729 outcome combinations for a group and accumulate
    finishing-position probabilities for each team.

    teams:       list of 4 team names
    matches:     list of 6 (home, away) tuples (must match the order used by match_odds)
    match_odds:  dict {(team_a, team_b): (p_a_wins, p_draw, p_b_wins)}

    Returns: {team: [p_1st, p_2nd, p_3rd, p_4th]}
    """
    # Resolve (p_home, p_draw, p_away) for each match in the fixed order
    match_probs = []
    for home, away in matches:
        if (home, away) in match_odds:
            match_probs.append(match_odds[(home, away)])
        elif (away, home) in match_odds:
            pa, pd, ph = match_odds[(away, home)]
            match_probs.append((ph, pd, pa))
        else:
            match_probs.append((1 / 3, 1 / 3, 1 / 3))

    result = {t: [0.0, 0.0, 0.0, 0.0] for t in teams}

    for combo in itertools.product(range(3), repeat=6):
        joint_prob = 1.0
        for i, idx in enumerate(combo):
            joint_prob *= match_probs[i][idx]

        outcomes = [OUTCOME_LABELS[idx] for idx in combo]
        shares = compute_position_shares(matches, outcomes)

        for team in teams:
            for pos in range(4):
                result[team][pos] += joint_prob * shares[team][pos]

    return result
