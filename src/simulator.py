import itertools
from ranking_rules import compute_position_shares

OUTCOME_LABELS = ['home', 'draw', 'away']


def simulate_group(teams, matches, match_odds):
    """
    Enumerate all 3^6 = 729 outcome combinations and accumulate statistics.

    Returns a dict with:
      'positions'  {team: [p_1st, p_2nd, p_3rd, p_4th]}
      'pairs'      {(team_i, team_j): prob}  — ordered (1st, 2nd) pair probabilities
      'third_pts'  {team: {k: prob}}  — P(team finishes 3rd with exactly k points)
    """
    match_probs = []
    for home, away in matches:
        if (home, away) in match_odds:
            match_probs.append(match_odds[(home, away)])
        elif (away, home) in match_odds:
            pa, pd, ph = match_odds[(away, home)]
            match_probs.append((ph, pd, pa))
        else:
            match_probs.append((1 / 3, 1 / 3, 1 / 3))

    positions  = {t: [0.0, 0.0, 0.0, 0.0] for t in teams}
    pairs      = {}
    third_pts  = {t: {} for t in teams}

    for combo in itertools.product(range(3), repeat=6):
        joint_prob = 1.0
        for i, idx in enumerate(combo):
            joint_prob *= match_probs[i][idx]

        outcomes = [OUTCOME_LABELS[idx] for idx in combo]
        shares, pair_probs, pts = compute_position_shares(matches, outcomes)

        # Position shares
        for team in teams:
            for pos in range(4):
                positions[team][pos] += joint_prob * shares[team][pos]

        # (1st, 2nd) ordered pair probabilities
        for (i, j), p in pair_probs.items():
            pairs[(i, j)] = pairs.get((i, j), 0.0) + joint_prob * p

        # 3rd-place point distribution: P(team is 3rd WITH exactly k points)
        for team in teams:
            s3 = shares[team][2]
            if s3 > 0:
                k = pts[team]
                third_pts[team][k] = third_pts[team].get(k, 0.0) + joint_prob * s3

    return {'positions': positions, 'pairs': pairs, 'third_pts': third_pts}
