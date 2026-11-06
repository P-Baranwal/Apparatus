#!/usr/bin/env python3

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from common import (
    CACHE,
    DATA,
    SHORTLIST,
    UPCOMING,
    competition,
    delegate_roles,
    delegates,
    ensure_export,
    export_rows,
    selected_results,
    teams,
    wcif,
)

EXCLUDED_TEAMS = {"wat", "wmt"}
ORG_TOKENS = (
    "association", "club", "federation", "team", "committee", "council",
    "cubing", "speedcubing", "speed cubing", "speedcubers", "treasurer",
    "organizing", "cubex", "rvce", "rvitm", "bppc", "cipher", "united",
    "culture",
)
DELEGATE_RANK = {
    "senior_delegate": 5,
    "regional_delegate": 4,
    "delegate": 3,
    "junior_delegate": 2,
    "trainee_delegate": 1,
}
STATUS_MAP = {
    "senior_delegate": "senior",
    "regional_delegate": "regional",
    "delegate": "full",
    "junior_delegate": "junior",
    "trainee_delegate": "trainee",
}
TEAM_RANK = {"leader": 3, "senior_member": 2, "member": 1}
NAME_RE = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")
WCA_RE = re.compile(r"^[0-9]{4}[A-Z]{4}[0-9]{2}$")


def write_csv(name, header, rows):
    path = DATA / name
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{name:28s} {len(rows):5d} rows -> {path}")


def parse_dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def split_name(name):
    match = NAME_RE.match(name)
    if match and any(ord(ch) > 127 for ch in match.group(2)):
        return match.group(1).strip(), match.group(2).strip()
    return name, ""


def synthetic_dob(key, reference_year, has_wca_id):
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    age = 6 + value % 55 if has_wca_id else 8 + value % 53
    birth_year = reference_year - age
    month = 1 + (value >> 8) % 12
    day = 1 + (value >> 16) % 28
    return f"{birth_year:04d}-{month:02d}-{day:02d}"


def make_email(name, person_no):
    ascii_name = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", ".", ascii_name).strip(".")
    if not slug:
        slug = "person"
    return f"{slug}.{person_no:04d}@example.com"


zf = ensure_export()

persons_export = {}
previous_export = defaultdict(list)
for row in export_rows(zf, "WCA_export_persons.tsv"):
    if row["sub_id"] == "1":
        persons_export[row["wca_id"]] = row
    else:
        previous_export[row["wca_id"]].append(row)

competition_start = {}
for row in export_rows(zf, "WCA_export_competitions.tsv"):
    if row["id"] in SHORTLIST:
        competition_start[row["id"]] = date(
            int(row["year"]), int(row["month"]), int(row["day"])
        )

country_rows = list(csv.DictReader(open(DATA / "countries.csv", encoding="utf-8")))
country_ids = {row["Country_ID"] for row in country_rows}
iso2_to_country = {row["ISO2"]: row["Country_ID"] for row in country_rows}

results = selected_results()
result_dates = defaultdict(list)
for row in results:
    result_dates[row["person_id"]].append(
        (competition_start[row["competition_id"]], row["person_country_id"])
    )

delegate_rows = delegates()
team_groups = teams()
competition_details = {cid: competition(cid) for cid in SHORTLIST}
upcoming_wcif = {cid: wcif(cid) for cid in UPCOMING}

uid_to_wca = {}


def note_user(uid, wca_id):
    if uid and wca_id:
        uid_to_wca.setdefault(uid, wca_id)


for row in delegate_rows:
    note_user(row.get("id"), row.get("wca_id"))
for group in team_groups:
    for role in group["_roles"]:
        note_user(role["user"].get("id"), role["user"].get("wca_id"))
for detail in competition_details.values():
    for organizer in detail.get("organizers", []):
        note_user(organizer.get("id"), organizer.get("wca_id"))
for data in upcoming_wcif.values():
    for person in data["persons"]:
        note_user(person.get("wcaUserId"), person.get("wcaId"))

union = set(result_dates)
union |= {row["wca_id"] for row in delegate_rows if row.get("wca_id")}
for group in team_groups:
    if group["_fid"] in EXCLUDED_TEAMS:
        continue
    for role in group["_roles"]:
        if role["user"].get("wca_id"):
            union.add(role["user"]["wca_id"])
for detail in competition_details.values():
    for organizer in detail.get("organizers", []):
        if organizer.get("wca_id"):
            union.add(organizer["wca_id"])
for data in upcoming_wcif.values():
    for person in data["persons"]:
        if person.get("wcaId"):
            union.add(person["wcaId"])

unattached = []
for wca_id in sorted(persons_export):
    if len(unattached) == 8:
        break
    if wca_id in union:
        continue
    if previous_export.get(wca_id):
        continue
    if persons_export[wca_id]["country_id"] not in country_ids:
        continue
    unattached.append(wca_id)
assert len(unattached) == 8
union |= set(unattached)

registry = {}


def ensure_wca(wca_id):
    if wca_id not in registry:
        source = persons_export[wca_id]
        registry[wca_id] = {
            "key": wca_id,
            "wca_id": wca_id,
            "user_id": None,
            "name": source["name"],
            "gender": source["gender"],
            "country_id": source["country_id"],
            "created_at": None,
            "sources": set(),
        }
    return registry[wca_id]


for wca_id in union:
    assert wca_id in persons_export, wca_id
    ensure_wca(wca_id)


def enrich(record, user_id, created_at, source):
    if user_id and not record["user_id"]:
        record["user_id"] = user_id
    if created_at:
        day = created_at[:10]
        if not record["created_at"] or day < record["created_at"]:
            record["created_at"] = day
    record["sources"].add(source)


for row in delegate_rows:
    wca_id = row.get("wca_id")
    if wca_id:
        enrich(ensure_wca(wca_id), row.get("id"), row.get("created_at"), "delegate")

no_id_team = []
for group in team_groups:
    if group["_fid"] in EXCLUDED_TEAMS:
        continue
    for role in group["_roles"]:
        user = role["user"]
        wca_id = user.get("wca_id")
        if wca_id:
            enrich(ensure_wca(wca_id), user.get("id"), user.get("created_at"), "team")
            continue
        key = uid_to_wca.get(user["id"], f"user:{user['id']}")
        if key in registry:
            enrich(registry[key], user["id"], user.get("created_at"), "team")
            continue
        registry[key] = {
            "key": key,
            "wca_id": None,
            "user_id": user["id"],
            "name": user["name"],
            "gender": user.get("gender"),
            "country_id": user["country"]["id"],
            "created_at": (user.get("created_at") or "")[:10] or None,
            "sources": {"team"},
        }
        no_id_team.append(key)


def is_person_organizer(organizer):
    name = organizer.get("name", "")
    lowered = name.lower()
    if "(" in name:
        return False
    if any(token in lowered for token in ORG_TOKENS):
        return False
    if organizer.get("gender") not in {"m", "f", "o"}:
        return False
    return bool(organizer.get("country"))


included_no_id_organizers = []
for detail in competition_details.values():
    for organizer in detail.get("organizers", []):
        wca_id = organizer.get("wca_id")
        if wca_id:
            enrich(
                ensure_wca(wca_id),
                organizer.get("id"),
                organizer.get("created_at"),
                "organizer",
            )
            continue
        if not is_person_organizer(organizer):
            continue
        included_no_id_organizers.append(organizer["name"])
        key = uid_to_wca.get(organizer["id"], f"user:{organizer['id']}")
        if key in registry:
            enrich(
                registry[key],
                organizer["id"],
                organizer.get("created_at"),
                "organizer",
            )
            continue
        registry[key] = {
            "key": key,
            "wca_id": None,
            "user_id": organizer["id"],
            "name": organizer["name"],
            "gender": organizer.get("gender"),
            "country_id": organizer["country"]["id"],
            "created_at": (organizer.get("created_at") or "")[:10] or None,
            "sources": {"organizer"},
        }

no_id_upcoming = []
for data in upcoming_wcif.values():
    for person in data["persons"]:
        wca_id = person.get("wcaId")
        if wca_id:
            enrich(ensure_wca(wca_id), person.get("wcaUserId"), None, "upcoming")
            continue
        if not person.get("registration"):
            continue
        key = uid_to_wca.get(person["wcaUserId"], f"user:{person['wcaUserId']}")
        if key in registry:
            continue
        registry[key] = {
            "key": key,
            "wca_id": None,
            "user_id": person["wcaUserId"],
            "name": person["name"],
            "gender": person.get("gender"),
            "country_id": iso2_to_country[person["countryIso2"]],
            "created_at": None,
            "sources": {"upcoming"},
        }
        no_id_upcoming.append(key)

for wca_id in unattached:
    registry[wca_id]["sources"].add("unattached")

for key, record in registry.items():
    assert record["name"], key
    assert record["gender"] in {"m", "f", "o"}, (key, record["gender"])
    assert record["country_id"] in country_ids, (key, record["country_id"])
    if record["wca_id"]:
        assert WCA_RE.match(record["wca_id"]), record["wca_id"]

wca_keys = sorted(key for key, record in registry.items() if record["wca_id"])
no_id_keys = sorted(
    (key for key, record in registry.items() if not record["wca_id"]),
    key=lambda key: (
        registry[key]["name"],
        registry[key]["country_id"],
        registry[key]["user_id"] or 0,
    ),
)
ordered_keys = wca_keys + no_id_keys
person_no = {key: index for index, key in enumerate(ordered_keys, start=1)}


def plan_registrations():
    plan = {}
    for cid in UPCOMING:
        detail = competition_details[cid]
        opens = parse_dt(detail["registration_open"])
        closes = parse_dt(detail["registration_close"])
        registrants = [
            person
            for person in upcoming_wcif[cid]["persons"]
            if person.get("registration")
        ]

        def key_of(person):
            if person.get("wcaId"):
                return person["wcaId"]
            return uid_to_wca.get(
                person.get("wcaUserId"), f"user:{person['wcaUserId']}"
            )

        registrants.sort(key=lambda person: person_no[key_of(person)])
        count = len(registrants)
        span = int((closes - opens).total_seconds())
        rows = []
        for index, person in enumerate(registrants, start=1):
            timestamp = opens + timedelta(seconds=span * index // (count + 1))
            rows.append(
                {
                    "person_no": person_no[key_of(person)],
                    "key": key_of(person),
                    "registrant_no": index,
                    "registered_at": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        assert all(
            rows[index]["registered_at"] < rows[index + 1]["registered_at"]
            for index in range(len(rows) - 1)
        )
        plan[cid] = rows
    (CACHE / "upcoming_registration_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    dates = defaultdict(list)
    for rows in plan.values():
        for row in rows:
            dates[row["key"]].append(row["registered_at"][:10])
    return plan, {key: min(values) for key, values in dates.items()}


registration_plan, registration_date = plan_registrations()

person_rows = []
since_sources = Counter()
email_seen = set()
local_name_scripts = Counter()

for key in ordered_keys:
    record = registry[key]
    romanized, local = split_name(record["name"])
    reference_year = int(record["wca_id"][:4]) if record["wca_id"] else 2026
    dob = synthetic_dob(key, reference_year, bool(record["wca_id"]))
    email = make_email(romanized, person_no[key])
    assert email not in email_seen
    email_seen.add(email)

    if record["wca_id"] and result_dates.get(record["wca_id"]):
        dates = result_dates[record["wca_id"]]
        current_dates = [day for day, country in dates if country == record["country_id"]]
        if current_dates:
            since = min(current_dates).isoformat()
            since_sources["current-country result"] += 1
        elif key in registration_date:
            since = registration_date[key]
            since_sources["registration date"] += 1
        else:
            since = min(day for day, country in dates).isoformat()
            since_sources["earliest result (other country)"] += 1
    elif key in registration_date:
        since = registration_date[key]
        since_sources["registration date"] += 1
    elif record["created_at"]:
        since = record["created_at"]
        since_sources["account created_at"] += 1
    else:
        since = ""
        since_sources["none"] += 1

    if local:
        if re.search(r"[\u4e00-\u9fff]", local):
            local_name_scripts["CJK"] += 1
        elif re.search(r"[\uac00-\ud7af]", local):
            local_name_scripts["Hangul"] += 1
        elif re.search(r"[\u0900-\u097f]", local):
            local_name_scripts["Devanagari"] += 1
        elif re.search(r"[\u0e00-\u0e7f]", local):
            local_name_scripts["Thai"] += 1
        elif re.search(r"[\u0400-\u04ff]", local):
            local_name_scripts["Cyrillic"] += 1
        else:
            local_name_scripts["other"] += 1

    person_rows.append(
        [
            person_no[key],
            record["wca_id"] or "",
            romanized,
            local,
            record["gender"],
            dob,
            email,
            record["country_id"],
            since,
        ]
    )

write_csv(
    "persons.csv",
    [
        "Person_No",
        "WCA_ID",
        "Romanized_Name",
        "Local_Name",
        "Gender",
        "Date_of_Birth",
        "Email",
        "Country_ID",
        "Since_Date",
    ],
    person_rows,
)

previous_rows = []
previous_sources = Counter()
pure_duplicates = []
for key in ordered_keys:
    record = registry[key]
    wca_id = record["wca_id"]
    if not wca_id:
        continue
    dates = result_dates.get(wca_id, [])
    for old in previous_export.get(wca_id, []):
        if old["name"] == record["name"] and old["country_id"] == record["country_id"]:
            pure_duplicates.append((wca_id, old["name"], old["country_id"]))
            continue
        old_dates = [day for day, country in dates if country == old["country_id"]]
        current_dates = [
            day for day, country in dates if country == record["country_id"]
        ]
        any_dates = [day for day, country in dates]
        if old_dates:
            valid_until = max(old_dates).isoformat()
            previous_sources["old-country result"] += 1
        elif current_dates:
            valid_until = (min(current_dates) - timedelta(days=1)).isoformat()
            previous_sources["day before first current-country result"] += 1
        elif any_dates:
            valid_until = (min(any_dates) - timedelta(days=1)).isoformat()
            previous_sources["day before first result"] += 1
        else:
            valid_until = f"{int(wca_id[:4]) - 1}-12-31"
            previous_sources["SYNTHETIC"] += 1
        assert old["country_id"] in country_ids, old["country_id"]
        previous_rows.append(
            [person_no[key], old["name"], old["country_id"], valid_until]
        )

previous_rows.sort(key=lambda row: (row[0], row[1], row[2]))
previous_keys = {(row[0], row[1], row[2], row[3]) for row in previous_rows}
assert len(previous_keys) == len(previous_rows)
write_csv(
    "previous_identities.csv",
    ["Person_No", "Old_Name", "Old_Country_ID", "Valid_Until"],
    previous_rows,
)

competitor_rows = [[person_no[key]] for key in wca_keys]
write_csv("competitors.csv", ["Person_No"], competitor_rows)

registry_out = {
    key: {
        "person_no": person_no[key],
        "wca_id": record["wca_id"],
        "user_id": record["user_id"],
        "name": record["name"],
        "country_id": record["country_id"],
    }
    for key, record in registry.items()
}
(CACHE / "person_registry.json").write_text(
    json.dumps(registry_out, ensure_ascii=False, indent=1), encoding="utf-8"
)

roles = delegate_roles()
best_role = {}
all_starts = defaultdict(list)
for role in roles:
    user = role["user"]
    wca_id = user.get("wca_id")
    if not wca_id:
        continue
    status = role["metadata"]["status"]
    if status not in DELEGATE_RANK:
        continue
    all_starts[wca_id].append(role["start_date"])
    current = best_role.get(wca_id)
    if (
        current is None
        or DELEGATE_RANK[status]
        > DELEGATE_RANK[current["metadata"]["status"]]
        or (
            DELEGATE_RANK[status]
            == DELEGATE_RANK[current["metadata"]["status"]]
            and (role["start_date"] or "9999-12-31")
            < (current["start_date"] or "9999-12-31")
        )
    ):
        best_role[wca_id] = role

assert len(best_role) == 766
senior_by_region = {
    role["group"]["name"]: wca_id
    for wca_id, role in best_role.items()
    if role["metadata"]["status"] == "senior_delegate"
}
regionals_by_group = defaultdict(list)
for wca_id, role in best_role.items():
    if role["metadata"]["status"] == "regional_delegate":
        regionals_by_group[role["group"]["id"]].append(wca_id)

delegate_rows_out = []
delegate_person_nos = {person_no[wca_id] for wca_id in best_role}
supervisor_counts = Counter()
missing_supervisor = []
for wca_id in sorted(best_role, key=lambda value: person_no[value]):
    role = best_role[wca_id]
    status = role["metadata"]["status"]
    senior_region = role["metadata"].get("senior_region")
    if status == "senior_delegate":
        supervisor = ""
    elif status == "regional_delegate":
        candidate = senior_by_region.get(senior_region)
        supervisor = person_no[candidate] if candidate and candidate != wca_id else ""
    else:
        candidates = sorted(
            regionals_by_group.get(role["group"]["id"], []),
            key=lambda value: person_no[value],
        )
        candidate = candidates[0] if candidates else senior_by_region.get(senior_region)
        if candidate == wca_id:
            candidate = senior_by_region.get(senior_region)
        supervisor = person_no[candidate] if candidate else ""
    if supervisor:
        supervisor_counts[supervisor] += 1
    elif status != "senior_delegate":
        missing_supervisor.append((wca_id, status, senior_region))
    appointed = min(all_starts[wca_id])
    delegate_rows_out.append(
        [
            person_no[wca_id],
            STATUS_MAP[status],
            role["user"].get("email") or "",
            appointed,
            supervisor,
            role["group"]["id"],
        ]
    )

assert len({row[2] for row in delegate_rows_out if row[2]}) == sum(
    1 for row in delegate_rows_out if row[2]
)
region_ids = {
    int(row["Region_ID"])
    for row in csv.DictReader(open(DATA / "regions.csv", encoding="utf-8"))
}
assert all(row[5] in region_ids for row in delegate_rows_out)
assert all(
    row[4] == "" or row[4] in delegate_person_nos for row in delegate_rows_out
)
write_csv(
    "delegate.csv",
    [
        "Person_No",
        "Delegate_Status",
        "WCA_Email",
        "Appointed_On",
        "Supervisor_Person_No",
        "Region_ID",
    ],
    delegate_rows_out,
)

membership = {}
team_ids = {
    row["Team_ID"]
    for row in csv.DictReader(open(DATA / "teams.csv", encoding="utf-8"))
}
for group in team_groups:
    if group["_fid"] in EXCLUDED_TEAMS:
        continue
    lead_user_id = (group.get("lead_user") or {}).get("id")
    for role in group["_roles"]:
        user = role["user"]
        key = user.get("wca_id") or uid_to_wca.get(user["id"]) or f"user:{user['id']}"
        role_name = (role.get("metadata") or {}).get("status")
        if role_name not in TEAM_RANK:
            role_name = "leader" if user["id"] == lead_user_id else "member"
        candidate = [
            person_no[key],
            group["_fid"],
            role_name,
            role["start_date"],
            role["end_date"] or "",
        ]
        existing = membership.get((person_no[key], group["_fid"]))
        if existing is None or TEAM_RANK[role_name] > TEAM_RANK[existing[2]]:
            membership[(person_no[key], group["_fid"])] = candidate

member_rows = sorted(membership.values(), key=lambda row: (row[1], row[0]))
person_no_set = set(person_no.values())
assert all(row[1] in team_ids for row in member_rows)
assert all(row[0] in person_no_set for row in member_rows)
write_csv(
    "member_of.csv",
    ["Person_No", "Team_ID", "Role", "Start_Date", "End_Date"],
    member_rows,
)

wca_id_year_recent = [key for key in wca_keys if int(key[:4]) >= 2025]
repeat_recent = 0
for key in wca_id_year_recent:
    days = sorted({day for day, country in result_dates.get(key, [])})
    if any(
        (days[index + 1] - days[index]).days <= 365
        for index in range(len(days) - 1)
    ):
        repeat_recent += 1

country_changed = 0
for key in wca_keys:
    dates = result_dates.get(key, [])
    if dates and any(country != registry[key]["country_id"] for day, country in dates):
        country_changed += 1

id_year_anomalies = []
for key in wca_keys:
    dates = result_dates.get(key, [])
    if dates:
        earliest_year = min(day.year for day, country in dates)
        if int(key[:4]) > earliest_year:
            id_year_anomalies.append((key, int(key[:4]), earliest_year))

print()
print(f"persons: {len(person_rows)} | WCA IDs: {len(wca_keys)} | no-ID: {len(no_id_keys)}")
print(f"  sources: results={len(result_dates)} delegates={len(delegate_rows)} teams={len(team_groups)} upcoming={sum(len(d['persons']) for d in upcoming_wcif.values())}")
print(f"  no-ID team={len(no_id_team)} organizers={len(included_no_id_organizers)} upcoming={len(no_id_upcoming)}")
print(f"  included no-ID organizers: {included_no_id_organizers}")
print(f"  unattached (demo-safe): {[(key, person_no[key]) for key in unattached]}")
print(f"  previous identities: {len(previous_rows)} | pure duplicates dropped: {len(pure_duplicates)}")
print(f"  previous date sources: {dict(previous_sources)}")
print(f"  Since_Date sources: {dict(since_sources)}")
print(f"  Local_Name scripts: {dict(local_name_scripts)}")
print(f"  WCA ID year >= 2025: {len(wca_id_year_recent)} | repeat within 12 months: {repeat_recent}")
print(f"  persons whose result country differs from current country: {country_changed}")
print(f"  WCA ID year later than earliest result year: {len(id_year_anomalies)} {id_year_anomalies[:5]}")
print(f"  delegates: {len(delegate_rows_out)} statuses={dict(Counter(row[1] for row in delegate_rows_out))}")
print(f"  delegate emails null: {sum(1 for row in delegate_rows_out if not row[2])}")
print(f"  delegate supervisors null: {sum(1 for row in delegate_rows_out if not row[4])} (incl. {len(missing_supervisor)} non-senior)")
print(f"  supervisee counts >=2: {sum(1 for value in supervisor_counts.values() if value >= 2)} | max={max(supervisor_counts.values())}")
print(f"  member_of: {len(member_rows)} roles={dict(Counter(row[2] for row in member_rows))} null ends={sum(1 for row in member_rows if not row[4])}")
