# WC2026 Group Stage Ranking Probability Calculator

## Project Goal
Calculate the probability of each team finishing in each position (1st–4th) in their group at the
2026 FIFA World Cup, using betting odds and completed match results. Display results via a static
web site hosted on GitHub Pages.

---

## Current State (as of transition)
The following Python files exist and work correctly — do not change their logic unless explicitly asked:

| File | Purpose |
|---|---|
| `groups.py` | All 12 groups + match pairings (hardcoded) |
| `config.py` | Loads `ODDS_API_KEY` from `.env`; team name alias dict |
| `odds_fetcher.py` | Fetches & normalises h2h odds from The Odds API |
| `results_fetcher.py` | Fetches completed match results; caches in `results_cache.json` |
| `ranking_rules.py` | Points + H2H tiebreaker logic; equal split for remaining ties |
| `simulator.py` | Brute-forces all 3^6=729 combos per group; accumulates position probs |
| `export_html.py` | Writes a self-contained `results.html` (legacy — to be replaced) |
| `main.py` | Entry point: fetch → simulate → print → call export_html |
| `results_cache.json` | Persisted completed match results (do not delete) |
| `requirements.txt` | `requests`, `python-dotenv` |

---

## Target Architecture

### Principle
Python writes JSON data files. A static JS frontend reads those files.
Both live in the same Git repository. GitHub Pages serves the web folder.
Running `main.py` locally and pushing to GitHub is the full deploy cycle.

### Directory structure
```
wc2026/
├── CLAUDE.md
├── requirements.txt
├── .env                        # not committed
├── results_cache.json          # committed
│
├── src/                        # Python — all calculation code
│   ├── config.py
│   ├── groups.py
│   ├── odds_fetcher.py
│   ├── results_fetcher.py
│   ├── ranking_rules.py
│   ├── simulator.py
│   └── main.py                 # writes to web/data/, then exits
│
└── web/                        # served by GitHub Pages
    ├── index.html
    ├── app.js
    ├── styles.css
    └── data/
        └── group_rankings.json # written by main.py
```

### GitHub Pages configuration
- Source: main branch, `/web` folder
- URL pattern: `https://<username>.github.io/<repo>/`

---

## Data Contract: group_rankings.json

`main.py` writes `web/data/group_rankings.json`. The JS frontend reads this file.
This schema must be kept in sync between Python writer and JS reader.

```json
{
  "generated": "2026-06-10T14:32:00",
  "groups": {
    "A": {
      "teams": [
        {
          "name": "Mexico",
          "probs": [0.452, 0.301, 0.164, 0.083]
        }
      ],
      "matches": [
        {
          "home": "Mexico",
          "away": "South Korea",
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

Field notes:
- `probs`: `[p_1st, p_2nd, p_3rd, p_4th]`, all four sum to 1.0
- `matches[].result`: `null` if not yet played, else `"home"` / `"draw"` / `"away"`
- Teams within each group are sorted by `probs[0]` descending (best 1st-place prob first)
- Groups are sorted alphabetically by key (A–L)

---

## Calculation Logic (do not change)

### Match outcome probabilities
- Odds normalised: `p_i = (1/odd_i) / Σ(1/odd_j)`
- Completed match results override odds with certainty: `(1,0,0)`, `(0,1,0)`, or `(0,0,1)`
- Fallback if no odds and no result: `(1/3, 1/3, 1/3)`

### Brute-force enumeration
- `itertools.product(range(3), repeat=6)` → 729 combos
- Joint probability = product of 6 match outcome probabilities
- Accumulate into `{team: [p1, p2, p3, p4]}`

### Tiebreaker rules (in order)
1. Overall points
2. Head-to-head points among only the tied teams
3. Equal split across all still-tied teams and all contested positions

### Points
- Win: 3, Draw: 1 each, Loss: 0

---

## Frontend (web/)

### index.html
Single-page app. On load, fetches `data/group_rankings.json` and renders all 12 group tables.
No build step, no framework — vanilla JS only.

### Display: group tables
Each group card shows:
- Group letter as heading
- Table with columns: Team | 1st | 2nd | 3rd | 4th
- Cells colour-coded by probability (green=1st, blue=2nd, amber=3rd, red=4th)
- Sorted by 1st-place probability descending
- Match results/odds shown below each group table

### styles.css
Responsive grid layout (auto-fill, minmax 310px). Cards with subtle shadow.
Same visual style as the current export_html.py output.

---

## Python main.py responsibilities (after transition)
1. Fetch odds (`odds_fetcher.py`)
2. Fetch/cache results (`results_fetcher.py`)
3. Merge: results override odds
4. Simulate all 12 groups (`simulator.py`)
5. Run sanity checks (column and row sums ≈ 1.0)
6. Write `web/data/group_rankings.json`
7. Print summary to console (keep existing print logic)
8. `export_html.py` is retired — delete it

---

## Key Constraints
- `results_cache.json` stays in project root (not in `src/`)
- All imports in `src/` files must work after moving into the subfolder — use `sys.path` insertion at the top of `main.py`: `sys.path.insert(0, os.path.dirname(__file__))`
- `web/data/` directory must be created by `main.py` if it does not exist (`os.makedirs(..., exist_ok=True)`)
- Do not change `results_cache.json` format — existing cached results must survive the transition
- `.env` stays in project root; after moving `config.py` to `src/`, load it with: `load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')`
- `results_cache.json` path in `results_fetcher.py` must also be updated to `Path(__file__).parent.parent / 'results_cache.json'`
- `.gitignore` must include `.env` and must NOT ignore `results_cache.json` or `web/data/`
