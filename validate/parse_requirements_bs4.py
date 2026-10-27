#!/usr/bin/env python3
"""
Independent requirements parser using BeautifulSoup — used by validate.py to
cross-check the regex-based production parser (scrape_requirements.py).

Same public interface: parse_requirements(html) -> (courses_dict, wildcards)
  courses_dict: {course_code: context}   context ∈ {required, choice, elective_menu}
  wildcards:    sorted list of "SUBJ ####"-style codes that are level references
"""

import re
from bs4 import BeautifulSoup

# Independent extractor: read course code from the anchor's visible text or title,
# NOT from the onclick attribute (which the production parser uses).
COURSE_TEXT_RE = re.compile(r"^([A-Z]{2,5})\s+(\d{3,4}[A-Z]?)\b")
HREF_CODE_RE = re.compile(r"/search/\?P=([A-Z]{2,5})%20?(\d{3,4}[A-Z]?)")
# Fallback (matches production): the bubblelink's href has ?P=SUBJ%20NUM
MENU_WORDS = re.compile(
    r"\b(elective|select\s+\d|select\s+one|select\s+two|select\s+three|choose|"
    r"pick\s+\d|option\b|approved|credits?\s+from|from\s+the\s+following|"
    r"any\s+.{0,40}level|emphasis|concentration\s+area|support\s+area|"
    r"track\b|certificate\s+option)\b",
    re.I,
)
CHOICE_WORDS = re.compile(r"\bselect\s+one\b|\bchoose\s+one\b|\bone\s+of\s+the\s+following\b", re.I)


def find_requirements_section(soup):
    """Locate the requirements section and return its tables.

    Structure observed in catalog.uidaho.edu pages: each named section
    (requirementstext, degreemaptext, learningoutcomestext) is wrapped in
    its own <div class="page_content tab_content"> that contains an
    <a name="..."> anchor plus the section's tables. So we just collect
    tables inside the anchor's parent div.
    """
    anchor = soup.find("a", attrs={"name": "requirementstext"})
    if not anchor:
        return None
    parent = anchor.parent
    if parent is None:
        return None
    tables = parent.find_all("table")
    return tables


def extract_course_code(a):
    """Pull a course code from an anchor using ONLY its visible DOM data
    (href query string, or display text). Independent of onclick regex.
    Returns "SUBJ NUM" or None."""
    # 1. href ?P=SUBJ%20NUM
    href = a.get("href", "")
    m = HREF_CODE_RE.search(href)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    # 2. display text: "COMM 1101" style
    text = a.get_text(" ", strip=True)
    m = COURSE_TEXT_RE.match(text)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    # 3. title attr
    title = a.get("title", "")
    m = COURSE_TEXT_RE.match(title)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return None


def parse_requirements(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = find_requirements_section(soup)
    courses = {}
    wild = set()

    if tables is None:
        return courses, []

    # Detect wildcards: any course-like anchor followed by "-level" text
    for a in soup.find_all("a"):
        code = extract_course_code(a)
        if not code:
            continue
        tail = a.next_sibling
        if tail and isinstance(tail, str) and re.match(r"^[\s\-\u2013\u2014]*level", tail, re.I):
            wild.add(code)

    in_menu = False
    menu_is_choice = False

    for table in tables:
        for tr in table.find_all("tr"):
            classes = tr.get("class") or []
            classes = " ".join(classes) if isinstance(classes, list) else str(classes)
            is_header = "areaheader" in classes or "areasubheader" in classes
            is_or = "orclass" in classes
            row_text = tr.get_text(" ", strip=True)

            # courses in row — use only course-link-shaped anchors
            row_courses = []
            for a in tr.find_all("a"):
                cls = a.get("class") or []
                cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)
                # Anchor is a course link if it has class "bubblelink code" OR carries a recognized code
                if "bubblelink" in cls_str or "code" in cls_str:
                    code = extract_course_code(a)
                    if code:
                        row_courses.append(code)

            if is_header:
                if MENU_WORDS.search(row_text):
                    in_menu = True
                    menu_is_choice = bool(CHOICE_WORDS.search(row_text))
                else:
                    in_menu = False
                    menu_is_choice = False
                continue

            if not row_courses:
                # comment row might open/close a menu
                if not in_menu and MENU_WORDS.search(row_text):
                    in_menu = True
                    menu_is_choice = bool(CHOICE_WORDS.search(row_text))
                continue

            for code in row_courses:
                if code in wild:
                    continue
                if code in courses:
                    continue
                if is_or:
                    ctx = "choice"
                elif in_menu:
                    ctx = "choice" if menu_is_choice else "elective_menu"
                else:
                    ctx = "required"
                courses[code] = ctx

    return courses, sorted(wild)


if __name__ == "__main__":
    import sys
    html = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
    courses, wild = parse_requirements(html)
    print(f"Courses: {len(courses)}")
    from collections import Counter
    print("Contexts:", Counter(courses.values()))
    print(f"Wildcards: {len(wild)}")
