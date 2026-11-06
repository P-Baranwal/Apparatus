#!/usr/bin/env python3

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from common import (
    CACHE,
    DATA,
    UPCOMING,
    ensure_export,
    export_rows,
    selected_results,
    wcif,
)

CANCELLED = "MohaliCubeOpen2026"
STATUS_PLAN = {
    "DCHydCubeOpenNovember2026": [
        ("accepted", 24),
        ("waiting_list", 3),
        ("pending", 1),
        ("cancelled", 1),
        ("rejected", 1),
    ],
    "IndianPBQChampionship2026": [
        ("accepted", 8),
        ("pending", 1),
        ("cancelled", 1),
        ("rejected", 1),
    ],
    "CubeXWinterOpenBengaluru2026": [
        ("accepted", 55),
        ("pending", 2),
        ("cancelled", 2),
        ("rejected", 1),
    ],
}
SELECT_STATUSES = {"accepted", "pending", "waiting_list"}


def write_csv(name, header, rows):
    path = DATA / name
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{name:28s} {len(rows):5d} rows -> {path}")


def parse_ts(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def ts_string(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def synthetic_guests(competition_id, person_no):
    digest = hashlib.sha256(
        f"{competition_id}|{person_no}|guests".encode("utf-8")
    ).digest()
    return digest[0] % 4


def guardian_consent(date_of_birth, start_date):
    born = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
    age = start_date.year - born.year - (
        (start_date.month, start_date.day) < (born.month, born.day)
    )
    return 1 if age < 18 else 0


competitions = {
    row["Competition_ID"]: row
    for row in csv.DictReader(open(DATA / "competitions.csv", encoding="utf-8"))
}
persons = {
    row["Person_No"]: row
    for row in csv.DictReader(open(DATA / "persons.csv", encoding="utf-8"))
}
registry = json.loads((CACHE / "person_registry.json").read_text(encoding="utf-8"))
wid_to_pno = {
    row["wca_id"]: row["person_no"] for row in registry.values() if row["wca_id"]
}
key_to_pno = {key: row["person_no"] for key, row in registry.items()}

results = selected_results()
past_competitions = sorted({row["competition_id"] for row in results})
plan = json.loads(
    (CACHE / "upcoming_registration_plan.json").read_text(encoding="utf-8")
)

event_round1 = {}
for cid in set(past_competitions) | set(UPCOMING):
    data = wcif(cid)
    event_round1[cid] = {
        (event["id"], rnd["id"])
        for event in data["events"]
        for rnd in event["rounds"]
    }

for cid, comp in competitions.items():
    main_event = comp["Main_Event_ID"]
    if main_event:
        assert (main_event, f"{main_event}-r1") in event_round1[cid], (cid, main_event)

registration_rows = []
select_rows = []

for cid in past_competitions:
    comp = competitions[cid]
    opens = parse_ts(comp["Opens_At"])
    closes = parse_ts(comp["Closes_At"])
    start_date = datetime.strptime(comp["Start_Date"], "%Y-%m-%d").date()
    by_person = defaultdict(set)
    for row in results:
        if row["competition_id"] == cid:
            by_person[row["person_id"]].add(row["event_id"])
    people = sorted(
        ((wid_to_pno[wca_id], wca_id) for wca_id in by_person),
        key=lambda item: item[0],
    )
    count = len(people)
    span = int((closes - opens).total_seconds())
    assert span > 0
    for index, (person_no, wca_id) in enumerate(people, start=1):
        registered_at = opens + timedelta(seconds=span * index // (count + 1))
        registration_rows.append(
            [
                cid,
                index,
                person_no,
                "accepted",
                ts_string(registered_at),
                synthetic_guests(cid, person_no),
                guardian_consent(persons[str(person_no)]["Date_of_Birth"], start_date),
            ]
        )
        for event_id in sorted(by_person[wca_id]):
            select_rows.append([cid, index, event_id])

for cid in UPCOMING:
    comp = competitions[cid]
    limit = int(comp["Competitor_Limit"])
    opens = parse_ts(comp["Opens_At"])
    closes = parse_ts(comp["Closes_At"])
    start_date = datetime.strptime(comp["Start_Date"], "%Y-%m-%d").date()
    entries = plan[cid]
    statuses = []
    for status, amount in STATUS_PLAN[cid]:
        statuses.extend([status] * amount)
    assert len(statuses) == len(entries), (cid, len(statuses), len(entries))

    registration_by_person_no = {}
    for person in wcif(cid)["persons"]:
        registration = person.get("registration")
        if not registration:
            continue
        key = person.get("wcaId") or f"user:{person['wcaUserId']}"
        person_no = key_to_pno[key]
        registration_by_person_no[person_no] = registration

    accepted = 0
    waiting = 0
    for entry in entries:
        person_no = entry["person_no"]
        registrant_no = entry["registrant_no"]
        status = statuses[registrant_no - 1]
        registered_at = parse_ts(entry["registered_at"])
        assert opens < registered_at < closes, (cid, registrant_no)
        assert person_no in registration_by_person_no, (cid, person_no)
        if status == "accepted":
            accepted += 1
        if status == "waiting_list":
            waiting += 1
        registration_rows.append(
            [
                cid,
                registrant_no,
                person_no,
                status,
                entry["registered_at"],
                synthetic_guests(cid, person_no),
                guardian_consent(persons[str(person_no)]["Date_of_Birth"], start_date),
            ]
        )
        if status in SELECT_STATUSES:
            for event_id in sorted(set(registration_by_person_no[person_no]["eventIds"])):
                select_rows.append([cid, registrant_no, event_id])
    assert accepted <= limit, (cid, accepted, limit)
    if cid == "DCHydCubeOpenNovember2026":
        assert waiting >= 3, waiting

registration_rows.sort(key=lambda row: (row[0], row[1]))
select_rows.sort(key=lambda row: (row[0], row[1], row[2]))

assert len({(row[0], row[1]) for row in registration_rows}) == len(registration_rows)
assert len({(row[0], row[2]) for row in registration_rows}) == len(registration_rows)
assert len({(row[0], row[1], row[2]) for row in select_rows}) == len(select_rows)

by_comp = defaultdict(list)
for row in registration_rows:
    by_comp[row[0]].append(row[1])
for cid, numbers in by_comp.items():
    assert sorted(numbers) == list(range(1, len(numbers) + 1)), cid

for cid in by_comp:
    timestamps = [
        row[4] for row in registration_rows if row[0] == cid
    ]
    assert all(
        timestamps[index] < timestamps[index + 1]
        for index in range(len(timestamps) - 1)
    ), cid
    opens = competitions[cid]["Opens_At"]
    closes = competitions[cid]["Closes_At"]
    assert all(opens <= value <= closes for value in timestamps), cid

select_keys = {(row[0], row[1], row[2]) for row in select_rows}
registration_status = {
    (row[0], row[1]): (row[2], row[3]) for row in registration_rows
}
for row in select_rows:
    assert (row[2], f"{row[2]}-r1") in event_round1[row[0]], row
    assert (row[0], row[1]) in registration_status, row

accepted_lookup = {
    (row[0], row[2]): row[3] for row in registration_rows
}
registrant_by_person = {
    (row[0], row[2]): row[1] for row in registration_rows
}
r9_missing = []
for row in results:
    key = (row["competition_id"], row["person_id"])
    person_no = wid_to_pno[row["person_id"]]
    if accepted_lookup.get((key[0], person_no)) != "accepted":
        r9_missing.append(row)
    registrant_no = registrant_by_person.get((key[0], person_no))
    if (key[0], registrant_no, row["event_id"]) not in select_keys:
        r9_missing.append(row)
assert not r9_missing, r9_missing[:3]

zf = ensure_export()
round_type_rank = {
    row["id"]: int(row["rank"])
    for row in export_rows(zf, "WCA_export_round_types.tsv")
}
types_by_event = defaultdict(set)
for row in results:
    types_by_event[(row["competition_id"], row["event_id"])].add(
        row["round_type_id"]
    )
round_order = {}
for key, types in types_by_event.items():
    for index, round_type in enumerate(
        sorted(types, key=lambda value: round_type_rank[value]), start=1
    ):
        round_order[(key[0], key[1], round_type)] = index

person_rounds = defaultdict(set)
for row in results:
    person_rounds[
        (row["competition_id"], row["event_id"], row["person_id"])
    ].add(round_order[(row["competition_id"], row["event_id"], row["round_type_id"])])
previous_round_violations = []
for key, orders in person_rounds.items():
    for value in orders:
        if value > 1 and value - 1 not in orders:
            previous_round_violations.append((key, sorted(orders)))

write_csv(
    "registrations.csv",
    [
        "Competition_ID",
        "Registrant_No",
        "Person_No",
        "Status",
        "Registered_At",
        "Guests",
        "Guardian_Consent",
    ],
    registration_rows,
)
write_csv(
    "selects.csv",
    ["Competition_ID", "Registrant_No", "Event_ID"],
    select_rows,
)

select_registrations = {(row[0], row[1]) for row in select_rows}
no_select = [
    (row[0], row[1])
    for row in registration_rows
    if (row[0], row[1]) not in select_registrations
]
registered_pnos = {int(row[2]) for row in registration_rows}
no_registration = [p for p in persons if int(p) not in registered_pnos]

status_counts = Counter(row[3] for row in registration_rows)
upcoming_status = Counter(
    row[3] for row in registration_rows if row[0] in UPCOMING
)
consent = Counter(row[6] for row in registration_rows)
guests = Counter(row[5] for row in registration_rows)

print()
print(f"registrations: {len(registration_rows)} | selects: {len(select_rows)}")
print(f"status totals: {dict(status_counts)}")
print(f"upcoming statuses: {dict(upcoming_status)}")
print(f"registrations per comp: {dict(Counter(row[0] for row in registration_rows))}")
print(f"guests distribution: {dict(guests)} | guardian consent: {dict(consent)}")
print(f"demo-safe registrations (no SELECTS): {len(no_select)} {no_select}")
print(f"persons with no registration: {len(no_registration)}")
print(f"competitions with no registration: {sorted(set(competitions) - set(by_comp))}")
print(f"R9 previous-round violations: {len(previous_round_violations)}")
print(f"accepted counts vs limits: " + ", ".join(
    f"{cid}={sum(1 for row in registration_rows if row[0]==cid and row[3]=='accepted')}/{competitions[cid]['Competitor_Limit'] or 'NULL'}"
    for cid in UPCOMING
))
