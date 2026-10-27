#!/usr/bin/env python3
"""
Scrape University of Idaho catalog to build cross-department course dependency data.

Pipeline:
1. Fetch colleges-related-units page -> all department URLs
2. For each department, find undergraduate degree program pages (B.* degrees)
3. For each degree page, extract course codes from the "Degree Map" plan-of-study grid
   (fall back to the requirements curriculum tables if no degree map)
4. Output JSON: degree -> list of course prefixes (with full course codes)
"""

import re
import json
import time
import os
import sys
import urllib.request
import ssl
from html.parser import HTMLParser

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://catalog.uidaho.edu"
CACHE_DIR = "cache_pages"
os.makedirs(CACHE_DIR, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def fetch(url):
    """Fetch a URL with simple file caching."""
    key = re.sub(r"[^A-Za-z0-9]+", "_", url)[-180:]
    path = os.path.join(CACHE_DIR, key + ".html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25, context=SSL_CTX) as r:
            data = r.read().decode("utf-8", errors="ignore")
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
        time.sleep(0.35)  # be polite
        return data
    except Exception as e:
        print(f"  !! fetch failed {url}: {e}", file=sys.stderr)
        return ""


# ---------- Step 1: departments ----------
# Colleges containing academic units with undergraduate degrees
ACADEMIC_COLLEGES = {
    "agricultural-life-sciences", "art-architecture", "business-economics",
    "education-health-human-sciences", "engineering",
    "letters-arts-social-sciences", "natural-resources", "science",
}

# Non-academic or non-unit slugs to skip within those colleges
SKIP_SLUGS = {
    "curricular-requirements", "general-studies", "general-studies-aa-as",
    "pre-health-professions-studies", "religious-studies",
}


def get_departments():
    html = fetch(BASE + "/colleges-related-units/")
    links = re.findall(r'href="(/colleges-related-units/[^"]+/)"[^>]*>([^<]+)</a>', html)
    depts = {}
    for href, name in links:
        parts = [p for p in href.split("/") if p]
        if len(parts) != 3:
            continue
        college_slug, unit_slug = parts[1], parts[2]
        if college_slug not in ACADEMIC_COLLEGES or unit_slug in SKIP_SLUGS:
            continue
        name = re.sub(r"&#8203;", "", name)
        name = re.sub(r"&nbsp;|&amp;", lambda m: " " if m.group(0) == "&nbsp;" else "&", name).strip()
        # skip degree-page-looking links (labels containing "(B.")
        if re.search(r"\(B\.", name):
            continue
        if name and href not in depts:
            depts[href] = {"name": name, "college": college_slug, "url": href}
    return depts


# ---------- Step 2: degree programs per department ----------
DEGREE_RE = re.compile(r"\((B\.[A-Za-z.& ]+|B\.A\.|B\.S\.|B\.Mus\.|B\.I\.A\.D\.|B\.F\.A\.|B\.B\.A\.)\)\s*$", re.I)


def get_degrees_for_dept(dept_url):
    html = fetch(BASE + dept_url)
    links = re.findall(r'href="(' + re.escape(dept_url) + r'[^"]+/)"[^>]*>([^<]+)</a>', html)
    degrees = {}
    for href, label in links:
        label = re.sub(r"&#8203;", "", label).strip()
        m = DEGREE_RE.search(label)
        if m and "minor" not in label.lower() and "certificate" not in label.lower():
            degrees[href] = label
    return degrees


# ---------- Step 3: parse degree map courses ----------
COURSE_CODE_RE = re.compile(r'showCourse\(this,\s*\'([A-Z]{2,5}) (\d{3,4}[A-Z]?)\'\)')


def get_degree_courses(degree_url):
    html = fetch(BASE + degree_url)
    # Prefer the degree map plan grid
    courses = []
    # find the degreemap section
    mm = re.search(r'<a name="degreemaptext".*?</table>', html, re.S)
    section = mm.group(0) if mm else html
    for subj, num in COURSE_CODE_RE.findall(section):
        courses.append(f"{subj} {num}")
    return sorted(set(courses))


def main():
    print("== Step 1: departments ==")
    depts = get_departments()
    print(f"Found {len(depts)} departments/schools/programs")

    all_data = {}
    tasks = []

    print("== Step 2 & 3: degrees + courses ==")
    for durl, dinfo in sorted(depts.items()):
        degrees = get_degrees_for_dept(durl)
        dinfo["degrees"] = degrees
        print(f"{dinfo['name']}: {len(degrees)} undergrad degree(s)")

    # fetch degree pages concurrently
    with ThreadPoolExecutor(max_workers=6) as ex:
        futmap = {}
        for durl, dinfo in depts.items():
            for deg_url, deg_label in dinfo.get("degrees", {}).items():
                fut = ex.submit(get_degree_courses, deg_url)
                futmap[fut] = (durl, deg_url, deg_label)
        for i, fut in enumerate(as_completed(futmap)):
            durl, deg_url, deg_label = futmap[fut]
            courses = fut.result()
            all_data[deg_url] = {
                "degree": deg_label,
                "department": depts[durl]["name"],
                "college": depts[durl]["college"],
                "url": BASE + deg_url,
                "courses": courses,
            }
            if (i + 1) % 20 == 0:
                print(f"  ... {i+1}/{len(futmap)} degree pages processed")

    with open("degree_data.json", "w") as f:
        json.dump(all_data, f, indent=1)
    print(f"\nSaved {len(all_data)} degree records to degree_data.json")


if __name__ == "__main__":
    main()
