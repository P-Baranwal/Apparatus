#!/usr/bin/env python3

import csv
import collections
import json
import re

from common import (
    CACHE,
    DATA,
    SHORTLIST,
    ensure_export,
    export_rows,
    selected_results,
    wcif,
)

STAFF_ROLES = {
    "staff-judge": "judge",
    "staff-runner": "runner",
    "staff-scrambler": "scrambler",
    "staff-dataentry": "score_taker",
    "staff-announcer": "announcer",
}
STAFF_ROLE_CODES = {
    row["Role_Code"]
    for row in csv.DictReader(open(DATA / "staff_role.csv", encoding="utf-8"))
}


def write_csv(name, header, rows):
    path = DATA / name
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{name:28s} {len(rows):6d} rows -> {path}")


def excel_column(number):
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


rounds_by_comp_event = collections.defaultdict(list)
round_by_key = {}
for row in csv.DictReader(open(DATA / "rounds.csv", encoding="utf-8")):
    rounds_by_comp_event[(row["Competition_ID"], row["Event_ID"])].append(row)
    round_by_key[(row["Competition_ID"], row["Event_ID"], row["Round_Number"])] = row
for key in rounds_by_comp_event:
    rounds_by_comp_event[key].sort(key=lambda row: int(row["Round_Number"]))

def load_scrambles():
    path = CACHE / "selected_scrambles.tsv"
    if path.exists():
        with open(path, encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh, delimiter="\t"))
    export = ensure_export()
    rows = [
        row
        for row in export_rows(export, "WCA_export_scrambles.tsv")
        if row["competition_id"] in SHORTLIST
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return rows


scramble_rows_raw = load_scrambles()
zf = ensure_export()
round_type_rank = {
    row["id"]: int(row["rank"])
    for row in export_rows(zf, "WCA_export_round_types.tsv")
}
scramble_types = collections.defaultdict(set)
for row in scramble_rows_raw:
    scramble_types[(row["competition_id"], row["event_id"])].add(row["round_type_id"])

scramble_round_type_to_round = {}
for key, types in scramble_types.items():
    wcif_rounds = rounds_by_comp_event[key]
    ordered_types = sorted(types, key=lambda value: round_type_rank[value])
    assert len(wcif_rounds) == len(ordered_types), (
        key,
        len(wcif_rounds),
        len(ordered_types),
    )
    for round_row, round_type in zip(wcif_rounds, ordered_types):
        scramble_round_type_to_round[(key[0], key[1], round_type)] = int(
            round_row["Round_Number"]
        )

scramble_rows = []
sequence_rows = []
scramble_groups = collections.defaultdict(set)
for row in scramble_rows_raw:
    competition_id = row["competition_id"]
    event_id = row["event_id"]
    round_number = scramble_round_type_to_round[
        (competition_id, event_id, row["round_type_id"])
    ]
    group_id = row["group_id"]
    is_extra = int(row["is_extra"])
    scramble_no = int(row["scramble_num"])
    scramble_rows.append(
        [competition_id, event_id, round_number, group_id, is_extra, scramble_no]
    )
    scramble_groups[(competition_id, event_id, str(round_number))].add(group_id)
    sequences = (
        row["scramble"].split("|") if event_id == "333mbf" else [row["scramble"]]
    )
    for sequence in sequences:
        sequence_rows.append(
            [
                competition_id,
                event_id,
                round_number,
                group_id,
                is_extra,
                scramble_no,
                sequence,
            ]
        )

scramble_rows.sort(key=lambda row: (row[0], row[1], row[2], row[3], row[4], row[5]))
sequence_rows.sort(
    key=lambda row: (row[0], row[1], row[2], row[3], row[4], row[5], row[6])
)
assert len({tuple(row) for row in scramble_rows}) == len(scramble_rows)
assert len({tuple(row) for row in sequence_rows}) == len(sequence_rows)
assert all(row[6].strip() for row in sequence_rows)

registry = json.loads((CACHE / "person_registry.json").read_text(encoding="utf-8"))
wid_to_pno = {
    row["wca_id"]: row["person_no"] for row in registry.values() if row["wca_id"]
}
uid_to_pno = {
    row["user_id"]: row["person_no"] for row in registry.values() if row["user_id"]
}

scramble_competitions = sorted({row["competition_id"] for row in scramble_rows_raw})
assigned_as = set()
slot_station = {}
excluded = collections.Counter()
excluded_codes = collections.Counter()
excluded_users = set()
missing_scramble_group = 0
duplicate_slot = 0
staff_rows = 0

for competition_id in scramble_competitions:
    data = wcif(competition_id)
    activity = {}
    for venue in data["schedule"]["venues"]:
        for room in venue["rooms"]:
            for item in room["activities"]:
                activity[item["id"]] = item
                for child in item.get("childActivities", []):
                    activity[child["id"]] = child
    for person in data["persons"]:
        for assignment in person.get("assignments", []):
            code = assignment.get("assignmentCode")
            if code not in STAFF_ROLES:
                excluded_codes[code] += 1
                continue
            staff_rows += 1
            activity_code = activity[assignment["activityId"]]["activityCode"]
            match = re.match(
                r"^(.+?)-r(\d+)-g(\d+)(?:-a\d+)?$", activity_code
            )
            if not match:
                excluded["no_round"] += 1
                continue
            event_id = match.group(1)
            round_number = int(match.group(2))
            group_number = int(match.group(3))
            if (competition_id, event_id, str(round_number)) not in round_by_key:
                excluded["round_not_loaded"] += 1
                continue
            person_no = None
            if person.get("wcaId"):
                person_no = wid_to_pno.get(person["wcaId"])
            if person_no is None and person.get("wcaUserId"):
                person_no = uid_to_pno.get(person["wcaUserId"])
            if person_no is None:
                excluded["not_in_person"] += 1
                excluded_users.add(person.get("wcaUserId"))
                continue
            role = STAFF_ROLES[code]
            assigned_key = (
                person_no,
                competition_id,
                event_id,
                round_number,
                role,
            )
            assigned_as.add(assigned_key)
            if assignment.get("stationNumber") is None:
                continue
            group_id = excel_column(group_number)
            if group_id not in scramble_groups[
                (competition_id, event_id, str(round_number))
            ]:
                missing_scramble_group += 1
                continue
            slot_key = assigned_key + (group_id,)
            if slot_key in slot_station:
                duplicate_slot += 1
                continue
            slot_station[slot_key] = int(assignment["stationNumber"])

assigned_as_rows = [
    [person_no, competition_id, event_id, round_number, role]
    for person_no, competition_id, event_id, round_number, role in sorted(assigned_as)
]
slot_rows = [
    [person_no, competition_id, event_id, round_number, role, group_id, station]
    for (person_no, competition_id, event_id, round_number, role, group_id), station
    in sorted(slot_station.items())
]

for row in slot_rows:
    assert tuple(row[:5]) in assigned_as
    assert row[4] in STAFF_ROLE_CODES
    assert row[5] in scramble_groups[(row[1], row[2], str(row[3]))]
for row in assigned_as_rows:
    assert row[4] in STAFF_ROLE_CODES
    assert row[4] != "delegate"
    assert (row[1], row[2], str(row[3])) in round_by_key

write_csv(
    "scrambles.csv",
    [
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Group_ID",
        "Is_Extra",
        "Scramble_No",
    ],
    scramble_rows,
)
write_csv(
    "scramble_sequences.csv",
    [
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Group_ID",
        "Is_Extra",
        "Scramble_No",
        "Sequence",
    ],
    sequence_rows,
)
write_csv(
    "assigned_as.csv",
    ["Person_No", "Competition_ID", "Event_ID", "Round_Number", "Role_Code"],
    assigned_as_rows,
)
write_csv(
    "assigned_as_slots.csv",
    [
        "Person_No",
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Role_Code",
        "Group_ID",
        "Station_No",
    ],
    slot_rows,
)

mbld_rows = [row for row in scramble_rows_raw if row["event_id"] == "333mbf"]
assigned_roles = collections.Counter(row[4] for row in assigned_as_rows)
assigned_by_comp = collections.Counter(row[1] for row in assigned_as_rows)
slots_by_comp = collections.Counter(row[1] for row in slot_rows)
rows_with_slots = len({tuple(row[:5]) for row in slot_rows})
print()
print(
    f"scrambles: {len(scramble_rows)} | sequences: {len(sequence_rows)} | "
    f"assigned_as: {len(assigned_as_rows)} | slots: {len(slot_rows)}"
)
print(f"scramble competitions: {scramble_competitions}")
print(f"scramble groups: {len({row[3] for row in scramble_rows})} | MBLD sequences: {sum(row['scramble'].count('|')+1 for row in mbld_rows)}")
print(f"assigned roles: {dict(assigned_roles)}")
print(f"assigned_as per comp: {dict(assigned_by_comp)}")
print(f"slots per comp: {dict(slots_by_comp)}")
print(f"assigned_as rows with at least one slot: {rows_with_slots}")
print(f"staff assignment rows: {staff_rows} | excluded not-in-PERSON: {excluded['not_in_person']} ({len(excluded_users)} users)")
print(f"excluded non-round: {excluded['no_round']} | round not loaded: {excluded['round_not_loaded']}")
print(f"excluded non-staff codes: {dict(excluded_codes)}")
print(f"station assignments without a matching scramble group: {missing_scramble_group}")
print(f"duplicate slot keys: {duplicate_slot}")

audit = {
    "staff_rows": staff_rows,
    "excluded_not_in_person": excluded["not_in_person"],
    "excluded_users": len(excluded_users),
    "excluded_codes": dict(excluded_codes),
    "missing_scramble_group": missing_scramble_group,
    "duplicate_slot": duplicate_slot,
    "assigned_as_rows": len(assigned_as_rows),
    "slot_rows": len(slot_rows),
    "rows_with_slots": rows_with_slots,
    "scramble_competitions": scramble_competitions,
}
(CACHE / "step7_audit.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8"
)
