#!/usr/bin/env python3
"""
Build REQUIREMENTS-BASED department dependency network.

Reads: degree_requirements.json (from scrape_requirements.py)
Writes: network_requirements.json + network-requirements.js

Each degree->subject edge carries context buckets:
  required, choice, elective_menu counts.

Unit->unit links aggregate with the same breakdown, so the app can
toggle whether broad elective menus count as dependencies.
"""

import json
import re
import os
from collections import defaultdict

from build_network import CURATED, load_prefix_map  # reuse curated prefix map


def main():
    prefix_map = load_prefix_map()
    data = json.load(open("degree_requirements.json"))

    used = set()
    for d in data.values():
        for c in d["courses"]:
            used.add(c["code"].split()[0])
    unmapped = sorted(p for p in used if p not in CURATED)
    if unmapped:
        print("WARNING unmapped prefixes:", {p: prefix_map.get(p, "?") for p in unmapped})

    units = {}
    degrees = []
    degree_edges = []
    for url, d in data.items():
        dept, college = d["department"], d["college"]
        units.setdefault(dept, college)
        degrees.append({
            "name": d["degree"], "unit": dept, "college": college,
            "url": d["url"],
            "n_required": sum(1 for c in d["courses"] if c["context"] == "required"),
            "n_choice": sum(1 for c in d["courses"] if c["context"] == "choice"),
            "n_elective_menu": sum(1 for c in d["courses"] if c["context"] == "elective_menu"),
        })
        # group by prefix
        by_prefix = defaultdict(lambda: {"courses": defaultdict(list)})
        for c in d["courses"]:
            subj, num = c["code"].split()
            by_prefix[subj]["courses"][c["context"]].append(num)
        for subj, bundle in by_prefix.items():
            ctxs = bundle["courses"]
            degree_edges.append({
                "degree": d["degree"], "degree_url": d["url"], "unit": dept,
                "subject_prefix": subj,
                "subject_name": prefix_map.get(subj, subj),
                "subject_unit": CURATED.get(subj, f"Other ({subj})"),
                "n_required": len(ctxs.get("required", [])),
                "n_choice": len(ctxs.get("choice", [])),
                "n_elective_menu": len(ctxs.get("elective_menu", [])),
                "courses_required": sorted(ctxs.get("required", [])),
                "courses_choice": sorted(ctxs.get("choice", [])),
                "courses_elective_menu": sorted(ctxs.get("elective_menu", [])),
                "count": sum(len(v) for v in ctxs.values()),
            })

    # aggregate unit->unit
    agg = defaultdict(lambda: {
        "weights": defaultdict(int),
        "degree_set": set(),
        "course_list": {"required": set(), "choice": set(), "elective_menu": set()},
    })
    for e in degree_edges:
        if e["unit"] == e["subject_unit"]:
            continue
        key = (e["unit"], e["subject_unit"])
        a = agg[key]
        a["degree_set"].add(e["degree"])
        for ctx in ("required", "choice", "elective_menu"):
            n = e[f"n_{ctx}"]
            if n:
                a["weights"][ctx] += n
                for num in e[f"courses_{ctx}"]:
                    a["course_list"][ctx].add(f"{e['subject_prefix']} {num}")

    unit_links = []
    for (src, tgt), a in agg.items():
        w = a["weights"]
        unit_links.append({
            "source": src, "target": tgt,
            "weight": w["required"] + w["choice"] + w["elective_menu"],
            "weight_core": w["required"] + w["choice"],
            "n_required": w["required"], "n_choice": w["choice"],
            "n_elective_menu": w["elective_menu"],
            "num_degrees": len(a["degree_set"]),
            "degrees": sorted(a["degree_set"]),
            "courses": sorted(a["course_list"]["required"] | a["course_list"]["choice"] | a["course_list"]["elective_menu"]),
            "courses_required": sorted(a["course_list"]["required"]),
            "courses_choice": sorted(a["course_list"]["choice"]),
            "courses_elective_menu": sorted(a["course_list"]["elective_menu"]),
        })
    unit_links.sort(key=lambda x: -x["weight_core"])

    subjects = {}
    for e in degree_edges:
        subjects[e["subject_prefix"]] = {
            "prefix": e["subject_prefix"], "name": e["subject_name"], "unit": e["subject_unit"],
        }

    # ensure every link endpoint exists as a unit node
    for l in unit_links:
        for name in (l["source"], l["target"]):
            units.setdefault(name, "other")

    out = {
        "units": [{"name": n, "college": c} for n, c in sorted(units.items())],
        "degrees": degrees,
        "subjects": sorted(subjects.values(), key=lambda x: x["prefix"]),
        "degree_edges": degree_edges,
        "unit_links": unit_links,
    }
    json.dump(out, open("network_requirements.json", "w"), indent=1)

    compact = json.dumps(out, separators=(",", ":"))
    js = ("// UI cross-department dependency data from DEGREE REQUIREMENTS "
          "(2026-2027 catalog)\nwindow.NETWORK_DATA = "
          + compact.replace("</", "<\\/") + ";\n")
    open("network-requirements.js", "w").write(js)

    print(f"Units: {len(units)} | Degrees: {len(degrees)} | Subjects: {len(subjects)}")
    print(f"Degree->subject edges: {len(degree_edges)} | Unit->unit links: {len(unit_links)}")
    print("\nTop 15 cross-unit dependencies (core = required + choice):")
    for l in unit_links[:15]:
        print(f"  {l['source']} -> {l['target']}: core={l['weight_core']} "
              f"(req {l['n_required']}, choice {l['n_choice']}), elective_menu={l['n_elective_menu']}, "
              f"degrees={l['num_degrees']}")


if __name__ == "__main__":
    main()
