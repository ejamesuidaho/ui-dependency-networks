# Validation Reports

## Result

**Tier A validation: PASS** — production parser output is fully consistent with an independent re-parse of the same HTML using a different parsing strategy.

| Check | Threshold | Result |
|---|---|---|
| Degrees with zero course-code disagreement | ≥ 95% | **100%** (109/109) |
| Required-context mismatches | ≤ 2% | **0%** (0/2,040) |

## What was validated

- 110 degree pages from catalog.uidaho.edu (2026–27 catalog)
- 4,773 course-extractions across three context buckets:
  - `required`: 2,040
  - `choice`: 1,674
  - `elective_menu`: 1,059

## Two parsers

| Parser | File | Strategy |
|---|---|---|
| **Production** | `../scripts/scrape_requirements.py` | regex over HTML, course codes from `showCourse(this,'SUBJ NUM')` onclick attributes |
| **Independent (Tier A)** | `parse_requirements_bs4.py` | BeautifulSoup DOM walk, course codes from anchor `href` query strings and visible text |

Both parsers walk each `sc_courselist` table row by row, classify rows as `areaheader`/`orclass`, and apply the same MENU_WORDS/CHOICE_WORDS regexes for context classification. So the structural logic is shared, but course-code extraction and DOM traversal are independent.

## Reports

- `summary.md` — overall result + per-context counts
- `parse_diff.md` — per-degree course-set diffs between the two parsers
- `text_diff.md` — coarse text-extraction comparison (regardless of course-link markup; expected to differ slightly because prose mentions in the requirement text produce "extra" codes that aren't actual requirements)
- `missing_degrees.md` — pages missing in one parse or lacking a `requirementstext` section (currently only `Physics (B.S.)`, which is a known data note: that page has no curriculum requirements tab and uses only its degree map)

## Re-running

```bash
cd /Users/ejames/Documents/UI\ Dependency\ Networks
python3 ui-dependency-networks/validate/validate.py
python3 ui-dependency-networks/validate/validate_text.py
```

Re-scrape the catalog and re-validate when the catalog changes (each term).

## Next steps (Tier B / Tier C)

Tier A only confirms the parser extracts what the catalog HTML encodes. It does **not** confirm:

- The prefix → unit attribution in `../scripts/build_network_req.py` is correct (e.g., is `MVSC` Movement Sciences and not Music?)
- The catalog itself encodes the requirement you think it does (e.g., a "select 6 credits from the following list" might really be 9)

For those, run **Tier B** (stratified manual audit of 12 degrees) and optionally **Tier C** (unit reconciliation).
