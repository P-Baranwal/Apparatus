#!/usr/bin/env python3

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from common import CACHE, DATA, SHORTLIST, competition, ensure_export, export_rows, wcif

CANCELLED = "MohaliCubeOpen2026"
TIMEZONES = {
    "IN": "Asia/Kolkata",
    "US": "America/Los_Angeles",
    "KR": "Asia/Seoul",
    "MY": "Asia/Kuala_Lumpur",
}
ROUND_ID_RE = re.compile(r"^(.+)-r(\d+)$")


def write_csv(name, header, rows):
    path = DATA / name
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{name:28s} {len(rows):5d} rows -> {path}")


def timestamp(value):
    if not value:
        return ""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def clean_venue(value):
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value).strip()


def schedule_activities(data):
    activities = []
    for venue in data["schedule"]["venues"]:
        for room in venue["rooms"]:
            for activity in room["activities"]:
                activities.append(activity)
                activities.extend(activity.get("childActivities", []))
    return activities


def local_last_day(activities, round_id, tz, start_date, end_date):
    hits = [
        activity
        for activity in activities
        if activity["activityCode"] == round_id
        or activity["activityCode"].startswith(round_id + "-")
    ]
    assert hits, round_id
    days = set()
    for activity in hits:
        for key in ("startTime", "endTime"):
            value = datetime.fromisoformat(
                activity[key].replace("Z", "+00:00")
            ).astimezone(tz)
            days.add(value.date())
    last = max(days)
    assert start_date <= last <= end_date, (round_id, last)
    return last.isoformat()


zf = ensure_export()
registry = json.loads((CACHE / "person_registry.json").read_text(encoding="utf-8"))
wid_to_pno = {
    row["wca_id"]: row["person_no"] for row in registry.values() if row["wca_id"]
}
uid_to_pno = {
    row["user_id"]: row["person_no"] for row in registry.values() if row["user_id"]
}

persons = {
    row["WCA_ID"]: row
    for row in csv.DictReader(open(DATA / "persons.csv", encoding="utf-8"))
    if row["WCA_ID"]
}
delegates = list(csv.DictReader(open(DATA / "delegate.csv", encoding="utf-8")))
delegate_pnos = {int(row["Person_No"]) for row in delegates}

events = list(csv.DictReader(open(DATA / "events.csv", encoding="utf-8")))
event_rank = {row["Event_ID"]: int(row["Display_Rank"]) for row in events}
event_status = {row["Event_ID"]: row["Status"] for row in events}

formats = {row["Format_ID"] for row in csv.DictReader(open(DATA / "formats.csv", encoding="utf-8"))}
allows = {}
for row in csv.DictReader(open(DATA / "allows.csv", encoding="utf-8")):
    allows[(row["Event_ID"], row["Format_ID"])] = {
        row["Usage_1"],
        row["Usage_2"],
    }

country_rows = list(csv.DictReader(open(DATA / "countries.csv", encoding="utf-8")))
iso2_to_country = {row["ISO2"]: row["Country_ID"] for row in country_rows}
country_ids = {row["Country_ID"] for row in country_rows}

competition_details = {cid: competition(cid) for cid in SHORTLIST}
competition_wcif = {cid: wcif(cid) for cid in SHORTLIST}

competition_rows = []
for cid in sorted(SHORTLIST, key=lambda value: (competition_details[value]["start_date"], value)):
    detail = competition_details[cid]
    start = date.fromisoformat(detail["start_date"])
    end = date.fromisoformat(detail["end_date"])
    opens = datetime.fromisoformat(detail["registration_open"].replace("Z", "+00:00"))
    closes = datetime.fromisoformat(detail["registration_close"].replace("Z", "+00:00"))
    assert start <= end
    assert opens < closes
    assert closes.date() <= start
    posted = detail.get("results_posted_at")
    if posted:
        posted_dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        assert posted_dt > datetime.combine(end, time.min, tzinfo=timezone.utc)
    assert -90 <= detail["latitude_degrees"] <= 90
    assert -180 <= detail["longitude_degrees"] <= 180
    assert detail["base_entry_fee_lowest_denomination"] >= 0
    assert len(detail["currency_code"]) == 3
    assert detail["refund_policy_percent"] is not None
    assert 0 <= detail["refund_policy_percent"] <= 100
    if detail.get("competitor_limit") is not None:
        assert detail["competitor_limit"] > 0
    main_event = detail.get("main_event_id") or ""
    if cid == CANCELLED:
        main_event = ""
    if main_event:
        assert main_event in {event["id"] for event in competition_wcif[cid]["events"]}
    competition_rows.append(
        [
            cid,
            detail["name"],
            detail.get("short_name") or "",
            clean_venue(detail.get("venue") or ""),
            detail.get("venue_address") or "",
            detail.get("venue_details") or "",
            detail.get("city") or "",
            detail["latitude_degrees"],
            detail["longitude_degrees"],
            detail["start_date"],
            detail["end_date"],
            timestamp(detail["registration_open"]),
            timestamp(detail["registration_close"]),
            int(detail["base_entry_fee_lowest_denomination"]),
            detail["currency_code"],
            detail.get("competitor_limit") if detail.get("competitor_limit") is not None else "",
            int(detail["refund_policy_percent"]),
            detail.get("website") or "",
            timestamp(detail.get("announced_at")),
            timestamp(detail.get("cancelled_at")),
            timestamp(detail.get("results_posted_at")),
            iso2_to_country[detail["country_iso2"]],
            main_event,
        ]
    )

write_csv(
    "competitions.csv",
    [
        "Competition_ID",
        "Name",
        "Short_Name",
        "Venue_Name",
        "Street_Address",
        "Venue_Details",
        "City",
        "Latitude",
        "Longitude",
        "Start_Date",
        "End_Date",
        "Opens_At",
        "Closes_At",
        "Amount",
        "Currency_Code",
        "Competitor_Limit",
        "Refund_Policy_Percent",
        "Website",
        "Announced_At",
        "Cancelled_At",
        "Results_Posted_At",
        "Country_ID",
        "Main_Event_ID",
    ],
    competition_rows,
)

championship_rows = []
for row in export_rows(zf, "WCA_export_championships.tsv"):
    if row["competition_id"] in SHORTLIST:
        championship_rows.append([row["competition_id"], row["championship_type"]])
championship_rows.sort()
assert len({tuple(row) for row in championship_rows}) == len(championship_rows)
write_csv(
    "championship_types.csv",
    ["Competition_ID", "Championship_Type"],
    championship_rows,
)

delegate_rows = set()
excluded_delegates = defaultdict(list)
for cid in SHORTLIST:
    if cid == CANCELLED:
        continue
    for person in competition_details[cid].get("delegates", []):
        wca_id = person.get("wca_id")
        person_no = wid_to_pno.get(wca_id)
        if person_no and person_no in delegate_pnos:
            delegate_rows.add((person_no, cid))
        else:
            reason = "not in PERSON" if not person_no else "not in delegate.csv"
            excluded_delegates[cid].append((wca_id, person.get("name"), reason))
delegate_rows = sorted(delegate_rows, key=lambda row: (row[1], int(row[0])))
for cid in SHORTLIST:
    if cid == CANCELLED:
        continue
    assert any(row[1] == cid for row in delegate_rows), cid
write_csv(
    "competition_delegates.csv",
    ["Person_No", "Competition_ID"],
    [[person_no, cid] for person_no, cid in delegate_rows],
)

organizer_rows = set()
for cid in SHORTLIST:
    if cid == CANCELLED:
        continue
    for person in competition_wcif[cid]["persons"]:
        if "organizer" not in (person.get("roles") or []):
            continue
        person_no = wid_to_pno.get(person.get("wcaId")) or uid_to_pno.get(
            person.get("wcaUserId")
        )
        if person_no:
            organizer_rows.add((person_no, cid))
organizer_rows = sorted(organizer_rows, key=lambda row: (row[1], int(row[0])))
write_csv(
    "competition_organizers.csv",
    ["Person_No", "Competition_ID"],
    [[person_no, cid] for person_no, cid in organizer_rows],
)

round_rows = []
cumulative_rows = []
round_numbers = defaultdict(dict)
dual_pairs = []
cutoff_count = 0
per_attempt_null = 0
adv_types = Counter()
h2h_rounds = 0

for cid in SHORTLIST:
    if cid == CANCELLED:
        continue
    detail = competition_details[cid]
    data = competition_wcif[cid]
    tz = ZoneInfo(TIMEZONES[detail["country_iso2"]])
    start_date = date.fromisoformat(detail["start_date"])
    end_date = date.fromisoformat(detail["end_date"])
    activities = schedule_activities(data)
    assert not detail.get("h2h_rounds")

    for event in data["events"]:
        event_id = event["id"]
        assert event_id in event_rank, event_id
        assert event_status[event_id] == "official"
        rounds = event["rounds"]
        assert 1 <= len(rounds) <= 4
        dual_pair = (
            len(rounds) >= 2
            and rounds[0]["format"] == rounds[1]["format"]
            and rounds[0].get("cutoff") == rounds[1].get("cutoff")
            and (rounds[0].get("timeLimit") or {}).get("centiseconds")
            == (rounds[1].get("timeLimit") or {}).get("centiseconds")
        )
        if dual_pair:
            dual_pairs.append((cid, event_id))

        for index, rnd in enumerate(rounds, start=1):
            assert rnd["id"] == f"{event_id}-r{index}", rnd["id"]
            round_numbers[(cid, event_id)][rnd["id"]] = index
            format_id = rnd["format"]
            assert format_id in formats, (cid, rnd["id"], format_id)
            assert (event_id, format_id) in allows, (cid, rnd["id"])
            usages = allows[(event_id, format_id)]

            time_limit = rnd.get("timeLimit")
            per_attempt = time_limit["centiseconds"] if time_limit else ""
            if not time_limit:
                per_attempt_null += 1

            cutoff = rnd.get("cutoff")
            if cutoff:
                cutoff_count += 1
                cutoff_attempts = cutoff["numberOfAttempts"]
                cutoff_value = cutoff["attemptResult"]
                assert cutoff_attempts in {1, 2}
                cutoff_format = str(cutoff_attempts)
                assert (event_id, cutoff_format) in allows, (
                    cid,
                    rnd["id"],
                    cutoff_format,
                )
                assert "cutoff_phase" in allows[(event_id, cutoff_format)]
                assert "full_round" in usages
            else:
                cutoff_attempts = ""
                cutoff_value = ""
                assert "full_round" in usages, (cid, rnd["id"])

            advancement = rnd.get("advancementCondition")
            if index < len(rounds):
                assert advancement is not None, (cid, rnd["id"])
                adv_type = advancement["type"]
                adv_level = advancement["level"]
                assert adv_type in {"ranking", "percent", "attempt_result"}
                adv_types[adv_type] += 1
            else:
                assert advancement is None, (cid, rnd["id"])
                adv_type = ""
                adv_level = ""

            is_dual = 1 if dual_pair and index <= 2 else 0
            is_h2h = 1 if rnd["format"] == "h" else 0
            assert is_h2h == 0
            h2h_rounds += is_h2h

            last_day = local_last_day(
                activities, rnd["id"], tz, start_date, end_date
            )
            round_rows.append(
                [
                    cid,
                    event_id,
                    index,
                    format_id,
                    per_attempt,
                    cutoff_attempts,
                    cutoff_value,
                    adv_type,
                    adv_level,
                    is_dual,
                    is_h2h,
                    last_day,
                ]
            )

            if time_limit and time_limit.get("cumulativeRoundIds"):
                for scope_id in time_limit["cumulativeRoundIds"]:
                    match = ROUND_ID_RE.match(scope_id)
                    assert match, scope_id
                    scope_event, scope_round = match.group(1), int(match.group(2))
                    assert scope_id in round_numbers[(cid, scope_event)], scope_id
                    cumulative_rows.append(
                        [cid, event_id, index, scope_event, scope_round]
                    )

round_rows.sort(key=lambda row: (row[0], event_rank[row[1]], row[2]))
assert len({(row[0], row[1], row[2]) for row in round_rows}) == len(round_rows)
write_csv(
    "rounds.csv",
    [
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Format_ID",
        "Per_Attempt",
        "Cutoff_Attempts",
        "Cutoff_Value",
        "Adv_Type",
        "Adv_Level",
        "Is_Dual",
        "Is_Head_to_Head",
        "Last_Day",
    ],
    round_rows,
)

cumulative_rows.sort()
assert len({tuple(row) for row in cumulative_rows}) == len(cumulative_rows)
write_csv(
    "cumulative_scope.csv",
    [
        "Competition_ID",
        "Event_ID",
        "Round_Number",
        "Scope_Event_ID",
        "Scope_Round_Number",
    ],
    cumulative_rows,
)

organizer_by_comp = Counter(row[1] for row in organizer_rows)
no_person_organizers = [
    cid
    for cid in SHORTLIST
    if cid != CANCELLED and organizer_by_comp[cid] == 0
]
rounds_by_comp = Counter(row[0] for row in round_rows)
delegates_by_comp = Counter(cid for _, cid in delegate_rows)

print()
print(f"competitions: {len(competition_rows)} | championship types: {len(championship_rows)}")
print(f"competition_delegates: {len(delegate_rows)} | competition_organizers: {len(organizer_rows)}")
print(f"rounds: {len(round_rows)} | cumulative scope: {len(cumulative_rows)}")
print(f"cutoff rounds: {cutoff_count} | Per_Attempt NULL: {per_attempt_null}")
print(f"adv types: {dict(adv_types)} | dual pairs: {len(dual_pairs)} | dual rounds: {sum(1 for row in round_rows if row[9] == 1)}")
print(f"H2H rounds: {h2h_rounds}")
print(f"rounds per comp: {dict(rounds_by_comp)}")
print(f"delegates per comp: {dict(delegates_by_comp)}")
print(f"organizers per comp: {dict(organizer_by_comp)}")
print(f"R4 competitions with NO person organizer: {no_person_organizers}")
print(f"excluded competition delegates: {dict(excluded_delegates)}")
print(f"last-day range: {min(row[11] for row in round_rows)} .. {max(row[11] for row in round_rows)}")
