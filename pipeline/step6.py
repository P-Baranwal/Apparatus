#!/usr/bin/env python3

import csv
import collections
import json

from common import (
    CACHE,
    DATA,
    ensure_export,
    export_rows,
    selected_results,
)

ALLOWED_RECORDS = {"WR", "AfR", "AsR", "ER", "NAR", "OcR", "SAR", "NR"}
CONTINENT_RECORDS = {"AfR", "AsR", "ER", "NAR", "OcR", "SAR"}


def write_csv(name, header, rows):
    path = DATA / name
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{name:28s} {len(rows):6d} rows -> {path}")


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


competitions = {
    row["Competition_ID"]: row
    for row in csv.DictReader(open(DATA / "competitions.csv", encoding="utf-8"))
}
formats = {
    row["Format_ID"]: int(row["Expected_Attempts"])
    for row in csv.DictReader(open(DATA / "formats.csv", encoding="utf-8"))
}
allows = {
    (row["Event_ID"], row["Format_ID"])
    for row in csv.DictReader(open(DATA / "allows.csv", encoding="utf-8"))
}
round_rows = list(csv.DictReader(open(DATA / "rounds.csv", encoding="utf-8")))
rounds_by_comp_event = collections.defaultdict(list)
round_by_key = {}
for row in round_rows:
    rounds_by_comp_event[(row["Competition_ID"], row["Event_ID"])].append(row)
    round_by_key[(row["Competition_ID"], row["Event_ID"], row["Round_Number"])] = row
for key in rounds_by_comp_event:
    rounds_by_comp_event[key].sort(key=lambda row: int(row["Round_Number"]))
countries = {
    row["Country_ID"]: row
    for row in csv.DictReader(open(DATA / "countries.csv", encoding="utf-8"))
}
continents = {
    row["Continent_ID"]: row
    for row in csv.DictReader(open(DATA / "continents.csv", encoding="utf-8"))
}
record_to_continent = {
    row["Record_Code"]: row["Continent_ID"] for row in continents.values()
}
registry = json.loads(
    (CACHE / "person_registry.json").read_text(encoding="utf-8")
)
wid_to_pno = {
    row["wca_id"]: row["person_no"] for row in registry.values() if row["wca_id"]
}
wid_to_country = {
    row["wca_id"]: row["country_id"] for row in registry.values() if row["wca_id"]
}
registrations = list(
    csv.DictReader(open(DATA / "registrations.csv", encoding="utf-8"))
)
selects = list(csv.DictReader(open(DATA / "selects.csv", encoding="utf-8")))
registration_status = {
    (row["Competition_ID"], int(row["Person_No"])): row["Status"]
    for row in registrations
}
registrant_no = {
    (row["Competition_ID"], int(row["Person_No"])): int(row["Registrant_No"])
    for row in registrations
}
select_keys = {
    (row["Competition_ID"], int(row["Registrant_No"]), row["Event_ID"])
    for row in selects
}

results = selected_results()
result_by_id = {row["id"]: row for row in results}
assert len(result_by_id) == len(results)

zf = ensure_export()
round_type_rank = {
    row["id"]: int(row["rank"])
    for row in export_rows(zf, "WCA_export_round_types.tsv")
}
types_by_event = collections.defaultdict(set)
format_by_type = {}
for row in results:
    key = (row["competition_id"], row["event_id"])
    types_by_event[key].add(row["round_type_id"])
    format_by_type[(key[0], key[1], row["round_type_id"])] = row["format_id"]

round_type_to_round = {}
for key, types in types_by_event.items():
    wcif_rounds = rounds_by_comp_event[key]
    ordered_types = sorted(types, key=lambda value: round_type_rank[value])
    assert len(wcif_rounds) == len(ordered_types), (key, len(wcif_rounds), len(ordered_types))
    for round_row, round_type in zip(wcif_rounds, ordered_types):
        assert round_row["Format_ID"] == format_by_type[(key[0], key[1], round_type)], (
            key,
            round_type,
        )
        round_type_to_round[(key[0], key[1], round_type)] = int(round_row["Round_Number"])

result_rows = []
for row in results:
    round_number = round_type_to_round[
        (row["competition_id"], row["event_id"], row["round_type_id"])
    ]
    single_record = "" if row["regional_single_record"] == "NULL" else row["regional_single_record"]
    average_record = "" if row["regional_average_record"] == "NULL" else row["regional_average_record"]
    result_rows.append(
        [
            int(row["id"]),
            row["competition_id"],
            row["event_id"],
            round_number,
            wid_to_pno[row["person_id"]],
            row["person_country_id"],
            int(row["best"]),
            int(row["average"]),
            int(row["pos"]),
            single_record,
            average_record,
        ]
    )
result_rows.sort(key=lambda row: (row[1], row[2], row[3], row[8], row[4]))
assert len({row[0] for row in result_rows}) == len(result_rows)
assert len({(row[1], row[2], row[3], row[4]) for row in result_rows}) == len(result_rows)

attempt_cache = CACHE / "selected_attempts.tsv"
if not attempt_cache.exists():
    rows = []
    for row in export_rows(zf, "WCA_export_result_attempts.tsv"):
        if row["result_id"] in result_by_id:
            rows.append(
                (int(row["result_id"]), int(row["attempt_number"]), int(row["value"]))
            )
    rows.sort(key=lambda item: (item[0], item[1]))
    with open(attempt_cache, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["result_id", "attempt_number", "value"])
        writer.writerows(rows)

attempts = collections.defaultdict(list)
attempt_rows = []
for row in csv.DictReader(open(attempt_cache, encoding="utf-8")):
    result_id = int(row["result_id"])
    attempt_no = int(row["attempt_number"])
    value = int(row["value"])
    expected = formats[result_by_id[str(result_id)]["format_id"]]
    assert 1 <= attempt_no <= expected, (result_id, attempt_no, expected)
    assert value >= -2 and value != 0, (result_id, attempt_no, value)
    attempts[str(result_id)].append((attempt_no, value))
    attempt_rows.append([result_id, attempt_no, value])
attempt_rows.sort(key=lambda row: (row[0], row[1]))
assert len({(row[0], row[1]) for row in attempt_rows}) == len(attempt_rows)
assert set(attempts) == set(result_by_id)

attempt_order_violations = []
for result_id, rows in attempts.items():
    numbers = sorted(number for number, value in rows)
    if numbers != list(range(1, len(numbers) + 1)):
        attempt_order_violations.append((result_id, numbers))

best_mismatches = []
average_mismatches = []
r7_violations = []
r9_registration_violations = []
r9_previous_violations = []
r5_violations = []
r14_violations = []
person_rounds = collections.defaultdict(set)
for row in results:
    result_id = row["id"]
    person_no = wid_to_pno[row["person_id"]]
    round_number = round_type_to_round[
        (row["competition_id"], row["event_id"], row["round_type_id"])
    ]
    person_rounds[(row["competition_id"], row["event_id"], person_no)].add(round_number)
    values = [value for number, value in sorted(attempts[result_id])]
    best = recompute_best(values)
    if best != int(row["best"]):
        best_mismatches.append((result_id, row["best"], best))
    average = recompute_average(values, row["format_id"], row["event_id"])
    if average != int(row["average"]):
        average_mismatches.append(
            (
                result_id,
                row["competition_id"],
                row["event_id"],
                row["format_id"],
                int(row["average"]),
                average,
                values,
            )
        )
    round_row = round_by_key[(row["competition_id"], row["event_id"], str(round_number))]
    if round_row["Cutoff_Attempts"]:
        cutoff_attempts = int(round_row["Cutoff_Attempts"])
        cutoff_value = int(round_row["Cutoff_Value"])
        if len(values) > cutoff_attempts:
            if not any(0 <= value <= cutoff_value for value in values[:cutoff_attempts]):
                r7_violations.append(
                    (result_id, row["competition_id"], row["event_id"], round_number, values)
                )
    if registration_status.get((row["competition_id"], person_no)) != "accepted":
        r9_registration_violations.append((result_id, "status"))
    registrant = registrant_no.get((row["competition_id"], person_no))
    if (row["competition_id"], registrant, row["event_id"]) not in select_keys:
        r9_registration_violations.append((result_id, "select"))
    if round_row["Format_ID"] != row["format_id"]:
        r5_violations.append((result_id, "format"))
    if (row["event_id"], row["format_id"]) not in allows:
        r5_violations.append((result_id, "allows"))
    for marker in (row["regional_single_record"], row["regional_average_record"]):
        if marker in CONTINENT_RECORDS:
            continent = countries[row["person_country_id"]]["Continent_ID"]
            if record_to_continent[marker] != continent:
                r14_violations.append((result_id, row["person_country_id"], marker))
        if marker != "NULL" and marker not in ALLOWED_RECORDS:
            r14_violations.append((result_id, "marker", marker))

for key, round_numbers in person_rounds.items():
    for round_number in round_numbers:
        if round_number > 1 and round_number - 1 not in round_numbers:
            r9_previous_violations.append((key, sorted(round_numbers)))

write_csv(
    "results.csv",
    [
        "Result_ID",
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Person_No",
        "Country_ID",
        "Best",
        "Average",
        "Position",
        "Single_Record",
        "Average_Record",
    ],
    result_rows,
)
write_csv(
    "attempts.csv",
    ["Result_ID", "Attempt_No", "Value"],
    attempt_rows,
)

record_single = collections.Counter(
    row[9] for row in result_rows if row[9]
)
record_average = collections.Counter(
    row[10] for row in result_rows if row[10]
)
attempt_values = collections.Counter(
    "DNF" if row[2] == -1 else "DNS" if row[2] == -2 else "positive"
    for row in attempt_rows
)
pool_results = sum(
    1
    for row in results
    if row["competition_id"]
    in {"WC2025", "WC2023", "RubiksWCAAsianChampionship2024"}
)
country_changes = {
    row["person_id"]
    for row in results
    if row["person_country_id"] != wid_to_country[row["person_id"]]
}
max_park = sum(1 for row in results if row["person_id"] == "2012PARK03")

print()
print(f"results: {len(result_rows)} | attempts: {len(attempt_rows)}")
print(f"single records: {dict(record_single)}")
print(f"average records: {dict(record_average)}")
print(f"attempt values: {dict(attempt_values)}")
print(f"best mismatches: {len(best_mismatches)} | average mismatches: {len(average_mismatches)}")
for row in average_mismatches:
    print(f"  avg mismatch: {row}")
print(f"R5 violations: {len(r5_violations)} | R7: {len(r7_violations)} | R9 status/select: {len(r9_registration_violations)} | R9 previous-round: {len(r9_previous_violations)} | R14: {len(r14_violations)}")
print(f"attempt sequence violations: {len(attempt_order_violations)}")
print(f"pool-based results: {pool_results} | country-change persons in results: {len(country_changes)} | Max Park results: {max_park}")
print(f"position range: {min(row[8] for row in result_rows)}..{max(row[8] for row in result_rows)}")
