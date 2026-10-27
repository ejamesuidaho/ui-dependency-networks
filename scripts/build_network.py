#!/usr/bin/env python3
"""
Build department dependency network from scraped degree data.

Outputs network_data.json for the visualization app:
- nodes: subject areas (course prefixes mapped to subject names & inferred home unit)
- degree_nodes: the degree programs grouped by owning unit
- links: degree -> subject dependencies with course lists
- unit_links: aggregated unit -> unit dependency weights
"""

import json
import re
import os
from collections import defaultdict

UA_CACHE = "cache_pages"

# 1. Build prefix -> subject name map from the courses index cache
def load_prefix_map():
    # try cache dir, then /tmp fetch
    html = None
    for f in os.listdir(UA_CACHE):
        if f.startswith("https_catalog_uidaho_edu_courses_") and f.endswith(".html"):
            html = open(os.path.join(UA_CACHE, f), encoding="utf-8", errors="ignore").read()
            break
    if html is None:
        if os.path.exists("/tmp/courses_index.html"):
            html = open("/tmp/courses_index.html", encoding="utf-8", errors="ignore").read()
        else:
            import urllib.request, ssl
            ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
            req = urllib.request.Request("https://catalog.uidaho.edu/courses/",
                                         headers={"User-Agent": "Mozilla/5.0"})
            html = urllib.request.urlopen(req, context=ctx, timeout=25).read().decode("utf-8", errors="ignore")
    pairs = re.findall(r'<a href="/courses/[a-z0-9-]+/">([^<]+)\(([A-Z]{2,5})\)</a>', html)
    prefix_map = {}
    for name, prefix in pairs:
        name = re.sub(r"&#8203;", "", name).strip()
        prefix_map[prefix] = name
    return prefix_map


# 2. Infer the "home unit" for each prefix by matching which department page
#    offers degrees containing courses of that prefix most heavily... too fuzzy.
#    Better: use explicit curated mapping prefix -> owning unit name, built from
#    the courses-index subject names matched against department names.

CURATED = {
    # prefix -> owning unit (department/school/program display name)
    "ACCT": "Accounting and Management Information Systems",
    "BIA": "Accounting and Management Information Systems",
    "MIS": "Accounting and Management Information Systems",
    "AGEC": "Department of Agricultural Economics and Rural Sociology",
    "AGED": "Department of Agricultural Education, Leadership and Communications",
    "AVS": "Department of Animal, Veterinary and Food Sciences",
    "AVFS": "Department of Animal, Veterinary and Food Sciences",
    "FS": "Department of Animal, Veterinary and Food Sciences",
    "ENT": "Department of Entomology, Plant Pathology and Nematology",
    "EPPN": "Department of Entomology, Plant Pathology and Nematology",
    "PLSC": "Department of Plant Sciences",
    "ASM": "Department of Soil and Water Systems",
    "SOIL": "Department of Soil and Water Systems",
    "WATER": "Department of Soil and Water Systems",
    "ATD": "Margaret Ritchie School of Family and Consumer Sciences",
    "FCS": "Margaret Ritchie School of Family and Consumer Sciences",
    "CD": "Margaret Ritchie School of Family and Consumer Sciences",
    "ECDE": "Margaret Ritchie School of Family and Consumer Sciences",
    "FN": "Margaret Ritchie School of Family and Consumer Sciences",
    "ARCH": "Department of Architecture",
    "ART": "Department of Art & Design",
    "IAD": "Department of Design and Environments",
    "LAND": "Department of Design and Environments",
    "VTD": "Department of Design and Environments",
    "BE": "Department of Chemical and Biological Engineering",
    "CHE": "Department of Chemical and Biological Engineering",
    "CE": "Department of Civil and Environmental Engineering",
    "CS": "Department of Computer Science",
    "CYB": "Department of Computer Science",
    "AIML": "Department of Computer Science",
    "ECE": "Department of Electrical and Computer Engineering",
    "ME": "Department of Mechanical Engineering",
    "NE": "Department of Nuclear Engineering and Industrial Management",
    "EM": "Department of Nuclear Engineering and Industrial Management",
    "IE": "Department of Nuclear Engineering and Industrial Management",
    "TECH": "Department of Nuclear Engineering and Industrial Management",
    "ENVS": "Environmental Science",
    "FISH": "Fish and Wildlife Sciences",
    "WLF": "Fish and Wildlife Sciences",
    "FOR": "Forest, Rangeland, and Fire Sciences",
    "REM": "Forest, Rangeland, and Fire Sciences",
    "FIRE": "Forest, Rangeland, and Fire Sciences",
    "NRS": "Natural Resources and Society",
    "BCB": "Bioinformatics and Computational Biology",
    "BIOL": "Biological Sciences",
    "MICB": "Biological Sciences",
    "BIMS": "Biological Sciences",
    "CHEM": "Chemistry",
    "ESS": "Earth and Spatial Sciences",
    "GEOG": "Earth and Spatial Sciences",
    "GEOL": "Earth and Spatial Sciences",
    "MATH": "Mathematics and Statistical Science",
    "STAT": "Mathematics and Statistical Science",
    "PHYS": "Physics",
    "BUS": "Business",
    "BLAW": "Business",
    "ECON": "Business",
    "ENTR": "Business",
    "FIN": "Business",
    "MGT": "Business",
    "MKTG": "Business",
    "OM": "Business",
    "MBA": "Business",
    "EDCI": "Curriculum and Instruction",
    "EDSP": "Curriculum and Instruction",
    "CTE": "Curriculum and Instruction",
    "ED": "Curriculum and Instruction",
    "EDAD": "Leadership and Counseling",
    "COUN": "Leadership and Counseling",
    "ESHS": "Movement Sciences",
    "MVSC": "Movement Sciences",
    "AT": "Movement Sciences",
    "CRIM": "Department of Culture, Society and Justice",
    "SOC": "Department of Culture, Society and Justice",
    "ANTH": "Department of Culture, Society and Justice",
    "SJS": "Department of Culture, Society and Justice",
    "ENGL": "Department of English",
    "HIST": "Department of History",
    "POLS": "Department of Politics and Philosophy",
    "PHIL": "Department of Politics and Philosophy",
    "PSYC": "Department of Psychology and Communication",
    "COMM": "Department of Psychology and Communication",
    "THEA": "Department of Theatre Arts",
    "DAN": "Department of Theatre Arts",
    "JAMM": "School of Journalism and Mass Media",
    "MUSA": "Lionel Hampton School of Music",
    "MUSC": "Lionel Hampton School of Music",
    "MUSI": "Lionel Hampton School of Music",
    "MUSH": "Lionel Hampton School of Music",
    "MUST": "Lionel Hampton School of Music",
    "MUSX": "Lionel Hampton School of Music",
    "CHIN": "School of Global Studies",
    "FREN": "School of Global Studies",
    "GERM": "School of Global Studies",
    "JAPN": "School of Global Studies",
    "SPAN": "School of Global Studies",
    "RUSS": "School of Global Studies",
    "ARBC": "School of Global Studies",
    "INTR": "School of Global Studies",
    "AIST": "Program in American Indian Studies",
    "AMST": "Program in Interdisciplinary Studies",
    "LAS": "Program in Latin American Studies",
    "ORGS": "Program in Organizational Sciences",
    "WGSS": "Program in Women's, Gender, and Sexuality Studies",
    "AGLS": "College of Agricultural and Life Sciences",
    "CORS": "College of Science",
    "ENGR": "College of Engineering",
    "CAA": "College of Art and Architecture",
    "GNST": "General Studies",
    "HON": "Honors Program",
    "AERO": "Aerospace Studies",
    "MS": "Department of Military Science",
    "NS": "Department of Naval Science",
    "REL": "Religious Studies",
    "FTV": "Department of English",
    "HUM": "College of Letters, Arts and Social Sciences",
    "INTRPS": "Pre-Health Professions Studies",
    "SUST": "Sustainability Program",
    "CLDR": "Department of Agricultural Education, Leadership and Communications",
    "ETEC": "Department of Nuclear Engineering and Industrial Management",
    "FL": "School of Global Studies",
    "FLEN": "Department of English",
    "FSP": "Forest, Rangeland, and Fire Sciences",
    "GENE": "Biological Sciences",
    "GEOE": "Department of Civil and Environmental Engineering",
    "HDFS": "Margaret Ritchie School of Family and Consumer Sciences",
    "HYDR": "Department of Soil and Water Systems",
    "IS": "School of Global Studies",
    "ISE": "Department of Nuclear Engineering and Industrial Management",
    "LARC": "Department of Design and Environments",
    "MTHE": "Curriculum and Instruction",
    "NR": "Natural Resources",
    "PGA": "Business",
    "PLP": "Department of Entomology, Plant Pathology and Nematology",
    "SRM": "Movement Sciences",
    "THE": "Department of Theatre Arts",
}


def main():
    prefix_map = load_prefix_map()
    data = json.load(open("degree_data.json"))

    # Collect all prefixes used
    used = set()
    for d in data.values():
        for c in d["courses"]:
            used.add(c.split()[0])
    unmapped = sorted(p for p in used if p not in CURATED)
    print("Unmapped prefixes:", unmapped)
    print({p: prefix_map.get(p, "?") for p in unmapped})

    # Build network
    units = {}  # unit name -> {college}
    degrees = []
    degree_edges = []  # degree -> subject prefix (courses)

    # map unit -> college from scrape dept info
    for url, d in data.items():
        dept = d["department"]
        college = d["college"]
        units.setdefault(dept, college)
        degrees.append({
            "name": d["degree"],
            "unit": dept,
            "college": college,
            "url": d["url"],
            "num_courses": len(d["courses"]),
        })
        by_prefix = defaultdict(list)
        for c in d["courses"]:
            subj, num = c.split()
            by_prefix[subj].append(num)
        own_prefixes = [p for p, u in CURATED.items() if u == dept]
        for subj, nums in by_prefix.items():
            degree_edges.append({
                "degree": d["degree"],
                "degree_url": d["url"],
                "unit": dept,
                "subject_prefix": subj,
                "subject_name": prefix_map.get(subj, subj),
                "subject_unit": CURATED.get(subj, "Other/Unknown"),
                "courses": sorted(nums),
                "count": len(nums),
            })

    # Aggregate unit -> unit
    unit_links = defaultdict(lambda: {"courses": 0, "degree_set": set(), "course_list": set()})
    for e in degree_edges:
        src = e["unit"]
        tgt = e["subject_unit"]
        if src == tgt:
            continue
        key = (src, tgt)
        unit_links[key]["courses"] += e["count"]
        unit_links[key]["degree_set"].add(e["degree"])
        for n in e["courses"]:
            unit_links[key]["course_list"].add(f"{e['subject_prefix']} {n}")

    agg_links = [
        {
            "source": k[0],
            "target": k[1],
            "weight": v["courses"],
            "num_degrees": len(v["degree_set"]),
            "degrees": sorted(v["degree_set"]),
            "courses": sorted(v["course_list"]),
        }
        for k, v in unit_links.items()
    ]
    agg_links.sort(key=lambda x: -x["weight"])

    # Subject-level nodes
    subjects = {}
    for e in degree_edges:
        p = e["subject_prefix"]
        subjects[p] = {"prefix": p, "name": e["subject_name"], "unit": e["subject_unit"]}

    out = {
        "units": [{"name": n, "college": c} for n, c in sorted(units.items())],
        "degrees": degrees,
        "subjects": sorted(subjects.values(), key=lambda x: x["prefix"]),
        "degree_edges": degree_edges,
        "unit_links": agg_links,
    }
    with open("network_data.json", "w") as f:
        json.dump(out, f, indent=1)

    print(f"\nUnits: {len(units)} | Degrees: {len(degrees)} | Subject prefixes: {len(subjects)}")
    print(f"Degree->subject edges: {len(degree_edges)} | Unit->unit links: {len(agg_links)}")
    print("\nTop 20 cross-unit dependencies:")
    for l in agg_links[:20]:
        print(f"  {l['source']} -> {l['target']}: {l['weight']} courses across {l['num_degrees']} degrees")


if __name__ == "__main__":
    main()
