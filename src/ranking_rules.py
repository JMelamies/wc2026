def compute_position_shares(matches, outcomes):
    """
    Given 6 match pairings and their outcomes, return position shares, (1st,2nd)
    pair probabilities, and each team's point total for this outcome combination.

    matches:  list of 6 (team_a, team_b) tuples; team_a is the 'home' side
    outcomes: list of 6 strings — 'home' (team_a wins), 'draw', 'away' (team_b wins)

    Returns: (position_shares, pair_probs, points)
      position_shares: {team: [p0, p1, p2, p3]}
      pair_probs:      {(team_i, team_j): prob}  — all (1st, 2nd) ordered pairs
      points:          {team: int}
    """
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

    # --- Step 3: within each multi-team tier apply H2H, build ranked_blocks ---
    # ranked_blocks is a flat list of lists; each inner list is an H2H sub-tier
    # whose members share equal probability for the positions they span.
    ranked_blocks = []
    for tier in tiers:
        if len(tier) == 1:
            ranked_blocks.append(tier)
        else:
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
            ranked_blocks.extend(h2h_tiers)

    # --- Step 4: assign position shares ---
    position_shares = {t: [0.0, 0.0, 0.0, 0.0] for t in teams}
    pos = 0
    for block in ranked_blocks:
        n = len(block)
        if n == 1:
            position_shares[block[0]][pos] = 1.0
        else:
            share = 1.0 / n
            for t in block:
                for p in range(pos, pos + n):
                    position_shares[t][p] = share
        pos += n

    # --- Step 5: pair probabilities for (1st, 2nd) ---
    # Identify which ranked block covers position 0 and which covers position 1.
    block_at_0 = None
    block_at_1 = None
    cur = 0
    for block in ranked_blocks:
        n = len(block)
        if block_at_0 is None and cur <= 0 < cur + n:
            block_at_0 = block
        if block_at_1 is None and cur <= 1 < cur + n:
            block_at_1 = block
        if block_at_0 is not None and block_at_1 is not None:
            break
        cur += n

    pair_probs = {}
    if block_at_0 is block_at_1:
        # Same block spans both positions 0 and 1 — uniform over all ordered pairs
        n = len(block_at_0)
        p = 1.0 / (n * (n - 1))
        for i in block_at_0:
            for j in block_at_0:
                if i != j:
                    pair_probs[(i, j)] = p
    else:
        # block_at_0 is a singleton; block_at_1 has all 2nd-place candidates
        i0 = block_at_0[0]
        p = 1.0 / len(block_at_1)
        for j in block_at_1:
            pair_probs[(i0, j)] = p

    return position_shares, pair_probs, points
