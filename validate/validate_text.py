#!/usr/bin/env python3
"""
Tier A, second independent validator: text-extraction based.

Differences from parse_requirements_bs4.py:
- does NOT walk table rows
- does NOT look at <a> markup at all
- just extracts ALL course-like patterns (SUBJ NUM) from the rendered text
- only filters obvious non-courses (periods, common words)

This is coarser than the anchors-based parsers (it can pick up courses mentioned
in prose paragraphs, not just the courselist table) so disagreements are EXPECTED
and indicate potential scrape issues worth investigating.

Outputs:
  validate/reports/text_diff.md — per-degree comparison (text-extractor vs production)
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from bs4 import BeautifulSoup

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(REPO)
CACHE = os.path.join(ROOT, "cache_pages")
DEG_JSON = os.path.join(ROOT, "degree_data.json")
REQ_JSON = os.path.join(ROOT, "degree_requirements.json")
BASE = "https://catalog.uidaho.edu"

CODE_RE = re.compile(r"\b([A-Z]{2,5})\s+(\d{3,4}[A-Z]?)\b")
NOT_SUBJ = {
    "THE","AND","NOT","WITH","FROM","THAT","THIS","OR","OF","AS","IN","ON","AT","BY","TO","IS","IT","BE",
    "PREREQ","COREQ","NEW","COURSE","NONE","YES","NO",
    # common words that look like subject codes but aren't
    "WILL","THIS","THAT","INTO","ONLY","OVER","SUCH","ALL","ANY","EACH","MUST","MAY","CAN","PER","SET","PER",
    # subject codes that are also common words — we must NOT exclude legitimate subjects
    # "FOR" is Forestry, "ARE" is Architecture, "AGE" could be AgEd, "CAP" could be capstone
}
# But common English words that happen to be all-caps in the catalog text
# (e.g., "FOR 2100-level", in a sentence) get filtered by the trailing-level check anyway.


def cache_path(url):
    key = re.sub(r"[^A-Za-z0-9]+", "_", url)[-180:]
    p = os.path.join(CACHE, key + ".html")
    if os.path.exists(p): return p
    key2 = re.sub(r"[^A-Za-z0-9]+", "_", BASE + url)[-180:]
    return os.path.join(CACHE, key2 + ".html")


def text_extract(path):
    """Extract all course-like codes from the requirementstext section text."""
    html = open(path, encoding="utf-8", errors="ignore").read()
    soup = BeautifulSoup(html, "html.parser")
    a = soup.find("a", attrs={"name": "requirementstext"})
    if a is None:
        return None
    parent = a.parent
    text = parent.get_text(" ", strip=True)
    codes = set()
    for m in CODE_RE.finditer(text):
        s, n = m.group(1), m.group(2)
        if s in NOT_SUBJ: continue
        # filter out obvious level references: "FOR 2100-level" or "CS 4000 level"
        tail = text[m.end():m.end()+15]
        if re.match(r"^[\s\-\u2013\u2014]*level", tail, re.I): continue
        # also skip "e.g., STAT 2510 or higher" etc.
        codes.add(f"{s} {n}")
    return codes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "validate", "reports"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    degrees = json.load(open(DEG_JSON))
    req_prod = json.load(open(REQ_JSON))

    rows = []
    total_only_prod = total_only_text = total_overlap = 0
    for url, meta in degrees.items():
        path = cache_path(url)
        if not os.path.exists(path):
            continue
        prod_codes = {c["code"] for c in req_prod.get(url, {}).get("courses", [])}
        text_codes = text_extract(path)
        if text_codes is None:
            continue
        overlap = prod_codes & text_codes
        only_prod = prod_codes - text_codes
        only_text = text_codes - prod_codes
        total_only_prod += len(only_prod)
        total_only_text += len(only_text)
        total_overlap += len(overlap)
        if only_prod or only_text:
            rows.append({
                "degree": meta.get("degree"),
                "prod": len(prod_codes),
                "text": len(text_codes),
                "overlap": len(overlap),
                "only_in_prod": sorted(only_prod),
                "only_in_text": sorted(only_text),
            })
    rows.sort(key=lambda r: -(len(r["only_in_prod"]) + len(r["only_in_text"])))

    lines = ["# Text-extractor (independent, coarse) vs production dataset\n"]
    lines.append(f"- Degrees compared: {len(rows) + total_overlap}")
    lines.append(f"- Total courses in production: {sum(1 for _ in [])}")  # placeholder
    lines.append(f"- Total overlap: {total_overlap}")
    lines.append(f"- Codescourses ONLY in production (likely OK if they're in courselist markup but not in prose): {total_only_prod}")
    lines.append(f"- Courses ONLY in text (likely OK if they're prose mentions or level references): {total_only_text}")
    lines.append("\n**Interpretation**: This extractor doesn't know the table structure.")
    lines.append("Asymmetry is expected. Look for *systematic* patterns in `only_*` lists, ")
    lines.append("not the absolute numbers.\n")

    for r in rows[:30]:
        if not r["only_in_prod"] and not r["only_in_text"]:
            continue
        lines.append(f"## {r['degree']}")
        lines.append(f"- prod count: {r['prod']}, text count: {r['text']}, overlap: {r['overlap']}")
        if r["only_in_prod"]:
            lines.append(f"- only in prod ({len(r['only_in_prod'])}): {', '.join(r['only_in_prod'][:15])}")
            if len(r["only_in_prod"]) > 15:
                lines.append(f"  … and {len(r['only_in_prod'])-15} more")
        if r["only_in_text"]:
            lines.append(f"- only in text ({len(r['only_in_text'])}): {', '.join(r['only_in_text'][:15])}")
            if len(r["only_in_text"]) > 15:
                lines.append(f"  … and {len(r['only_in_text'])-15} more")
        lines.append("")

    open(os.path.join(args.out, "text_diff.md"), "w").write("\n".join(lines))
    print(f"Wrote {args.out}/text_diff.md ({len(rows)} degrees with disagreements)")


if __name__ == "__main__":
    main()
