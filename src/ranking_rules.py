def compute_position_shares(matches, outcomes):
    """
    Given 6 match pairings and their outcomes, return each team's probability
    share per finishing position for this single outcome combination.

    matches:  list of 6 (team_a, team_b) tuples; team_a is the 'home' side
    outcomes: list of 6 strings — 'home' (team_a wins), 'draw', or 'away' (team_b wins)

    Returns: {team: [p1, p2, p3, p4]}
             For an outright position the share is 1.0; for a tie it is 1/n
             distributed equally across all contested positions.
    """
    # Collect teams in stable order
    teams = list(dict.fromkeys(t for pair in matches for t in pair))

    # --- Step 1: overall points ---
    points = {t: 0 for t in teams}
    for (ta, tb), outcome in zip(matches, outcomes):
        if outcome == 'home':
            points[ta] += 3
        elif outcome == 'draw':
            points[ta] += 1
            points[tb] += 1
        else:
            points[tb] += 3

    # --- Step 2: sort into tiers by overall points ---
    sorted_teams = sorted(teams, key=lambda t: -points[t])
    tiers = []
    for team in sorted_teams:
        if not tiers or points[team] != points[tiers[-1][0]]:
            tiers.append([team])
        else:
            tiers[-1].append(team)

    result = {t: [0.0, 0.0, 0.0, 0.0] for t in teams}
    pos = 0

    for tier in tiers:
        if len(tier) == 1:
            result[tier[0]][pos] = 1.0
            pos += 1
            continue

        # --- Step 3: head-to-head points within the tied group ---
        h2h = {t: 0 for t in tier}
        tier_set = set(tier)
        for (ta, tb), outcome in zip(matches, outcomes):
            if ta in tier_set and tb in tier_set:
                if outcome == 'home':
                    h2h[ta] += 3
                elif outcome == 'draw':
                    h2h[ta] += 1
                    h2h[tb] += 1
                else:
                    h2h[tb] += 3

        sorted_tier = sorted(tier, key=lambda t: -h2h[t])
        h2h_tiers = []
        for team in sorted_tier:
            if not h2h_tiers or h2h[team] != h2h[h2h_tiers[-1][0]]:
                h2h_tiers.append([team])
            else:
                h2h_tiers[-1].append(team)

        sub_pos = pos
        for h2h_tier in h2h_tiers:
            if len(h2h_tier) == 1:
                result[h2h_tier[0]][sub_pos] = 1.0
                sub_pos += 1
            else:
                # Still tied after H2H → equal split across all contested positions
                share = 1.0 / len(h2h_tier)
                for t in h2h_tier:
                    for p in range(sub_pos, sub_pos + len(h2h_tier)):
                        result[t][p] = share
                sub_pos += len(h2h_tier)

        pos += len(tier)

    return result
