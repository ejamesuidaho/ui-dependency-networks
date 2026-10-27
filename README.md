# University of Idaho Cross-Department Course Dependency Explorer

Interactive visualization tools built from the **2026-2027 University of Idaho catalog**, showing which courses from one academic unit appear in the curricula of other units.

## Two Analytical Versions

| Version | App | Source data | Use case |
|---------|-----|-------------|----------|
| **v0.1** | `index.html` | Degree Maps (4-year plans of study) | What students actually schedule |
| **v0.2** | `requirements-explorer.html` | Curriculum Requirements (degree requirement tables) | Full curricular structure incl. elective menus |

Both are self-contained HTML files — open in any browser, no server needed.

## v0.2 New Features

- **Requirement-context classification**: every course mention tagged as `required`, `choice` (constrained "select one" sets), or `elective_menu` (broad "select N credits" lists)
- **Weighting toggle** in the app: *Core only* (required + choice, 1,883 course links) vs *Core + elective menus* (2,375 links)
- **396 unit→unit links** across **50 units** (vs 354 in v0.1)

## Repository Contents

- `index.html` — v0.1 degree-map explorer (self-contained)
- `requirements-explorer.html` — v0.2 requirements explorer (self-contained)
- `network-data.js`, `app/network_data.json` — v0.1 dataset
- `network-requirements.js`, `app/network_requirements.json` — v0.2 dataset
- `scripts/scrape_catalog.py` — degree-map crawler → `degree_data.json`
- `scripts/scrape_requirements.py` — requirements parser → `degree_requirements.json`
- `scripts/build_network.py`, `scripts/build_network_req.py` — network builders

## Data Summary

| Metric | v0.1 (degree maps) | v0.2 (requirements) |
|--------|-------------------|---------------------|
| Degrees analyzed | 110 | 110 |
| Academic units | 44 | 50 |
| Degree→subject edges | 1,143 | 1,087 |
| Unit→unit links | 354 | 396 |
| Course listings | 4,210 | 4,773 (2,040 required, 1,674 choice, 1,059 elective menu) |

## Methodology

1. Scrape every undergraduate degree page from catalog.uidaho.edu
2. v0.1: extract courses from "Degree Map" plan-of-study grids
3. v0.2: extract courses from "Requirements" curriculum tables with context classification (wildcard level-references like "CS 4000-level" excluded)
4. Map course prefixes → owning units via the catalog course index + curated mapping
5. Aggregate to unit→unit dependency edges; v0.2 tracks required/choice/elective-menu breakdown separately

**Caveat:** Both datasets capture *explicitly listed* courses. Generic "Ways of Knowing" or "approved elective" placeholders aren't attributed to any unit.

## Regenerating

```bash
python3 scripts/scrape_catalog.py        # v0.1
python3 scripts/build_network.py
python3 scripts/scrape_requirements.py   # v0.2
python3 scripts/build_network_req.py
```
