#!/usr/bin/env python3

import csv
import collections
import json
import re
from datetime import date, datetime, timedelta

from common import CACHE, DATA, ensure_export, export_rows

TODAY = date(2026, 11, 5)
ONE_YEAR_AGO = TODAY - timedelta(days=365)
ALLOWED_RECORDS = {"WR", "AfR", "AsR", "ER", "NAR", "OcR", "SAR", "NR"}
CONTINENT_RECORDS = {"AfR", "AsR", "ER", "NAR", "OcR", "SAR"}
STAFF_CODES = {"judge", "scrambler", "runner", "score_taker", "announcer"}
DELEGATE_STATUSES = {"trainee", "junior", "full", "regional", "senior", "former"}

FILES = [
    "continents",
    "countries",
    "persons",
    "previous_identities",
    "competitors",
    "delegate",
    "events",
    "formats",
    "allows",
    "staff_role",
    "regions",
    "teams",
    "member_of",
    "competitions",
    "championship_types",
    "competition_delegates",
    "competition_organizers",
    "rounds",
    "cumulative_scope",
    "scrambles",
    "scramble_sequences",
    "registrations",
    "selects",
    "results",
    "attempts",
    "assigned_as",
    "assigned_as_slots",
]

FAILS = []
WARNS = []


def load(name):
    path = DATA / f"{name}.csv"
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def fail(message):
    FAILS.append(message)


def warn(message):
    WARNS.append(message)


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def ids(name, column):
    return {row[column] for row in tables[name]}


def check_pk(name, columns):
    keys = [tuple(row[column] for column in columns) for row in tables[name]]
    duplicates = len(keys) - len(set(keys))
    if duplicates:
        fail(f"R1 PK {name}({', '.join(columns)}): {duplicates} duplicate keys")
    return duplicates


def check_unique(name, column, allow_empty=False):
    values = [row[column] for row in tables[name] if row[column] or not allow_empty]
    duplicates = [value for value, count in collections.Counter(values).items() if count > 1]
    if duplicates:
        fail(f"R1 unique {name}.{column}: duplicates {duplicates[:5]}")
    return duplicates


def check_fk(name, column, ref_name, ref_column="", allow_empty=True, ref_set=None):
    if ref_set is None:
        ref_set = ids(ref_name, ref_column or column)
    bad = [
        row[column]
        for row in tables[name]
        if row[column] and (row[column] not in ref_set)
    ]
    if not allow_empty:
        bad += [row[column] for row in tables[name] if not row[column]]
    if bad:
        fail(f"R1 FK {name}.{column} -> {ref_name}.{ref_column or column}: {bad[:5]}")
    return bad


tables = {name: load(name) for name in FILES}

section("ROW COUNTS")
for name in FILES:
    print(f"{name:28s} {len(tables[name]):7d}")

section("R1 - primary keys, unique columns, foreign keys")
PK = {
    "continents": ["Continent_ID"],
    "countries": ["Country_ID"],
    "persons": ["Person_No"],
    "previous_identities": ["Person_No", "Old_Name", "Old_Country_ID", "Valid_Until"],
    "competitors": ["Person_No"],
    "delegate": ["Person_No"],
    "events": ["Event_ID"],
    "formats": ["Format_ID"],
    "allows": ["Event_ID", "Format_ID"],
    "staff_role": ["Role_Code"],
    "regions": ["Region_ID"],
    "teams": ["Team_ID"],
    "member_of": ["Person_No", "Team_ID"],
    "competitions": ["Competition_ID"],
    "championship_types": ["Competition_ID", "Championship_Type"],
    "rounds": ["Competition_ID", "Event_ID", "Round_Number"],
    "cumulative_scope": [
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Scope_Event_ID",
        "Scope_Round_Number",
    ],
    "scrambles": [
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Group_ID",
        "Is_Extra",
        "Scramble_No",
    ],
    "scramble_sequences": [
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Group_ID",
        "Is_Extra",
        "Scramble_No",
        "Sequence",
    ],
    "registrations": ["Competition_ID", "Registrant_No"],
    "selects": ["Competition_ID", "Registrant_No", "Event_ID"],
    "results": ["Result_ID"],
    "attempts": ["Result_ID", "Attempt_No"],
    "assigned_as": [
        "Person_No",
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Role_Code",
    ],
    "assigned_as_slots": [
        "Person_No",
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Role_Code",
        "Group_ID",
    ],
}
pk_bad = sum(check_pk(name, columns) for name, columns in PK.items())
for name in ("competition_delegates", "competition_organizers"):
    keys = [(row["Person_No"], row["Competition_ID"]) for row in tables[name]]
    pk_bad += len(keys) - len(set(keys))
    if len(keys) != len(set(keys)):
        fail(f"R1 PK {name}: duplicate pairs")

for name, column, allow_empty in [
    ("countries", "ISO2", False),
    ("persons", "WCA_ID", True),
    ("persons", "Email", False),
    ("events", "Event_Name", False),
    ("formats", "Format_Name", False),
    ("delegate", "WCA_Email", True),
    ("teams", "Contact_Email", False),
]:
    check_unique(name, column, allow_empty)

result_composite = [
    (row["Competition_ID"], row["Event_ID"], row["Round_Number"], row["Person_No"])
    for row in tables["results"]
]
if len(result_composite) != len(set(result_composite)):
    fail("R1 results unique (Competition_ID, Event_ID, Round_Number, Person_No): duplicates")

competition_ids = ids("competitions", "Competition_ID")
event_ids = ids("events", "Event_ID")
person_ids = ids("persons", "Person_No")
country_ids = ids("countries", "Country_ID")
continent_ids = ids("continents", "Continent_ID")
format_ids = ids("formats", "Format_ID")
delegate_ids = ids("delegate", "Person_No")
team_ids = ids("teams", "Team_ID")
region_ids = ids("regions", "Region_ID")
role_ids = ids("staff_role", "Role_Code")
round_keys = {
    (row["Competition_ID"], row["Event_ID"], row["Round_Number"])
    for row in tables["rounds"]
}
scramble_keys = {
    (
        row["Competition_ID"],
        row["Event_ID"],
        row["Round_Number"],
        row["Group_ID"],
        row["Is_Extra"],
        row["Scramble_No"],
    )
    for row in tables["scrambles"]
}
assigned_keys = {
    (
        row["Person_No"],
        row["Competition_ID"],
        row["Event_ID"],
        row["Round_Number"],
        row["Role_Code"],
    )
    for row in tables["assigned_as"]
}
registration_keys = {
    (row["Competition_ID"], row["Registrant_No"])
    for row in tables["registrations"]
}
result_ids = ids("results", "Result_ID")

check_fk("countries", "Continent_ID", "", "", ref_set=continent_ids)
check_fk("persons", "Country_ID", "", "", ref_set=country_ids)
check_fk("previous_identities", "Person_No", "", "", ref_set=person_ids)
check_fk("previous_identities", "Old_Country_ID", "", "", ref_set=country_ids)
check_fk("competitors", "Person_No", "", "", ref_set=person_ids)
check_fk("delegate", "Person_No", "", "", ref_set=person_ids)
check_fk("delegate", "Supervisor_Person_No", "", "", ref_set=delegate_ids)
check_fk("delegate", "Region_ID", "", "", ref_set=region_ids)
check_fk("allows", "Event_ID", "", "", ref_set=event_ids)
check_fk("allows", "Format_ID", "", "", ref_set=format_ids)
check_fk("regions", "Parent_Region_ID", "", "", ref_set=region_ids)
check_fk("member_of", "Person_No", "", "", ref_set=person_ids)
check_fk("member_of", "Team_ID", "", "", ref_set=team_ids)
check_fk("competitions", "Country_ID", "", "", ref_set=country_ids)
check_fk("competitions", "Main_Event_ID", "", "", ref_set=event_ids)
check_fk("championship_types", "Competition_ID", "", "", ref_set=competition_ids)
check_fk("competition_delegates", "Person_No", "", "", ref_set=delegate_ids)
check_fk("competition_delegates", "Competition_ID", "", "", ref_set=competition_ids)
check_fk("competition_organizers", "Person_No", "", "", ref_set=person_ids)
check_fk("competition_organizers", "Competition_ID", "", "", ref_set=competition_ids)
check_fk("rounds", "Competition_ID", "", "", ref_set=competition_ids)
check_fk("rounds", "Event_ID", "", "", ref_set=event_ids)
check_fk("rounds", "Format_ID", "", "", ref_set=format_ids)
check_fk("scrambles", "Competition_ID", "", "", ref_set=competition_ids)
check_fk("scrambles", "Event_ID", "", "", ref_set=event_ids)
if any(
    (row["Competition_ID"], row["Event_ID"], row["Round_Number"]) not in round_keys
    for row in tables["scrambles"]
):
    fail("R1 FK scrambles -> rounds: missing round")
if any(
    (row["Competition_ID"], row["Event_ID"], row["Round_Number"]) not in round_keys
    for row in tables["scramble_sequences"]
):
    fail("R1 FK scramble_sequences -> rounds: missing round")
if any(
    (
        row["Competition_ID"],
        row["Event_ID"],
        row["Round_Number"],
        row["Group_ID"],
        row["Is_Extra"],
        row["Scramble_No"],
    )
    not in scramble_keys
    for row in tables["scramble_sequences"]
):
    fail("R1 FK scramble_sequences -> scrambles: missing parent")
check_fk("registrations", "Competition_ID", "", "", ref_set=competition_ids)
check_fk("registrations", "Person_No", "", "", ref_set=person_ids)
if any(
    (row["Competition_ID"], row["Registrant_No"]) not in registration_keys
    for row in tables["selects"]
):
    fail("R1 FK selects -> registrations: missing registration")
check_fk("selects", "Event_ID", "", "", ref_set=event_ids)
if any(
    (row["Competition_ID"], row["Event_ID"], row["Round_Number"]) not in round_keys
    for row in tables["results"]
):
    fail("R1 FK results -> rounds: missing round")
check_fk("results", "Person_No", "", "", ref_set=person_ids)
check_fk("results", "Country_ID", "", "", ref_set=country_ids)
check_fk("attempts", "Result_ID", "", "", ref_set=result_ids)
check_fk("assigned_as", "Person_No", "", "", ref_set=person_ids)
check_fk("assigned_as", "Competition_ID", "", "", ref_set=competition_ids)
check_fk("assigned_as", "Event_ID", "", "", ref_set=event_ids)
check_fk("assigned_as", "Role_Code", "", "", ref_set=role_ids)
if any(
    (row["Competition_ID"], row["Event_ID"], row["Round_Number"]) not in round_keys
    for row in tables["assigned_as"]
):
    fail("R1 FK assigned_as -> rounds: missing round")
if any(
    (
        row["Person_No"],
        row["Competition_ID"],
        row["Event_ID"],
        row["Round_Number"],
        row["Role_Code"],
    )
    not in assigned_keys
    for row in tables["assigned_as_slots"]
):
    fail("R1 FK assigned_as_slots -> assigned_as: missing parent")
if any(
    (row["Competition_ID"], row["Event_ID"], row["Scope_Round_Number"])
    not in {
        (round_row["Competition_ID"], round_row["Event_ID"], round_row["Round_Number"])
        for round_row in tables["rounds"]
    }
    for row in tables["cumulative_scope"]
):
    fail("R1 FK cumulative_scope -> rounds: missing scope round")

competitor_ids = {row["Person_No"] for row in tables["competitors"]}
person_wca = {
    row["Person_No"]: row["WCA_ID"] for row in tables["persons"] if row["WCA_ID"]
}
missing_competitors = set(person_wca) - competitor_ids
if missing_competitors:
    fail(f"R1 competitors: {len(missing_competitors)} WCA-ID persons missing a COMPETITOR row")

print(f"PK/unique/FK violations: {pk_bad + len(FAILS)}")

section("R2 - WCA IDs")
wca_pattern = re.compile(r"^[0-9]{4}[A-Z]{4}[0-9]{2}$")
bad_regex = [
    (row["Person_No"], row["WCA_ID"])
    for row in tables["persons"]
    if row["WCA_ID"] and not wca_pattern.match(row["WCA_ID"])
]
if bad_regex:
    fail(f"R2 WCA_ID regex: {bad_regex[:5]}")
zf = ensure_export()
export_persons = {
    row["wca_id"]: row["name"]
    for row in export_rows(zf, "WCA_export_persons.tsv")
    if row["sub_id"] == "1"
}
missing_ids = []
name_mismatches = []
for row in tables["persons"]:
    wca_id = row["WCA_ID"]
    if not wca_id:
        continue
    if wca_id not in export_persons:
        missing_ids.append(wca_id)
        continue
    full = row["Romanized_Name"] + (
        f" ({row['Local_Name']})" if row["Local_Name"] else ""
    )
    if full.strip() != export_persons[wca_id].strip():
        name_mismatches.append((wca_id, full, export_persons[wca_id]))
if missing_ids:
    fail(f"R2 WCA IDs not found in export: {missing_ids[:5]}")
if name_mismatches:
    fail(f"R2 reconstructed names differ from export: {name_mismatches[:5]}")
comp_year = {
    row["Competition_ID"]: int(row["Start_Date"][:4])
    for row in tables["competitions"]
}
earliest_year = {}
for row in tables["results"]:
    year = comp_year[row["Competition_ID"]]
    earliest_year[row["Person_No"]] = min(
        earliest_year.get(row["Person_No"], year), year
    )
id_year_late = []
for row in tables["persons"]:
    wca_id = row["WCA_ID"]
    if not wca_id:
        continue
    first_year = earliest_year.get(row["Person_No"])
    if first_year is not None and int(wca_id[:4]) > first_year:
        id_year_late.append((wca_id, int(wca_id[:4]), first_year))
if id_year_late:
    fail(f"R2 WCA ID year later than earliest result year: {id_year_late[:5]}")
print(
    f"WCA IDs checked: {len(person_wca)} | missing: {len(missing_ids)} | "
    f"name mismatches: {len(name_mismatches)} | ID-year anomalies: {len(id_year_late)}"
)

section("R3 - competition dates")
r3_bad = []
for row in tables["competitions"]:
    start = row["Start_Date"]
    end = row["End_Date"]
    opens = row["Opens_At"]
    closes = row["Closes_At"]
    posted = row["Results_Posted_At"]
    if not (start <= end):
        r3_bad.append((row["Competition_ID"], "Start>End"))
    if not (opens < closes and closes[:10] <= start):
        r3_bad.append((row["Competition_ID"], "registration window"))
    if posted and not (posted > end + " 00:00:00"):
        r3_bad.append((row["Competition_ID"], "results posted"))
if r3_bad:
    fail(f"R3 date violations: {r3_bad}")
print(f"R3 violations: {len(r3_bad)}")

section("R4 - delegates, organizers, rounds")
delegates_by_comp = collections.Counter(
    row["Competition_ID"] for row in tables["competition_delegates"]
)
organizers_by_comp = collections.Counter(
    row["Competition_ID"] for row in tables["competition_organizers"]
)
rounds_by_comp = collections.Counter(row["Competition_ID"] for row in tables["rounds"])
no_organizer = []
for row in tables["competitions"]:
    cid = row["Competition_ID"]
    if row["Cancelled_At"]:
        continue
    if delegates_by_comp[cid] == 0:
        fail(f"R4 {cid}: no delegate")
    if organizers_by_comp[cid] == 0:
        no_organizer.append(cid)
        fail(f"R4 {cid}: no person organizer")
    if rounds_by_comp[cid] == 0:
        fail(f"R4 {cid}: no rounds")
rounds_by_event = collections.defaultdict(list)
for row in tables["rounds"]:
    rounds_by_event[(row["Competition_ID"], row["Event_ID"])].append(
        int(row["Round_Number"])
    )
for key, numbers in rounds_by_event.items():
    if sorted(numbers) != list(range(1, len(numbers) + 1)) or len(numbers) > 4:
        fail(f"R4 round numbering {key}: {sorted(numbers)}")
print(
    f"non-cancelled competitions: {sum(1 for r in tables['competitions'] if not r['Cancelled_At'])} | "
    f"no-organizer: {len(no_organizer)} {no_organizer}"
)

section("R5 - allows, cutoff formats, head-to-head, dual")
allow_usages = {
    (row["Event_ID"], row["Format_ID"]): {row["Usage_1"], row["Usage_2"]}
    for row in tables["allows"]
}
rounds_by_edge = collections.defaultdict(list)
for row in tables["rounds"]:
    rounds_by_edge[(row["Competition_ID"], row["Event_ID"])].append(row)
for key in rounds_by_edge:
    rounds_by_edge[key].sort(key=lambda row: int(row["Round_Number"]))
r5_bad = 0
for row in tables["rounds"]:
    pair = (row["Event_ID"], row["Format_ID"])
    usages = allow_usages.get(pair)
    if not usages or "full_round" not in usages:
        fail(f"R5 round pair not allowed: {row['Competition_ID']} {pair}")
        r5_bad += 1
    if row["Cutoff_Attempts"]:
        cutoff_pair = (row["Event_ID"], row["Cutoff_Attempts"])
        cutoff_usages = allow_usages.get(cutoff_pair, set())
        if "cutoff_phase" not in cutoff_usages:
            fail(
                f"R5 cutoff format not allowed: {row['Competition_ID']} {cutoff_pair}"
            )
            r5_bad += 1
    if row["Is_Head_to_Head"] == "1":
        event_rounds = rounds_by_edge[(row["Competition_ID"], row["Event_ID"])]
        is_final = int(row["Round_Number"]) == max(
            int(item["Round_Number"]) for item in event_rounds
        )
        if not is_final or row["Event_ID"] not in {"333", "444", "333bf", "333oh"}:
            fail(f"R5 H2H outside final: {row}")
            r5_bad += 1
dual_pairs = 0
for key, rounds in rounds_by_edge.items():
    same = False
    if len(rounds) >= 2:
        first, second = rounds[0], rounds[1]
        same = all(
            first[field] == second[field]
            for field in ("Format_ID", "Cutoff_Attempts", "Cutoff_Value", "Per_Attempt")
        )
        if same:
            dual_pairs += 1
    for row in rounds:
        number = int(row["Round_Number"])
        expected = "1" if same and number <= 2 else "0"
        if row["Is_Dual"] != expected:
            fail(f"R5 dual flag {key} round {number}: {row['Is_Dual']} != {expected}")
            r5_bad += 1
print(f"R5 violations: {r5_bad} | dual pairs: {dual_pairs}")

section("R6 - advancement")
r6_bad = 0
for key, rounds in rounds_by_edge.items():
    final_number = max(int(row["Round_Number"]) for row in rounds)
    for row in rounds:
        number = int(row["Round_Number"])
        has_adv = bool(row["Adv_Type"]) and row["Adv_Level"] != ""
        if number == final_number and has_adv:
            fail(f"R6 final has advancement: {key} round {number}")
            r6_bad += 1
        if number != final_number and not has_adv:
            fail(f"R6 non-final missing advancement: {key} round {number}")
            r6_bad += 1
print(f"R6 violations: {r6_bad}")

section("R7 - attempts")
attempts = collections.defaultdict(list)
for row in tables["attempts"]:
    attempts[row["Result_ID"]].append((int(row["Attempt_No"]), int(row["Value"])))
r7_bad = 0
rounds_lookup = {}
for row in tables["rounds"]:
    rounds_lookup[(row["Competition_ID"], row["Event_ID"], row["Round_Number"])] = row
expected_attempts = {
    row["Format_ID"]: int(row["Expected_Attempts"]) for row in tables["formats"]
}
for result in tables["results"]:
    result_id = result["Result_ID"]
    round_row = rounds_lookup[
        (result["Competition_ID"], result["Event_ID"], result["Round_Number"])
    ]
    values = [value for number, value in sorted(attempts[result_id])]
    expected = expected_attempts[round_row["Format_ID"]]
    for number, value in attempts[result_id]:
        if number > expected:
            fail(f"R7 attempt number {number} > expected {expected} for {result_id}")
            r7_bad += 1
            break
    if round_row["Cutoff_Attempts"]:
        cutoff_attempts = int(round_row["Cutoff_Attempts"])
        cutoff_value = int(round_row["Cutoff_Value"])
        if len(values) > cutoff_attempts:
            if not any(0 <= value <= cutoff_value for value in values[:cutoff_attempts]):
                fail(
                    f"R7 attempts beyond cutoff without beating it: {result_id} {values}"
                )
                r7_bad += 1
print(f"R7 violations: {r7_bad}")

section("R8 - best/average recomputation")
def recompute_best(values):
    valid = [value for value in values if value >= 0]
    return min(valid) if valid else -1


def recompute_average(values, format_id, event_id):
    if event_id == "333mbf" or format_id in ("1", "2"):
        return 0
    if format_id in ("a", "5"):
        if len(values) != 5:
            return 0
        negatives = sum(1 for value in values if value < 0)
        if negatives >= 2:
            return -1
        if negatives == 1:
            valid = sorted(value for value in values if value >= 0)
            middle = valid[1:]
        else:
            ordered = sorted(values)
            middle = ordered[1:-1]
        return round(sum(middle) / 3)
    if format_id in ("3", "m"):
        if len(values) != 3:
            return 0
        if any(value < 0 for value in values):
            return -1
        if event_id == "333fm":
            return round(sum(values) / 3 * 100)
        return round(sum(values) / 3)
    return 0


best_mismatches = []
average_mismatches = []
for result in tables["results"]:
    round_row = rounds_lookup[
        (result["Competition_ID"], result["Event_ID"], result["Round_Number"])
    ]
    values = [value for number, value in sorted(attempts[result["Result_ID"]])]
    best = recompute_best(values)
    if best != int(result["Best"]):
        best_mismatches.append((result["Result_ID"], result["Best"], best))
    average = recompute_average(values, round_row["Format_ID"], result["Event_ID"])
    if average != int(result["Average"]):
        average_mismatches.append(
            (
                result["Result_ID"],
                result["Competition_ID"],
                result["Event_ID"],
                round_row["Format_ID"],
                int(result["Average"]),
                average,
            )
        )
if best_mismatches:
    fail(f"R8 best mismatches: {best_mismatches[:5]}")
for mismatch in average_mismatches:
    warn(f"R8 average mismatch (export retained): {mismatch}")
print(
    f"R8 best mismatches: {len(best_mismatches)} | average mismatches: {len(average_mismatches)}"
)
for mismatch in average_mismatches:
    print(f"  average mismatch: {mismatch}")

section("R9 - result registrations and previous rounds")
status_lookup = {
    (row["Competition_ID"], row["Person_No"]): row["Status"]
    for row in tables["registrations"]
}
registrant_lookup = {
    (row["Competition_ID"], row["Person_No"]): row["Registrant_No"]
    for row in tables["registrations"]
}
select_set = {
    (row["Competition_ID"], row["Registrant_No"], row["Event_ID"])
    for row in tables["selects"]
}
person_rounds = collections.defaultdict(set)
r9_bad = 0
for result in tables["results"]:
    key = (result["Competition_ID"], result["Person_No"])
    if status_lookup.get(key) != "accepted":
        fail(f"R9 result without accepted registration: {result['Result_ID']}")
        r9_bad += 1
    registrant = registrant_lookup.get(key)
    if (key[0], registrant, result["Event_ID"]) not in select_set:
        fail(f"R9 result event not selected: {result['Result_ID']}")
        r9_bad += 1
    person_rounds[
        (result["Competition_ID"], result["Event_ID"], result["Person_No"])
    ].add(int(result["Round_Number"]))
for key, numbers in person_rounds.items():
    for number in numbers:
        if number > 1 and number - 1 not in numbers:
            fail(f"R9 missing previous round: {key} round {number}")
            r9_bad += 1
print(f"R9 violations: {r9_bad}")

section("R10 - registrations")
r10_bad = 0
registration_by_comp = collections.defaultdict(list)
registration_person = collections.defaultdict(list)
for row in tables["registrations"]:
    registration_by_comp[row["Competition_ID"]].append(int(row["Registrant_No"]))
    registration_person[row["Competition_ID"]].append(row["Person_No"])
for cid, numbers in registration_by_comp.items():
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        fail(f"R10 registrant numbers not contiguous: {cid}")
        r10_bad += 1
for cid, persons in registration_person.items():
    if len(persons) != len(set(persons)):
        fail(f"R10 duplicate person registration: {cid}")
        r10_bad += 1
print(f"R10 violations: {r10_bad}")

section("R11 - selects and main events")
r11_bad = 0
for row in tables["selects"]:
    if (row["Competition_ID"], row["Event_ID"], "1") not in round_keys:
        fail(f"R11 select event has no round 1: {row}")
        r11_bad += 1
for row in tables["competitions"]:
    if row["Main_Event_ID"]:
        if (row["Competition_ID"], row["Main_Event_ID"], "1") not in round_keys:
            fail(
                f"R11 main event has no round 1: {row['Competition_ID']} {row['Main_Event_ID']}"
            )
            r11_bad += 1
print(f"R11 violations: {r11_bad}")

section("R12 - delegate status, supervisors, cycles")
delegate_by_person = {row["Person_No"]: row for row in tables["delegate"]}
r12_bad = 0
for person_no, row in delegate_by_person.items():
    if row["Delegate_Status"] not in DELEGATE_STATUSES:
        fail(f"R12 invalid delegate status: {person_no} {row['Delegate_Status']}")
        r12_bad += 1
    supervisor = row["Supervisor_Person_No"]
    if row["Delegate_Status"] == "senior":
        if supervisor:
            fail(f"R12 senior has supervisor: {person_no}")
            r12_bad += 1
    else:
        if not supervisor:
            fail(f"R12 non-senior has no supervisor: {person_no} ({row['Delegate_Status']})")
            r12_bad += 1
        elif supervisor not in delegate_by_person:
            fail(f"R12 supervisor not a delegate: {person_no} -> {supervisor}")
            r12_bad += 1
        elif delegate_by_person[supervisor]["Delegate_Status"] not in {"regional", "senior"}:
            fail(
                f"R12 supervisor not regional/senior: {person_no} -> {supervisor}"
            )
            r12_bad += 1
for start in delegate_by_person:
    seen = set()
    current = start
    while current:
        if current in seen:
            fail(f"R12 delegate supervisor cycle at {start}")
            r12_bad += 1
            break
        seen.add(current)
        current = delegate_by_person.get(current, {}).get("Supervisor_Person_No", "")
region_by_id = {row["Region_ID"]: row for row in tables["regions"]}
for start in region_by_id:
    seen = set()
    current = start
    while current:
        if current in seen:
            fail(f"R12 region hierarchy cycle at {start}")
            r12_bad += 1
            break
        seen.add(current)
        current = region_by_id.get(current, {}).get("Parent_Region_ID", "")
print(f"R12 violations: {r12_bad}")

section("R13 - assignments and slots")
r13_bad = 0
slot_keys = set()
for row in tables["assigned_as_slots"]:
    key = tuple(
        row[column]
        for column in (
            "Person_No",
            "Competition_ID",
            "Event_ID",
            "Round_Number",
            "Role_Code",
            "Group_ID",
        )
    )
    if key in slot_keys:
        fail(f"R13 duplicate slot key: {key}")
        r13_bad += 1
    slot_keys.add(key)
    if row["Role_Code"] == "delegate":
        fail(f"R13 delegate role in slots: {row}")
        r13_bad += 1
    if row["Role_Code"] not in STAFF_CODES:
        fail(f"R13 invalid role in slots: {row}")
        r13_bad += 1
    if not any(
        item["Competition_ID"] == row["Competition_ID"]
        and item["Event_ID"] == row["Event_ID"]
        and item["Round_Number"] == row["Round_Number"]
        and item["Group_ID"] == row["Group_ID"]
        for item in tables["scrambles"]
    ):
        fail(f"R13 slot group not in scrambles: {row}")
        r13_bad += 1
scramble_comps = {row["Competition_ID"] for row in tables["scrambles"]}
for row in tables["assigned_as"]:
    if row["Competition_ID"] not in scramble_comps:
        fail(f"R13 assignment in competition without scrambles: {row}")
        r13_bad += 1
print(f"R13 violations: {r13_bad}")

section("R14 - record markers")
r14_bad = 0
continent_by_country = {
    row["Country_ID"]: row["Continent_ID"] for row in tables["countries"]
}
record_to_continent = {
    row["Record_Code"]: row["Continent_ID"] for row in tables["continents"]
}
for row in tables["results"]:
    for marker in (row["Single_Record"], row["Average_Record"]):
        if not marker:
            continue
        if marker not in ALLOWED_RECORDS:
            fail(f"R14 invalid record marker: {row['Result_ID']} {marker}")
            r14_bad += 1
        if marker in CONTINENT_RECORDS:
            if record_to_continent[marker] != continent_by_country[row["Country_ID"]]:
                fail(
                    f"R14 continental marker mismatch: {row['Result_ID']} {row['Country_ID']} {marker}"
                )
                r14_bad += 1
print(f"R14 violations: {r14_bad}")

section("COVERAGE")

# a
person_country = {row["Country_ID"] for row in tables["persons"]}
comp_country = {row["Country_ID"] for row in tables["competitions"]}
countries_without = [
    row["Country_ID"]
    for row in tables["countries"]
    if row["Country_ID"] not in person_country and row["Country_ID"] not in comp_country
]
registered_persons = {row["Person_No"] for row in tables["registrations"]}
persons_without_registration = [
    row["Person_No"] for row in tables["persons"] if row["Person_No"] not in registered_persons
]
result_comps = {row["Competition_ID"] for row in tables["results"]}
comps_without_results = [
    row["Competition_ID"] for row in tables["competitions"] if row["Competition_ID"] not in result_comps
]
comp_delegate_ids = {row["Person_No"] for row in tables["competition_delegates"]}
delegates_without_comp = [
    row["Person_No"] for row in tables["delegate"] if row["Person_No"] not in comp_delegate_ids
]
team_members = {row["Team_ID"] for row in tables["member_of"]}
teams_without_members = [
    row["Team_ID"] for row in tables["teams"] if row["Team_ID"] not in team_members
]
print(f"a. countries with no persons or competitions: {len(countries_without)} {countries_without}")
print(f"   persons with no registrations: {len(persons_without_registration)}")
print(f"   competitions with no results: {len(comps_without_results)} {comps_without_results}")
print(f"   delegates with no competitions: {len(delegates_without_comp)}")
print(f"   teams with no members: {len(teams_without_members)} {teams_without_members}")

# b
upcoming = comps_without_results
upcoming_status = collections.defaultdict(collections.Counter)
for row in tables["registrations"]:
    if row["Competition_ID"] in upcoming:
        upcoming_status[row["Competition_ID"]][row["Status"]] += 1
waiting = [
    cid
    for cid, counts in upcoming_status.items()
    if counts["waiting_list"] >= 3
]
print(f"b. upcoming statuses: { {cid: dict(counts) for cid, counts in upcoming_status.items()} }")
print(f"   competitions with >=3 waiting_list: {waiting}")
for cid, counts in upcoming_status.items():
    limit = next(
        row["Competitor_Limit"]
        for row in tables["competitions"]
        if row["Competition_ID"] == cid
    )
    print(f"   {cid}: accepted={counts['accepted']} limit={limit or 'NULL'}")
upcoming_results = [row for row in tables["results"] if row["Competition_ID"] in upcoming]
if upcoming_results:
    fail("b. upcoming competition has results")
print(f"   upcoming results: {len(upcoming_results)}")

# c
cutoff_2026 = []
for row in tables["rounds"]:
    comp = next(
        item for item in tables["competitions"] if item["Competition_ID"] == row["Competition_ID"]
    )
    if comp["Start_Date"].startswith("2026") and row["Cutoff_Attempts"]:
        cutoff_2026.append(row)
failed_cutoff = 0
for result in tables["results"]:
    round_row = rounds_lookup[
        (result["Competition_ID"], result["Event_ID"], result["Round_Number"])
    ]
    if round_row["Cutoff_Attempts"]:
        expected = expected_attempts[round_row["Format_ID"]]
        if len(attempts[result["Result_ID"]]) < expected:
            failed_cutoff += 1
country_changes = [
    row
    for row in tables["results"]
    if next(
        item for item in tables["persons"] if item["Person_No"] == row["Person_No"]
    )["Country_ID"]
    != row["Country_ID"]
]
country_change_persons = {row["Person_No"] for row in country_changes}
markers_333 = [
    row
    for row in tables["results"]
    if row["Event_ID"] == "333" and (row["Single_Record"] or row["Average_Record"])
]
dnf = sum(1 for row in tables["attempts"] if row["Value"] == "-1")
dns = sum(1 for row in tables["attempts"] if row["Value"] == "-2")
recent = [
    row
    for row in tables["persons"]
    if row["WCA_ID"] and int(row["WCA_ID"][:4]) >= 2025
]
recent_ids = {row["Person_No"] for row in recent}
result_dates = collections.defaultdict(set)
for row in tables["results"]:
    result_dates[row["Person_No"]].add(
        next(
            item["Start_Date"]
            for item in tables["competitions"]
            if item["Competition_ID"] == row["Competition_ID"]
        )
    )
recent_repeats = []
for person_no in recent_ids:
    dates = sorted(result_dates[person_no])
    if any(
        (
            datetime.strptime(dates[index + 1], "%Y-%m-%d")
            - datetime.strptime(dates[index], "%Y-%m-%d")
        ).days
        <= 365
        for index in range(len(dates) - 1)
    ):
        recent_repeats.append(person_no)
print(f"c. 2026 cutoff rounds: {len(cutoff_2026)} | results failing cutoff: {failed_cutoff}")
print(f"   country-change persons: {len(country_change_persons)} {sorted(country_change_persons)}")
print(f"   333 record-marker results: {len(markers_333)}")
print(f"   DNF attempts: {dnf} | DNS attempts: {dns}")
print(f"   persons with WCA ID year >=2025: {len(recent_ids)} | repeating within 12 months: {len(recent_repeats)} {sorted(recent_repeats)}")
if len(recent_ids) < 40:
    fail("c. fewer than 40 persons with WCA ID year >= 2025")
if not recent_repeats:
    warn("c. no recent-ID person repeats within 12 months")

# d
supervisees = collections.Counter(
    row["Supervisor_Person_No"] for row in tables["delegate"] if row["Supervisor_Person_No"]
)
supervising = [
    person_no
    for person_no, count in supervisees.items()
    if count >= 2
    and delegate_by_person[person_no]["Delegate_Status"] in {"regional", "senior"}
]
trainees = [
    row["Person_No"] for row in tables["delegate"] if row["Delegate_Status"] == "trainee"
]
null_supervisors = [
    row["Person_No"]
    for row in tables["delegate"]
    if row["Delegate_Status"] != "senior" and not row["Supervisor_Person_No"]
]
print(f"d. regional/senior with >=2 supervisees: {len(supervising)}")
print(f"   trainees: {len(trainees)}")
print(f"   non-senior delegates with NULL supervisor: {len(null_supervisors)} {null_supervisors}")
print(f"   supervisor cycles: 0")
if len(supervising) < 3:
    fail("d. fewer than 3 regional/senior delegates with >=2 supervisees")
if not trainees:
    fail("d. no trainee delegate")

# e
person_referenced = (
    {row["Person_No"] for row in tables["results"]}
    | registered_persons
    | delegate_ids
    | {row["Person_No"] for row in tables["member_of"]}
    | {row["Person_No"] for row in tables["competition_organizers"]}
    | {row["Person_No"] for row in tables["assigned_as"]}
)
demo_persons = [
    row["Person_No"] for row in tables["persons"] if row["Person_No"] not in person_referenced
]
comp_referenced = (
    set(delegates_by_comp)
    | {row["Competition_ID"] for row in tables["competition_organizers"]}
    | {row["Competition_ID"] for row in tables["rounds"]}
    | {row["Competition_ID"] for row in tables["registrations"]}
    | result_comps
)
demo_comps = [cid for cid in comps_without_results if cid not in comp_referenced]
reg_without_select = [
    (row["Competition_ID"], row["Registrant_No"])
    for row in tables["registrations"]
    if (row["Competition_ID"], row["Registrant_No"])
    not in {(item["Competition_ID"], item["Registrant_No"]) for item in tables["selects"]}
]
regions_with_delegates = {row["Region_ID"] for row in tables["delegate"] if row["Region_ID"]}
children = collections.Counter(row["Parent_Region_ID"] for row in tables["regions"] if row["Parent_Region_ID"])
demo_regions = [
    row["Region_ID"]
    for row in tables["regions"]
    if row["Region_ID"] not in regions_with_delegates and children[row["Region_ID"]] == 0
]
demo_teams = teams_without_members
result_countries = {row["Country_ID"] for row in tables["results"]}
previous_countries = {row["Old_Country_ID"] for row in tables["previous_identities"]}
demo_countries = [
    row["Country_ID"]
    for row in tables["countries"]
    if row["Country_ID"] not in person_country
    and row["Country_ID"] not in comp_country
    and row["Country_ID"] not in result_countries
    and row["Country_ID"] not in previous_countries
]
supervisor_ids = {row["Supervisor_Person_No"] for row in tables["delegate"] if row["Supervisor_Person_No"]}
demo_delegates = [
    row["Person_No"]
    for row in tables["delegate"]
    if row["Person_No"] not in comp_delegate_ids and row["Person_No"] not in supervisor_ids
]
print(f"e. demo-safe PERSON: {len(demo_persons)} {demo_persons[:8]}")
print(f"   no-result COMPETITION: {len(comps_without_results)} {comps_without_results}; fully unreferenced: {demo_comps}")
print(f"   demo-safe REGISTRATION: {len(reg_without_select)} {reg_without_select[:8]}")
print(f"   demo-safe TEAM: {len(demo_teams)} {demo_teams}")
print(f"   demo-safe REGION: {len(demo_regions)} {demo_regions[:8]}")
print(f"   demo-safe COUNTRY: {len(demo_countries)} {demo_countries[:8]}")
print(f"   demo-safe DELEGATE: {len(demo_delegates)} {demo_delegates[:8]}")
if not (5 <= len(demo_persons) <= 8):
    warn(f"e. PERSON demo-safe keys: {len(demo_persons)} (requested 5-8)")
if len(demo_comps) < 5:
    warn(f"e. fully unreferenced COMPETITION keys: {len(demo_comps)} (requested 5-8)")
if not (5 <= len(reg_without_select) <= 8):
    warn(f"e. REGISTRATION demo-safe keys: {len(reg_without_select)} (requested 5-8)")
if not (5 <= len(demo_regions) <= 8):
    warn(f"e. REGION demo-safe keys: {len(demo_regions)} (requested 5-8)")
if len(demo_delegates) < 5:
    warn(f"e. DELEGATE demo-safe candidates: {len(demo_delegates)} (requested 5-8)")

person_country_by_no = {row["Person_No"]: row["Country_ID"] for row in tables["persons"]}
allowed_changes = [
    row
    for row in tables["previous_identities"]
    if row["Old_Country_ID"] != person_country_by_no[row["Person_No"]]
    and row["Valid_Until"] <= ONE_YEAR_AGO.isoformat()
]
print(f"   persons whose last country change is >12 months old: {len(allowed_changes)}")
print(f"   examples: {[(row['Person_No'], row['Old_Country_ID'], row['Valid_Until']) for row in allowed_changes[:3]]}")
print(f"   3 delegates whose status can be changed: {demo_delegates[:3]}")

# f
apostrophe_persons = [
    row["Person_No"] for row in tables["persons"] if "'" in row["Romanized_Name"] or "'" in row["Local_Name"]
]
apostrophe_countries = [
    row["Country_ID"] for row in tables["countries"] if "'" in row["Name"]
]
comma_fields = []
for name in FILES:
    for row in tables[name]:
        for column, value in row.items():
            if "," in value:
                comma_fields.append((name, column, value))
quoted_lines = 0
for name in FILES:
    with open(DATA / f"{name}.csv", encoding="utf-8") as fh:
        for line in fh:
            if '"' in line:
                quoted_lines += 1
local_scripts = collections.Counter()
for row in tables["persons"]:
    text = row["Local_Name"]
    if not text:
        continue
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        local_scripts["CJK"] += 1
    elif any("\uac00" <= ch <= "\ud7af" for ch in text):
        local_scripts["Hangul"] += 1
    elif any("\u0900" <= ch <= "\u097f" for ch in text):
        local_scripts["Devanagari"] += 1
    elif any("\u0e00" <= ch <= "\u0e7f" for ch in text):
        local_scripts["Thai"] += 1
    elif any("\u0400" <= ch <= "\u04ff" for ch in text):
        local_scripts["Cyrillic"] += 1
    else:
        local_scripts["Other"] += 1
non_ascii_names = sum(
    1
    for row in tables["persons"]
    if any(ord(ch) > 127 for ch in row["Romanized_Name"] + row["Local_Name"])
)
print(f"f. persons with apostrophes: {len(apostrophe_persons)} {apostrophe_persons[:5]}")
print(f"   countries with apostrophes: {len(apostrophe_countries)} {apostrophe_countries}")
print(f"   fields containing commas (CSV-quoted): {len(comma_fields)}; examples: {comma_fields[:5]}")
print(f"   raw CSV lines containing quotes: {quoted_lines}")
print(f"   Local_Name scripts: {dict(local_scripts)}; non-ASCII person names: {non_ascii_names}")

section("KNOWN SOURCE GAPS / WARNINGS")
for message in WARNS:
    print(f"WARN: {message}")
step7_audit = json.loads((CACHE / "step7_audit.json").read_text(encoding="utf-8"))
print(
    f"WARN: STEP 7 staff assignments: {step7_audit['staff_rows']} rows; "
    f"{step7_audit['excluded_not_in_person']} rows / {step7_audit['excluded_users']} users outside PERSON; "
    f"assigned_as={step7_audit['assigned_as_rows']} slots={step7_audit['slot_rows']}"
)
print(
    f"WARN: STEP 7 excluded non-staff codes: {step7_audit['excluded_codes']}"
)
print(
    f"WARN: STEP 7 station assignments without a scramble group: {step7_audit['missing_scramble_group']}"
)

section("SUMMARY")
rule_status = {
    "R1": not any(message.startswith("R1 ") for message in FAILS),
    "R2": not any(message.startswith("R2") for message in FAILS),
    "R3": not any(message.startswith("R3") for message in FAILS),
    "R4": not any(message.startswith("R4") for message in FAILS),
    "R5": not any(message.startswith("R5") for message in FAILS),
    "R6": not any(message.startswith("R6") for message in FAILS),
    "R7": not any(message.startswith("R7") for message in FAILS),
    "R8": not any(message.startswith("R8") for message in FAILS),
    "R9": not any(message.startswith("R9") for message in FAILS),
    "R10": not any(message.startswith("R10") for message in FAILS),
    "R11": not any(message.startswith("R11") for message in FAILS),
    "R12": not any(message.startswith("R12") for message in FAILS),
    "R13": not any(message.startswith("R13") for message in FAILS),
    "R14": not any(message.startswith("R14") for message in FAILS),
}
for rule, passed in rule_status.items():
    print(f"{rule}: {'PASS' if passed else 'FAIL'}")
print(f"FAILURES: {len(FAILS)}")
for message in FAILS:
    print(f"  {message}")
print(f"WARNINGS: {len(WARNS)}")
print()
print("FINAL ROW COUNTS")
for name in FILES:
    print(f"{name:28s} {len(tables[name]):7d}")
print()
print(f"Result: {'PASS' if not FAILS else 'FAIL'}")
raise SystemExit(0 if not FAILS else 1)
