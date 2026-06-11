# WC2026 Group Stage Ranking Probability Calculator

## Project Goal
Calculate the probability of each team finishing in each position (1st–4th) in their group at the
2026 FIFA World Cup, using betting odds and completed match results. Display results via a static
web site hosted on GitHub Pages. Compare calculated probabilities against Betfair Exchange and
Unibet markets to identify value opportunities.

---

## Current file structure
```
wc2026/
├── CLAUDE.md
├── requirements.txt              # requests, python-dotenv, betfairlightweight, playwright
├── .env                          # not committed
├── results_cache.json            # committed, project root
├── odds_cache.json               # committed, project root
├── betfair_cache.json            # committed, project root
├── unibet_cache.json             # committed, project root (written by unibet_scraper.py)
│
├── src/
│   ├── config.py                 # loads API keys from .env; TEAM_ALIASES dict
│   ├── groups.py                 # GROUPS dict + GROUP_MATCHES dict
│   ├── odds_fetcher.py           # fetch_odds(), load_cached_odds(), load_schedule()
│   ├── results_fetcher.py        # fetch_results() → results_cache.json
│   ├── betfair_fetcher.py        # fetch_betfair(), load_betfair_cache(), get_inplay_matches()
│   ├── unibet_scraper.py         # scrape_unibet(), load_unibet_cache()
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
        ├── betfair_cache.json    # copied from project root by main.py
        └── unibet_cache.json     # copied from project root by unibet_scraper.py
```

---

## Running the calculator
```
python src/main.py                                  # default: normal mode
python src/main.py --mode normal                    # Odds API + results
python src/main.py --mode cached                    # no API calls, load all from cache
python src/main.py --mode live                      # cached odds + fresh results + Betfair
python src/main.py --mode betfair-group --group A   # results + Betfair for all Group A matches
```

## Running the Unibet scraper (separate script)
```
python src/unibet_scraper.py              # scrape all 12 groups
python src/unibet_scraper.py --group A    # scrape one group (for testing)
python src/unibet_scraper.py --debug      # headless=False for DOM inspection
```
Requires one-time setup: `playwright install chromium`

---

## Key module contracts (do not change logic unless explicitly asked)

### simulate_group() → dict
Returns `{'positions': {team: [p1,p2,p3,p4]}, 'pairs': {(first,second): prob}}`
- `positions`: finishing position probabilities per team
- `pairs`: probability of each (1st_team, 2nd_team) ordered combination, sums to 1.0

### compute_advancement_probs(all_sim_results) → dict
Returns `{team: adv_prob}` — probability of advancing to round of 32.
Accounts for: 1st + 2nd automatic qualification + 8 best 3rd-place teams.

### odds_fetcher
- `fetch_odds()` → `(match_odds_dict, credits_dict)`, writes `odds_cache.json`
- `load_cached_odds()` → `(match_odds_dict, fetched_at_str)` or `(None, None)`
- `load_schedule()` → `{(team_a, team_b): date_str}`

### results_fetcher
- `fetch_results()` → `{(home, away): (p_home, p_draw, p_away)}` with certainty values

### betfair_fetcher
- `fetch_betfair(groups_filter=None, fetch_match_odds=True)` → dict, writes betfair_cache.json
- `load_betfair_cache()` → dict (empty structure if not found)
- `get_inplay_matches(betfair_data)` → list of (home, away) tuples

### unibet_scraper
- `scrape_unibet(groups=None)` → dict, writes unibet_cache.json + docs/data/unibet_cache.json
- `load_unibet_cache()` → dict (empty structure if not found)

### Priority order for match probabilities
1. Completed result from `results_cache.json`
2. Betfair in-play odds (when applicable per mode)
3. Odds API odds from `odds_cache.json`
4. Fallback `(1/3, 1/3, 1/3)`

---

## group_rankings.json schema
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
          "adv_prob": 0.753,
          "bf_group_winner_odds": 1.85,
          "bf_to_qualify_odds": 1.25,
          "ub_group_winner_odds": 2.50,
          "ub_fourth_place_odds": 5.00
        }
      ],
      "pairs": [
        {"first": "Mexico", "second": "South Korea", "prob": 0.312, "ub_odds": 3.10}
      ],
      "matches": [
        {
          "home": "Mexico",
          "away": "South Korea",
          "date": "2026-06-12T18:00:00",
          "p_home": 0.45,
          "p_draw": 0.28,
          "p_away": 0.27,
          "result": null,
          "inplay": false
        }
      ]
    }
  }
}
```

Field notes:
- `probs`: `[p_1st, p_2nd, p_3rd, p_4th]`, sum to 1.0
- `adv_prob`: probability of advancing to round of 32
- `pairs`: all 12 ordered (1st, 2nd) combinations sorted by prob descending, sum to 1.0
- `bf_*` fields: Betfair best back decimal odds, `null` if unavailable
- `ub_group_winner_odds`: Unibet decimal odds for winning the group, `null` if unavailable
- `ub_fourth_place_odds`: Unibet decimal odds for finishing 4th, `null` if unavailable
- `pairs[].ub_odds`: Unibet decimal odds for that ordered pair, `null` if unavailable
- `matches[].result`: `null` / `"home"` / `"draw"` / `"away"`
- `matches[].inplay`: `true` if Betfair reports match as currently in-play
- Teams sorted by `probs[0]` descending; groups sorted A–L

---

## Betfair integration

### Environment variables (in .env)
```
BETFAIR_APP_KEY=...
BETFAIR_USERNAME=...
BETFAIR_PASSWORD=...
```

### betfair_fetcher.py
Uses `betfairlightweight` with non-certificate login (no SSL cert files required).
Competition resolved via `listCompetitions` where name contains `'World Cup'`.
Markets fetched in batches of 40 with `virtualise=False`.

#### betfair_cache.json schema
```json
{
  "fetched": "2026-06-10T14:32:00",
  "match_odds": {
    "Mexico|South Korea": {"home": 2.10, "draw": 3.40, "away": 3.60, "inplay": false}
  },
  "group_winner": {
    "A": {"Mexico": 1.85, "South Korea": 3.20, "South Africa": 8.00, "Czechia": 6.50}
  },
  "to_qualify": {
    "A": {"Mexico": 1.25, "South Korea": 1.90, "South Africa": 3.50, "Czechia": 2.80}
  }
}
```

### Running modes

| Mode | Odds API | Results | Betfair match odds | Betfair winner/qualify |
|---|---|---|---|---|
| `cached` | load cache | load cache | fetch fresh (all) | fetch fresh |
| `normal` | fetch fresh | fetch fresh | fetch fresh (all) | fetch fresh |
| `live` | load cache | fetch fresh | fetch fresh (all) | fetch fresh |
| `betfair-group` | load cache | fetch fresh | fetch fresh (one group) | fetch fresh (all groups) |

---

## Unibet scraper

### unibet_scraper.py
Playwright + Chromium, headless by default.
Single browser instance for all 12 pages.
1–2 second wait between pages.

#### Group URL mapping
```python
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
```

#### Markets scraped per page
1. **Group winner** — heading contains "Lohkovoittaja" or "voittaja"
2. **Finish 4th** — heading contains "Neljäs" or "4." or "viimeinen"
3. **1st/2nd pair** — heading contains "1. ja 2." or "kaksi parasta"
   - Runner format: "Team1 / Team2" or "Team1 & Team2" (both team names extracted)
   - Order preserved: first listed = 1st place, second listed = 2nd place

#### unibet_cache.json schema
```json
{
  "fetched": "2026-06-10T14:32:00",
  "group_winner": {
    "A": {"Mexico": 2.50, "South Korea": 3.20, "South Africa": 8.00, "Czechia": 6.50}
  },
  "fourth_place": {
    "A": {"Mexico": 5.00, "South Korea": 4.00, "South Africa": 2.10, "Czechia": 2.50}
  },
  "pairs": {
    "A": {
      "Mexico|South Korea": 3.10,
      "South Korea|Mexico": 4.50,
      "Mexico|South Africa": 8.00
    }
  }
}
```

---

## Frontend flagging (app.js + styles.css)

### Threshold controls
Two number inputs in page header (default: flag=20%, super-flag=50%).
Re-evaluates all flags client-side on change — no refetch.

### Flag condition (same for both sources)
```javascript
const pct = (source_odds - 1/our_prob) / (1/our_prob);
// flag if pct >= flagT/100, super-flag if pct >= superT/100
```
Flag when source odds are HIGHER than our implied odds (source thinks less likely = value).

### Visual treatment
- **Betfair flags**: amber/red left border (4px)
- **Unibet flags**: amber/red right border (4px)
- Both can show simultaneously on the same cell
- Superscript shows source and odds: `ᴮᶠ1.85` and/or `ᵁᴮ2.50`
- Display value matches current page mode (% or decimal odds)

### Cells where flags apply
- `1st` cell: Betfair group_winner + Unibet group_winner
- `Adv` cell: Betfair to_qualify (no Unibet equivalent)
- `4th` cell: Unibet fourth_place (no Betfair equivalent)
- Pair rows: Unibet pair odds vs our pair prob

### In-play indicator
🔴 LIVE badge on any match in match list where `inplay === true`.

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
- All cache files stay in project root; `docs/data/` copies are for frontend access only
- `docs/data/` path used throughout (not `web/data/`)
- `.env` in project root; loaded via `Path(__file__).parent.parent / '.env'`
- Cache file paths use `Path(__file__).parent.parent / 'filename.json'`
- `.gitignore`: includes `.env`; does NOT ignore cache files or `docs/data/`
