"""
Compute each team's probability of advancing to the knockout round.

Rules:
  - All 12 group winners (1st) advance automatically.
  - All 12 runners-up (2nd) advance automatically.
  - The 8 best third-place teams advance (ranked by points).
  - Ties among 3rd-place teams are broken by equal split (we have no goal data).
"""

from groups import GROUPS

N_SPOTS_THIRD = 8   # how many 3rd-place teams qualify
N_GROUPS      = 12


def compute_advancement_probs(all_sim_results):
    """
    all_sim_results: {group_name: {'positions': ..., 'pairs': ..., 'third_pts': ...}}

    Returns {team: advancement_probability}
    """
    # Group-level 3rd-place point distributions:
    # group_third_dist[g][k] = P(group g's 3rd-place team has exactly k points)
    group_third_dist = {}
    for g, result in all_sim_results.items():
        dist = {}
        for team_pts in result['third_pts'].values():
            for k, p in team_pts.items():
                dist[k] = dist.get(k, 0.0) + p
        group_third_dist[g] = dist

    adv_probs = {}
    for g, result in all_sim_results.items():
        positions = result['positions']
        third_pts = result['third_pts']
        other_dists = [group_third_dist[og] for og in all_sim_results if og != g]

        for team in GROUPS[g]:
            p_top2      = positions[team][0] + positions[team][1]
            p_third_adv = _third_advancement(third_pts[team], other_dists)
            adv_probs[team] = p_top2 + p_third_adv

    return adv_probs


def _third_advancement(team_third_pts, other_dists):
    """
    P(team advances as a 3rd-place team).

    team_third_pts: {k: P(team is 3rd with k points)}  — sums to P(team is 3rd) ≤ 1
    other_dists:    list of 11 dicts {k: prob}          — each sums to 1.0

    For each possible k the team could achieve as 3rd, we use a DP over the 11 other
    groups to find the joint distribution of (n_above, n_equal) — how many other
    3rd-place teams have more than k points, and how many have exactly k points.
    The advancement fraction is then (N_SPOTS_THIRD - n_above) / (n_equal + 1),
    clamped to [0, 1].
    """
    if not team_third_pts:
        return 0.0

    n = len(other_dists)   # 11

    total = 0.0
    for k, p_at_k in team_third_pts.items():
        if p_at_k <= 0:
            continue

        # Precompute per-group probabilities relative to threshold k
        above_eq_below = [
            (
                sum(p for kk, p in d.items() if kk > k),
                d.get(k, 0.0),
            )
            for d in other_dists
        ]

        # DP over n groups: dp[a][e] = P(n_above==a, n_equal==e)
        dp = [[0.0] * (n + 1) for _ in range(n + 1)]
        dp[0][0] = 1.0

        for p_above, p_equal in above_eq_below:
            p_below = max(0.0, 1.0 - p_above - p_equal)
            new_dp = [[0.0] * (n + 1) for _ in range(n + 1)]
            for a in range(n + 1):
                for e in range(n + 1 - a):
                    w = dp[a][e]
                    if w == 0.0:
                        continue
                    if a + 1 <= n:
                        new_dp[a + 1][e] += w * p_above
                    new_dp[a][e + 1]     += w * p_equal
                    new_dp[a][e]         += w * p_below
            dp = new_dp

        # Expected advancement fraction for this value of k
        e_frac = 0.0
        for a in range(n + 1):
            for e in range(n + 1 - a):
                w = dp[a][e]
                if w == 0.0:
                    continue
                if a >= N_SPOTS_THIRD:
                    frac = 0.0
                elif a + e + 1 <= N_SPOTS_THIRD:
                    frac = 1.0
                else:
                    frac = (N_SPOTS_THIRD - a) / (e + 1)
                e_frac += w * frac

        total += p_at_k * e_frac

    return total
