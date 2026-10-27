#!/usr/bin/env python3
"""
Scrape University of Idaho catalog DEGREE REQUIREMENTS (curriculum requirements,
not 4-year degree maps) to build a cross-department course dependency network.

For each degree, we parse the "requirementstext" HTML section, walking the
course-list tables row by row and classifying every course mention by its
curricular context:

  - "required"      : individually named required course (default)
  - "choice"        : a row marked as an OR-alternative (class contains 'orclass')
  - "elective_menu" : course appears under an areaheader/areasubheader whose
                      label indicates a credit-menu ('elective', 'select N credits',
                      'choose', 'pick', 'option', 'approved ... courses')

Wildcard level references like "CS 4000-level" are discarded.

Output: degree_requirements.json
  { url: {degree, department, college, url,
          courses: [{code, context}],   # context in {required, choice, elective_menu}
          wildcard_refs: [...] } }
"""

import re
import json
import os
import sys
from collections import Counter

CACHE_DIR = "cache_pages"
BASE = "https://catalog.uidaho.edu"

COURSE_RE = re.compile(r"showCourse\(this,\s*'([A-Z]{2,5}) (\d{3,4}[A-Z]?)'\)")
MENU_WORDS = re.compile(
    r"\b(elective|select\s+\d|select\s+one|select\s+two|select\s+three|choose|"
    r"pick\s+\d|option\b|approved|credits?\s+from|from\s+the\s+following|"
    r"any\s+.{0,40}level|emphasis|concentration\s+area|support\s+area|"
    r"track\b|certificate\s+option)\b",
    re.I,
)
CHOICE_WORDS = re.compile(r"\bselect\s+one\b|\bchoose\s+one\b|\bone\s+of\s+the\s+following\b", re.I)


def cache_path(url):
    key = re.sub(r"[^A-Za-z0-9]+", "_", url)[-180:]
    p = os.path.join(CACHE_DIR, key + ".html")
    if os.path.exists(p):
        return p
    key2 = re.sub(r"[^A-Za-z0-9]+", "_", BASE + url)[-180:]
    return os.path.join(CACHE_DIR, key2 + ".html")


def strip_tags(html):
    return re.sub(r"<[^>]+>", " ", html)


def parse_requirements(html):
    """Walk requirementstext section, return (courses_with_context, wildcards)."""
    m = re.search(
        r'<a name="requirementstext".*?</a>(.*?)(?=<a name="degreemaptext|<a name="[a-z]+text|</body)',
        html, re.S,
    )
    if not m:
        return [], []
    sec = m.group(1)

    # Wildcards: code immediately followed by "-level" in the visible text
    wild = set()
    for cm in re.finditer(
        r"showCourse\(this,\s*'([A-Z]{2,5}) (\d{3,4}[A-Z]?)'\)[^<]*</a>\s*[-\s]*level",
        sec, re.I,
    ):
        wild.add(f"{cm.group(1)} {cm.group(2)}")

    # Walk tables row by row. Only use the first big course-list table region;
    # requirement sections may include several tables.
    courses = {}  # code -> context (first-seen conservative: keep most specific)
    in_menu = False
    menu_is_choice = False

    # Tokenize: iterate over <tr> blocks and header-comment spans in document order
    tokens = re.finditer(
        r"<tr[^>]*class=\"([^\"]*)\"[^>]*>(.*?)</tr>",
        sec, re.S,
    )
    for tm in tokens:
        tclass, row = tm.group(1), tm.group(2)
        rowtext = re.sub(r"\s+", " ", strip_tags(row)).strip()
        row_courses = [f"{a} {b}" for a, b in COURSE_RE.findall(row)]

        is_header = "areaheader" in tclass or "areasubheader" in tclass
        is_or = "orclass" in tclass

        if is_header:
            # Determine if this header opens an elective menu
            if MENU_WORDS.search(rowtext):
                in_menu = True
                menu_is_choice = bool(CHOICE_WORDS.search(rowtext))
            else:
                # a plain requirement group header closes previous menu
                in_menu = False
                menu_is_choice = False
            # headers themselves can contain courses (rare); skip
            continue

        if not row_courses:
            # a comment row that might itself open/close a menu
            if in_menu is False and MENU_WORDS.search(rowtext):
                in_menu = True
                menu_is_choice = bool(CHOICE_WORDS.search(rowtext))
            continue

        for code in row_courses:
            if code in wild:
                continue
            if code in courses:
                continue  # first occurrence wins (core appears before menus usually)
            if is_or:
                ctx = "choice"
            elif in_menu:
                ctx = "choice" if menu_is_choice else "elective_menu"
            else:
                ctx = "required"
            courses[code] = ctx

    return courses, sorted(wild)


def extract(url):
    path = cache_path(url)
    if not os.path.exists(path):
        return {}, []
    html = open(path, encoding="utf-8", errors="ignore").read()
    courses, wild = parse_requirements(html)
    if isinstance(courses, list):
        courses = {c["code"]: c["context"] for c in courses}
    return courses, wild


def main():
    deg = json.load(open("degree_data.json"))
    out = {}
    stats = Counter()
    no_req_section = []
    for url, d in deg.items():
        courses, wild = extract(url)
        if not courses and not wild:
            # check whether the page had a requirementstext section at all
            path = cache_path(url)
            html = open(path, encoding="utf-8", errors="ignore").read() if os.path.exists(path) else ""
            if "requirementstext" not in html:
                no_req_section.append(d["degree"])
        items = [{"code": c, "context": ctx} for c, ctx in sorted(courses.items())]
        out[url] = {
            "degree": d["degree"],
            "department": d["department"],
            "college": d["college"],
            "url": d["url"],
            "courses": items,
            "wildcard_refs": wild,
        }
        for it in items:
            stats[it["context"]] += 1

    with open("degree_requirements.json", "w") as f:
        json.dump(out, f, indent=1)

    print(f"Degrees processed: {len(out)}")
    print(f"Context counts: required={stats['required']}, choice={stats['choice']}, elective_menu={stats['elective_menu']}")
    print(f"Degrees lacking a requirementstext section: {len(no_req_section)}")
    for n in no_req_section:
        print("   -", n)


if __name__ == "__main__":
    main()
