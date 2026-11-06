#!/usr/bin/env python3

import collections
import csv
import sys

from common import (
    CANCELLED,
    DATA,
    POOL_COMPS,
    SHORTLIST,
    UPCOMING,
    competition,
    delegates,
    ensure_export,
    export_rows,
    selected_results,
    teams,
    wcif,
)

MAIN10 = ["333", "222", "444", "555", "333oh", "clock", "minx", "pyram", "skewb", "sq1"]
FORMAT_ORDER = ["1", "2", "3", "5", "a", "m"]
CONTINENT_ORDER = [
    "_Africa",
    "_Asia",
    "_Europe",
    "_North America",
    "_Oceania",
    "_South America",
]


def write_csv(name, header, rows):
    path = DATA / name
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{name:24s} {len(rows):4d} rows -> {path}")


zf = ensure_export()

countries = {r["id"]: r for r in export_rows(zf, "WCA_export_countries.tsv")}
iso2_to_id = {}
for cid, row in countries.items():
    iso2 = row["iso2"]
    if len(iso2) == 2 and iso2.isupper():
        assert iso2 not in iso2_to_id, f"duplicate ISO2 {iso2}"
        iso2_to_id[iso2] = cid

continents = [
    r for r in export_rows(zf, "WCA_export_continents.tsv") if r["record_name"]
]
assert {r["id"] for r in continents} == set(CONTINENT_ORDER)
write_csv(
    "continents.csv",
    ["Continent_ID", "Name", "Record_Code"],
    [[r["id"], r["name"], r["record_name"]] for r in continents],
)

event_rows = []
for row in export_rows(zf, "WCA_export_events.tsv"):
    if row["id"] == "fto":
        continue
    event_rows.append(
        [
            row["id"],
            row["name"],
            int(row["rank"]),
            row["format"],
            "official" if int(row["rank"]) < 900 else "retired",
        ]
    )
event_rows.sort(key=lambda r: (r[2], r[0]))
assert len(event_rows) == 21
assert sum(1 for r in event_rows if r[4] == "official") == 17
assert sum(1 for r in event_rows if r[4] == "retired") == 4
event_rank = {r[0]: r[2] for r in event_rows}
write_csv(
    "events.csv",
    ["Event_ID", "Event_Name", "Display_Rank", "Result_Kind", "Status"],
    event_rows,
)

format_rows = []
for row in export_rows(zf, "WCA_export_formats.tsv"):
    if row["id"] not in FORMAT_ORDER:
        continue
    format_rows.append(
        [
            row["id"],
            row["name"],
            int(row["expected_solve_count"]),
            row["sort_by"],
            1 if row["id"] == "a" else 0,
        ]
    )
format_rows.sort(key=lambda r: FORMAT_ORDER.index(r[0]))
assert len(format_rows) == 6
write_csv(
    "formats.csv",
    ["Format_ID", "Format_Name", "Expected_Attempts", "Sort_By", "Trimmed_Per_Side"],
    format_rows,
)

allow_rows = []


def allow(event, fmt, usage_1, usage_2=""):
    allow_rows.append([event, fmt, usage_1, usage_2])


for event in MAIN10:
    allow(event, "a", "full_round")
    allow(event, "2", "cutoff_phase")
for event in ["666", "777"]:
    allow(event, "m", "full_round")
    allow(event, "1", "cutoff_phase")
allow("333bf", "5", "full_round")
for event in ["444bf", "555bf"]:
    allow(event, "3", "full_round")
for fmt in ["1", "2"]:
    allow("333fm", fmt, "full_round", "cutoff_phase")
allow("333fm", "m", "full_round")
for fmt in ["1", "2"]:
    allow("333mbf", fmt, "full_round", "cutoff_phase")
allow("333mbf", "3", "full_round")
allow("333bf", "3", "full_round")

HISTORICAL = {("333bf", "3")}
allow_rows.sort(key=lambda r: (event_rank[r[0]], FORMAT_ORDER.index(r[1])))
allow_set = {(r[0], r[1]) for r in allow_rows}

used_pairs = set()
for cid in SHORTLIST:
    if cid in CANCELLED:
        continue
    data = wcif(cid)
    for event in data["events"]:
        assert event["id"] in event_rank, f"{cid}: unknown event {event['id']}"
        for rnd in event["rounds"]:
            used_pairs.add((event["id"], rnd["format"]))

missing = used_pairs - allow_set
assert not missing, f"rounds using pairs absent from allows: {sorted(missing)}"
assert HISTORICAL <= used_pairs
assert all(fid in FORMAT_ORDER for _, fid in used_pairs)
assert all(event_rank[e] < 900 for e, _ in used_pairs)
write_csv("allows.csv", ["Event_ID", "Format_ID", "Usage_1", "Usage_2"], allow_rows)

write_csv(
    "staff_role.csv",
    ["Role_Code", "Description", "Regulation_Ref"],
    [
        ["judge", "Judge", "1e"],
        ["scrambler", "Scrambler", "1f"],
        ["runner", "Runner", ""],
        ["score_taker", "Score taker", "1g"],
        ["announcer", "Announcer", "1l"],
    ],
)

current_person = {}
previous_country = collections.defaultdict(set)
global_person_count = collections.Counter()
for row in export_rows(zf, "WCA_export_persons.tsv"):
    global_person_count[row["country_id"]] += 1
    if row["sub_id"] == "1":
        current_person[row["wca_id"]] = row
    else:
        previous_country[row["wca_id"]].add(row["country_id"])

global_competition_count = collections.Counter()
for row in export_rows(zf, "WCA_export_competitions.tsv"):
    global_competition_count[row["country_id"]] += 1

results = selected_results()
referenced = {r["person_country_id"] for r in results}
person_ids = {r["person_id"] for r in results}

for person in delegates():
    if person.get("wca_id"):
        person_ids.add(person["wca_id"])
    if person.get("wca_id") and person.get("country"):
        referenced.add(person["country"]["id"])

for group in teams():
    for role in group["_roles"]:
        user = role["user"]
        if user.get("wca_id"):
            person_ids.add(user["wca_id"])
        if user.get("country"):
            referenced.add(user["country"]["id"])

for cid in SHORTLIST:
    comp = competition(cid)
    referenced.add(iso2_to_id[comp["country_iso2"]])
    for organizer in comp.get("organizers", []):
        if organizer.get("wca_id"):
            person_ids.add(organizer["wca_id"])
            if organizer.get("country"):
                referenced.add(organizer["country"]["id"])

for cid in UPCOMING:
    for person in wcif(cid)["persons"]:
        referenced.add(iso2_to_id[person["countryIso2"]])
        if person.get("wcaId"):
            person_ids.add(person["wcaId"])

for wid in person_ids:
    row = current_person.get(wid)
    if row:
        referenced.add(row["country_id"])
    referenced |= previous_country.get(wid, set())

assert referenced <= set(countries)
unreferenced = [
    cid
    for cid, row in countries.items()
    if cid not in referenced
    and len(row["iso2"]) == 2
    and row["iso2"].isupper()
]

picks = []
globally_empty = [
    cid
    for cid in unreferenced
    if global_person_count[cid] == 0 and global_competition_count[cid] == 0
]
candidate_pool = globally_empty if len(globally_empty) >= 8 else unreferenced
for continent in CONTINENT_ORDER:
    candidates = sorted(
        (c for c in candidate_pool if countries[c]["continent_id"] == continent),
        key=lambda c: countries[c]["iso2"],
    )
    if candidates:
        picks.append(candidates[0])
for cid in sorted(candidate_pool, key=lambda c: countries[c]["iso2"]):
    if len(picks) >= 8:
        break
    if cid not in picks:
        picks.append(cid)
for cid in sorted(unreferenced, key=lambda c: countries[c]["iso2"]):
    if len(picks) >= 8:
        break
    if cid not in picks:
        picks.append(cid)

final_country_ids = referenced | set(picks)
country_rows = [
    [cid, countries[cid]["iso2"], countries[cid]["name"], countries[cid]["continent_id"]]
    for cid in sorted(final_country_ids)
]
assert len({r[1] for r in country_rows}) == len(country_rows)
assert all(len(r[1]) == 2 and r[1].isupper() for r in country_rows)
write_csv(
    "countries.csv",
    ["Country_ID", "ISO2", "Name", "Continent_ID"],
    country_rows,
)

print()
print(f"referenced countries: {len(referenced)}")
print(
    "unreferenced picks: "
    + ", ".join(f"{countries[c]['iso2']}={c}" for c in picks)
)
print(f"used (event,format) pairs in loaded rounds: {len(used_pairs)}")
print(f"historical allows additions: {sorted(HISTORICAL)}")
print(f"result rows after pool: {len(results)}")
print(f"distinct result persons: {len({r['person_id'] for r in results})}")
