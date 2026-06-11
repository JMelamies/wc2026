# WC2026 Group Stage Ranking Probability Calculator

## Project Goal
Calculate the probability of each team finishing in each position (1st–4th) in their group at the
2026 FIFA World Cup, using betting odds and completed match results. Display results via a static
web site hosted on GitHub Pages. Compare calculated probabilities against Betfair Exchange markets
to identify value opportunities.

---

## Current file structure
```
wc2026/
├── CLAUDE.md
├── requirements.txt              # requests, python-dotenv, betfairlightweight
├── .env                          # not committed
├── results_cache.json            # committed, project root
├── odds_cache.json               # committed, project root
├── betfair_cache.json            # committed, project root (written by main.py)
│
├── src/
│   ├── config.py                 # loads API keys from .env; TEAM_ALIASES dict
│   ├── groups.py                 # GROUPS dict + GROUP_MATCHES dict
│   ├── odds_fetcher.py           # fetch_odds(), load_cached_odds(), load_schedule()
│   ├── results_fetcher.py        # fetch_results() → results_cache.json
│   ├── betfair_fetcher.py        # fetch_betfair(), load_betfair_cache(), get_inplay_matches()
│   ├── ranking_rules.py          # compute_position_shares()
│   ├── simulator.py              # simulate_group() → {positions, pairs}
│   ├── qualification.py          # compute_advancement_probs()
│   └── main.py                   # entry point
│
└── docs/                         # GitHub Pages source (branch: main, folder: /docs)
    ├── index.html
    ├── app.js
    ├── styles.css
    └── data/
        ├── group_rankings.json   # written by main.py
        └── betfair_cache.json    # copied from project root by main.py
```

---

## Running the calculator
```
python src/main.py                              # default: Odds API + results (normal mode)
python src/main.py --mode normal               # same as above
python src/main.py --mode cached               # no API calls, load from cache files
python src/main.py --mode live                 # cached odds baseline + Betfair override for in-play matches
python src/main.py --mode all                  # Odds API + results + Betfair in-play
python src/main.py --mode betfair-group --group A  # results + Betfair for all Group A matches
```

---

## Key module contracts (do not change logic unless explicitly asked)

### simulate_group() → dict
Returns `{'positions': {team: [p1,p2,p3,p4]}, 'pairs': {(first,second): prob}}`
- `positions`: finishing position probabilities per team
- `pairs`: probability of each (1st_team, 2nd_team) combination, sums to 1.0

### compute_advancement_probs(all_sim_results) → dict
Returns `{team: adv_prob}` where `adv_prob` = probability of advancing to round of 32.
Accounts for: automatic qualification as 1st or 2nd + being among the 8 best 3rd-place teams.

### odds_fetcher
- `fetch_odds()` → `(match_odds_dict, credits_dict)`, writes `odds_cache.json`
- `load_cached_odds()` → `(match_odds_dict, fetched_at_str)` or `(None, None)`
- `load_schedule()` → `{(team_a, team_b): date_str}`

### results_fetcher
- `fetch_results()` → `{(home, away): (p_home, p_draw, p_away)}` with certainty values

### Priority order for match probabilities
1. Completed result from `results_cache.json` — certainty `(1,0,0)` / `(0,1,0)` / `(0,0,1)`
2. Betfair in-play odds (when applicable per mode — see below)
3. Odds API odds from `odds_cache.json`
4. Fallback `(1/3, 1/3, 1/3)`

---

## group_rankings.json schema (current)
Written to `docs/data/group_rankings.json` by `main.py`.

```json
{
  "generated": "2026-06-10T14:32:00",
  "groups": {
    "A": {
      "teams": [
        {
          "name": "Mexico",
          "probs": [0.452, 0.301, 0.164, 0.083],
          "adv_prob": 0.753
        }
      ],
      "pairs": [
        {"first": "Mexico", "second": "South Korea", "prob": 0.312}
      ],
      "matches": [
        {
          "home": "Mexico",
          "away": "South Korea",
          "date": "2026-06-12T18:00:00",
          "p_home": 0.45,
          "p_draw": 0.28,
          "p_away": 0.27,
          "result": null
        }
      ]
    }
  }
}
```

- `probs`: `[p_1st, p_2nd, p_3rd, p_4th]`, sum to 1.0
- `adv_prob`: probability of advancing to round of 32
- `pairs`: all 12 (1st, 2nd) team combinations sorted by prob descending, sum to 1.0
- `matches[].result`: `null` / `"home"` / `"draw"` / `"away"`
- `matches[].date`: ISO datetime string or `null`
- Teams sorted by `probs[0]` descending; groups sorted A–L

---

## Betfair integration (TO BE IMPLEMENTED)

### New environment variables (already in .env)
```
BETFAIR_APP_KEY=...
BETFAIR_USERNAME=...
BETFAIR_PASSWORD=...
```
Load in `config.py` alongside existing keys.

### New file: src/betfair_fetcher.py
Uses `betfairlightweight` library. Manages session internally.

#### Functions

**`fetch_betfair(groups_filter=None) -> dict`**
Fetches Betfair markets, writes `betfair_cache.json` to project root, returns data.
- `groups_filter`: optional list of group letters — if provided, only fetch match odds
  for those groups. Always fetch group_winner and to_qualify for all groups.
- On any failure: warn, return existing cache if available, else empty structure.

**`load_betfair_cache() -> dict`**
Load `betfair_cache.json` from project root. Return empty structure if not found.

**`get_inplay_matches(betfair_data) -> list[tuple]`**
Return list of `(home, away)` tuples for matches currently in-play per Betfair.

#### Markets to fetch
- `MATCH_ODDS` — for match outcome probabilities (in-play override)
- `TO_QUALIFY` — for adv_prob comparison
- `WINNER` — for p_1st comparison (group winner market)

Filter: `eventTypeId="1"` (soccer), competition name containing "World Cup 2026".
Map all runner/team names through `TEAM_ALIASES` from `config.py`.
Use best available **back price** per runner.

#### betfair_cache.json schema
```json
{
  "fetched": "2026-06-10T14:32:00",
  "match_odds": {
    "Mexico|South Korea": {
      "home": 2.10,
      "draw": 3.40,
      "away": 3.60,
      "inplay": false
    }
  },
  "group_winner": {
    "A": {"Mexico": 1.85, "South Korea": 3.20, "South Africa": 8.00, "Czechia": 6.50}
  },
  "to_qualify": {
    "A": {"Mexico": 1.25, "South Korea": 1.90, "South Africa": 3.50, "Czechia": 2.80}
  }
}
```
All values are decimal back odds. Keys use canonical team names from `groups.py`.

### Updated running modes
Replace the current `--cached` flag with `--mode` argument:

```
python src/main.py --mode normal        # default: Odds API + results (replaces no-flag)
python src/main.py --mode cached        # replaces --cached flag
python src/main.py --mode live          # results + Betfair for in-play matches only
python src/main.py --mode all           # Odds API + results + Betfair for in-play matches
python src/main.py --mode betfair-group --group A   # results + Betfair for all matches in group A
```

| Mode | Odds API | Betfair | Scope |
|---|---|---|---|
| `cached` | load cache | load cache | no API calls |
| `normal` | fetch | — | upcoming matches |
| `live` | load cache | fetch | Betfair overrides in-play matches |
| `all` | fetch | fetch | Odds API upcoming + Betfair in-play |
| `betfair-group` | — | fetch | ongoing + upcoming in `--group X` only |

Betfair in-play odds are converted to normalised probabilities before overriding Odds API:
```python
ph, pd, pa = 1/bf_home, 1/bf_draw, 1/bf_away
total = ph + pd + pa
probs = (ph/total, pd/total, pa/total)
```

### Updated group_rankings.json schema (add Betfair fields)
Add to each team entry:
```json
{
  "name": "Mexico",
  "probs": [0.452, 0.301, 0.164, 0.083],
  "adv_prob": 0.753,
  "bf_group_winner_odds": 1.85,
  "bf_to_qualify_odds": 1.25
}
```
Add to each match entry:
```json
{
  "home": "Mexico", "away": "South Korea",
  "date": "2026-06-12T18:00:00",
  "p_home": 0.45, "p_draw": 0.28, "p_away": 0.27,
  "result": null,
  "inplay": false
}
```
- `bf_*` fields are `null` when Betfair data not available
- `inplay` is `false` by default

After writing `docs/data/group_rankings.json`, also copy `betfair_cache.json` from
project root to `docs/data/betfair_cache.json` so the frontend can access it.

### Frontend: Betfair comparison & flagging (app.js + styles.css)

#### Threshold controls
Add to page header, above group cards:
```
Flag threshold: [20] %     Super-flag threshold: [50] %
```
Two `<input type="number">` fields. On change, re-evaluate all flags client-side instantly.

#### Flagging logic
Flag when **Betfair odds are higher than our implied odds** — Betfair thinks outcome is
less likely than we do → potential value.

```javascript
function flagLevel(bf_odds, our_prob, flagT, superT) {
  if (!bf_odds || !our_prob || our_prob <= 0) return null;
  const our_odds = 1 / our_prob;
  const pct = (bf_odds - our_odds) / our_odds;  // e.g. (110-90)/90 = 0.22
  if (pct >= superT / 100) return 'super';
  if (pct >= flagT / 100) return 'flag';
  return null;
}
```

Apply to:
- `1st` cell: `flagLevel(team.bf_group_winner_odds, team.probs[0], ...)`
- `adv` cell: `flagLevel(team.bf_to_qualify_odds, team.adv_prob, ...)`

#### Flagged cell styling
- Normal flag: amber left border (4px solid `#f59e0b`) + small superscript with Betfair odds
- Super-flag: red left border (4px solid `#ef4444`) + same superscript
- Example cell content: `45.2% ᴮᶠ1.85`

#### In-play indicator
Show 🔴 LIVE badge next to any match in the matches list where `inplay === true`.

---

## Calculation logic (do not change)

### Match outcome probabilities
- Normalised: `p_i = (1/odd_i) / Σ(1/odd_j)`
- Results override with certainty; Betfair in-play overrides Odds API; fallback 1/3

### Brute-force enumeration
- 729 combos per group via `itertools.product(range(3), repeat=6)`
- Joint prob = product of 6 match outcome probs

### Tiebreakers (in order)
1. Overall points
2. Head-to-head points among tied teams only
3. Equal split

### Points: Win 3, Draw 1, Loss 0

---

## Key constraints
- `results_cache.json`, `odds_cache.json`, `betfair_cache.json` all stay in project root
- `docs/data/` path used throughout (not `web/data/`)
- `.env` in project root; loaded via `Path(__file__).parent.parent / '.env'`
- Cache file paths use `Path(__file__).parent.parent / 'filename.json'`
- `.gitignore`: includes `.env`; does NOT ignore cache files or `docs/data/`
- Add `betfairlightweight` to `requirements.txt`
