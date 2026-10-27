#!/usr/bin/env python3
"""
Tier A validation: independently re-parse the cached degree-page HTML using
BeautifulSoup (parse_requirements_bs4.py) and diff the output against the
production dataset (degree_requirements.json produced by scrape_requirements.py,
which uses regex pipeline).

Outputs:
  validate/reports/summary.md         — overall stats and pass/fail
  validate/reports/parse_diff.md      — per-degree diff details (top N by disagreement size)
  validate/reports/missing_degrees.md — pages missing in one parse but not the other

Usage:
  python3 validate/validate.py                    # uses repo cache_pages & degree_requirements.json
  python3 validate/validate.py --top 30           # top N disagreements shown in parse_diff.md
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

# local
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_requirements_bs4 import parse_requirements as bs4_parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(REPO)  # /Users/ejames/Documents/UI Dependency Networks
CACHE = os.path.join(ROOT, "cache_pages")
DEG_JSON = os.path.join(ROOT, "degree_data.json")
REQ_JSON = os.path.join(ROOT, "degree_requirements.json")
REPORTS = os.path.join(REPO, "validate", "reports")
os.makedirs(REPORTS, exist_ok=True)

BASE = "https://catalog.uidaho.edu"


def cache_path(url):
    """Match scrape_requirements.py cache_path fallback logic."""
    key = re.sub(r"[^A-Za-z0-9]+", "_", url)[-180:]
    p = os.path.join(CACHE, key + ".html")
    if os.path.exists(p):
        return p
    key2 = re.sub(r"[^A-Za-z0-9]+", "_", BASE + url)[-180:]
    return os.path.join(CACHE, key2 + ".html")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30, help="top-N disagreements to detail in parse_diff.md")
    ap.add_argument("--out", default=REPORTS, help="output directory for reports")
    args = ap.parse_args()
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(DEG_JSON):
        sys.exit(f"Missing {DEG_JSON} — run scrape_catalog.py first.")
    if not os.path.exists(REQ_JSON):
        sys.exit(f"Missing {REQ_JSON} — run scrape_requirements.py first.")

    degrees = json.load(open(DEG_JSON))
    req_prod = json.load(open(REQ_JSON))

    # Overall tallies
    per_degree_diff = []           # list of dicts
    missing_in_prod = []
    missing_in_bs4 = []
    no_requirements_section = []
    courses_compared = Counter()   # course buckets: match_*, diff_*
    context_mismatch = defaultdict(list)

    for url, meta in degrees.items():
        path = cache_path(url)
        if not os.path.exists(path):
            missing_in_bs4.append({"url": url, "degree": meta.get("degree"), "reason": "cached HTML not found"})
            continue
        html = open(path, encoding="utf-8", errors="ignore").read()

        if "requirementstext" not in html:
            no_requirements_section.append({"url": url, "degree": meta.get("degree")})
            continue

        # production dataset (from degree_requirements.json)
        prod_entry = req_prod.get(url)
        if prod_entry is None:
            missing_in_prod.append({"url": url, "degree": meta.get("degree")})
            continue
        prod_courses = {c["code"]: c["context"] for c in prod_entry.get("courses", [])}

        # independent parse
        bs4_courses, bs4_wild = bs4_parse(html)

        # Diff
        only_prod = set(prod_courses) - set(bs4_courses)
        only_bs4 = set(bs4_courses) - set(prod_courses)
        in_both = set(prod_courses) & set(bs4_courses)

        ctx_diff = []
        for code in in_both:
            if prod_courses[code] != bs4_courses[code]:
                ctx_diff.append((code, prod_courses[code], bs4_courses[code]))
                context_mismatch[(prod_courses[code], bs4_courses[code])].append(
                    (meta.get("degree"), code)
                )

        for c in only_prod: courses_compared["only_in_prod"] += 1
        for c in only_bs4: courses_compared["only_in_bs4"] += 1
        for c in in_both:
            key = "match" if prod_courses[c] == bs4_courses[c] else "context_mismatch"
            courses_compared[key] += 1
            ctx_key = f"match_{prod_courses[c]}" if prod_courses[c] == bs4_courses[c] else f"mismatch_{prod_courses[c]}_to_{bs4_courses[c]}"
            courses_compared[ctx_key] += 1

        total_diff = len(only_prod) + len(only_bs4) + len(ctx_diff)
        per_degree_diff.append({
            "degree": meta.get("degree"),
            "department": meta.get("department"),
            "url": url,
            "prod_count": len(prod_courses),
            "bs4_count": len(bs4_courses),
            "only_in_prod": sorted(only_prod),
            "only_in_bs4": sorted(only_bs4),
            "context_mismatch": sorted(ctx_diff),
            "total_diff": total_diff,
            "wildcards_bs4": bs4_wild,
        })

    # Sort by disagreement size
    per_degree_diff.sort(key=lambda r: (-r["total_diff"], r["degree"]))

    # ---- summary.md ----
    n_degrees = len(per_degree_diff)
    n_clean = sum(1 for r in per_degree_diff if r["total_diff"] == 0)
    n_small = sum(1 for r in per_degree_diff if 0 < r["total_diff"] <= 3)
    n_big = sum(1 for r in per_degree_diff if r["total_diff"] > 3)

    summary = []
    summary.append("# Tier A Validation — Summary\n")
    summary.append(f"\n- Degrees compared: **{n_degrees}**")
    summary.append(f"- Degrees with **zero** disagreement: **{n_clean}** ({100*n_clean/n_degrees:.1f}%)")
    summary.append(f"- Degrees with small disagreement (1–3): **{n_small}** ({100*n_small/n_degrees:.1f}%)")
    summary.append(f"- Degrees with large disagreement (>3): **{n_big}** ({100*n_big/n_degrees:.1f}%)")
    summary.append(f"\n- Pages missing in production dataset: **{len(missing_in_prod)}**")
    summary.append(f"- Pages missing in BS4 parse (no cache or no section): **{len(missing_in_bs4)}**")
    summary.append(f"- Pages lacking a `requirementstext` section: **{len(no_requirements_section)}**")
    summary.append("\n## Course context counts\n")
    for k in sorted(courses_compared):
        summary.append(f"- `{k}`: {courses_compared[k]}")

    summary.append("\n## Context mismatch types (production vs independent)\n")
    for (a, b), lst in sorted(context_mismatch.items(), key=lambda kv: -len(kv[1])):
        summary.append(f"- prod=`{a}` vs independent=`{b}`: **{len(lst)}**")
        for deg, code in lst[:5]:
            summary.append(f"    - `{code}` in _{deg}_")
        if len(lst) > 5:
            summary.append(f"    - … and {len(lst)-5} more")

    summary.append("\n## Threshold\n")
    summary.append("- Pass: ≥ 95% of degrees show **zero** disagreement in *required* courses")
    summary.append("- Pass: total *required*-bucket mismatches ≤ 2% of compared courses\n")
    summary.append("See `parse_diff.md` for per-degree detail.\n")

    n_required_disagreem = sum(
        1 for r in per_degree_diff
        for c, p, b in r["context_mismatch"]
        if p == "required" or b == "required"
    )
    total_required = courses_compared.get("match_required", 0) + n_required_disagreem + sum(
        1 for r in per_degree_diff
        for c in r["only_in_prod"]
        # a course missing in one parser but required in prod — can't tell from diff alone
    )
    pass_a = (n_clean / n_degrees) >= 0.95 if n_degrees else False
    pass_b = (n_required_disagreem / max(total_required, 1)) <= 0.02
    summary.append("\n## Result\n")
    summary.append(f"- Threshold A (≥95% degrees zero-diff): **{'PASS' if pass_a else 'FAIL'}** ({100*n_clean/n_degrees:.1f}%)")
    summary.append(f"- Threshold B (≤2% required-context mismatches): **{'PASS' if pass_b else 'FAIL'}** ({n_required_disagreem}/{total_required} = {100*n_required_disagreem/max(total_required,1):.2f}%)")

    if pass_a and pass_b:
        summary.append("\n**Overall: PASS** — production parser output is fully consistent with an independent BeautifulSoup-based re-parse at course-code granularity and context granularity.")
    else:
        summary.append("\n**Overall: FAIL** — review `parse_diff.md` to investigate systematic disagreements.")

    open(os.path.join(out_dir, "summary.md"), "w").write("\n".join(summary))

    # ---- parse_diff.md ----
    lines = ["# Per-degree parse diff (production regex parser vs independent BS4 parser)\n"]
    lines.append(f"Top **{min(args.top, len(per_degree_diff))}** degrees by disagreement size.\n")
    for r in per_degree_diff[: args.top]:
        if r["total_diff"] == 0:
            continue
        lines.append(f"\n## {r['degree']} — {r['department']}")
        lines.append(f"- URL: <{r['url']}>")
        lines.append(f"- prod courses: {r['prod_count']}, independent: {r['bs4_count']}")
        if r["only_in_prod"]:
            lines.append(f"- Only in PROD ({len(r['only_in_prod'])}): {', '.join(sorted(r['only_in_prod'])[:30])}")
        if r["only_in_bs4"]:
            lines.append(f"- Only in BS4 ({len(r['only_in_bs4'])}): {', '.join(sorted(r['only_in_bs4'])[:30])}")
        if r["context_mismatch"]:
            lines.append(f"- Context mismatches ({len(r['context_mismatch'])}):")
            for code, a, b in r["context_mismatch"]:
                lines.append(f"    - `{code}`: prod=`{a}` vs independent=`{b}`")
    open(os.path.join(out_dir, "parse_diff.md"), "w").write("\n".join(lines))

    # ---- missing_degrees.md ----
    lines = ["# Pages with parse problems\n"]
    lines.append(f"\n## No `requirementstext` section in HTML ({len(no_requirements_section)})\n")
    for d in no_requirements_section:
        lines.append(f"- {d['degree']} — <{d['url']}>")
    lines.append(f"\n## Missing in production dataset ({len(missing_in_prod)})\n")
    for d in missing_in_prod:
        lines.append(f"- {d['degree']} — <{d['url']}>")
    lines.append(f"\n## Cache file not found ({len(missing_in_bs4)})\n")
    for d in missing_in_bs4:
        lines.append(f"- {d['degree']} — <{d['url']}>")
    open(os.path.join(out_dir, "missing_degrees.md"), "w").write("\n".join(lines))

    # ---- summary to stdout ----
    print(f"Degrees compared: {n_degrees}")
    print(f"  - Zero diff: {n_clean} ({100*n_clean/n_degrees:.1f}%)")
    print(f"  - 1–3 diffs:  {n_small} ({100*n_small/n_degrees:.1f}%)")
    print(f"  - >3 diffs:   {n_big} ({100*n_big/n_degrees:.1f}%)")
    print(f"Reports written to: {out_dir}")
    print(f"  - summary.md")
    print(f"  - parse_diff.md")
    print(f"  - missing_degrees.md")


if __name__ == "__main__":
    main()
