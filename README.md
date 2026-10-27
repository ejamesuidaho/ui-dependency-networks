# University of Idaho Cross-Department Course Dependency Explorer

An interactive visualization tool built from the **2026-2027 University of Idaho catalog** that shows which courses from one academic unit (department/school/program) appear in the **degree maps** of other units.

**Live demo:** [open `index.html`](https://YOUR-USERNAME.github.io/ui-dependency-networks/) *(after Pages is enabled)*

## What's Included

- **`index.html`** — Self-contained interactive D3 app (3 views: Network Map, Chord Diagram, Degree Explorer) with all data embedded. Works offline.
- **`app/network-data.js`** — The dataset as a JS module (`window.NETWORK_DATA`), used by the app.
- **`app/network_data.json`** — Same data as JSON, for analysis or reuse.
- **`scripts/scrape_catalog.py`** — Crawls https://catalog.uidaho.edu/colleges-related-units/, extracts degree maps & course listings → `degree_data.json`
- **`scripts/build_network.py`** — Maps course prefixes → owning units → `network_data.json` / `network-data.js`
- **`data/`** — Raw catalog cache (for auditing/scaling runs)

## Data Summary (as generated)

| Metric | Value |
|--------|-------|
| Degree programs analyzed | 110 |
| Academic units (departments/schools) | 44 |
| Course-subject dependencies (degree → subject) | 1,143 |
| Cross-unit course links (aggregated)** | 354 |

**Most depended-upon units** (courses listed in other units' degree maps): English (374), Global Studies/Languages (350), Math & Statistical Science (275), and Chemistry (212).

## Methodology

1. Scrape every undergraduate Degree Map ("Plan of Study" grid) from each degree page in the catalog.
2. Extract all course listings visible in those grids (e.g., `MATH 1170`, `COMM 1101`).
3. Map each course prefix (e.g., `MATH`, `COMM`) to its home unit using the catalog course-catalog index.
4. Aggregate: for each degree → its course prefixes; for each unit → unit pairs by linking degree-owner to course-owner.

**Note:** the dataset captures *explicitly listed* courses in degree maps. Free-choice "select from approved list" or generic "Ways of Knowing" requirements aren't attributed.

## Regenerating the data for a new catalog year

```bash
python3 scripts/scrape_catalog.py   # writes degree_data.json
python3 scripts/build_network.py      # writes network_data.json + app/network-data.js
# optionally, re-embed data into index.html
```

## License

Data sourced from the publicly available University of Idaho catalog (catalog.uidaho.edu). Use in accordance with catalog terms. App is a custom goose-generated artifact.
