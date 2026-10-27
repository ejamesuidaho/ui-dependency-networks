# Tier A Validation — Summary


- Degrees compared: **109**
- Degrees with **zero** disagreement: **109** (100.0%)
- Degrees with small disagreement (1–3): **0** (0.0%)
- Degrees with large disagreement (>3): **0** (0.0%)

- Pages missing in production dataset: **0**
- Pages missing in BS4 parse (no cache or no section): **0**
- Pages lacking a `requirementstext` section: **1**

## Course context counts

- `match`: 4773
- `match_choice`: 1674
- `match_elective_menu`: 1059
- `match_required`: 2040

## Context mismatch types (production vs independent)


## Threshold

- Pass: ≥ 95% of degrees show **zero** disagreement in *required* courses
- Pass: total *required*-bucket mismatches ≤ 2% of compared courses

See `parse_diff.md` for per-degree detail.


## Result

- Threshold A (≥95% degrees zero-diff): **PASS** (100.0%)
- Threshold B (≤2% required-context mismatches): **PASS** (0/2040 = 0.00%)

**Overall: PASS** — production parser output is fully consistent with an independent BeautifulSoup-based re-parse at course-code granularity and context granularity.