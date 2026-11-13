"""DEV ONLY - delete before submission.

In-memory implementation of the data-layer contract in docs/feature_specs.md.

This may filter, sort and page in Python: it is a UI-unblocking stand-in for
data/real.py, which does all of that in the database. Shapes must match real.py
exactly, because the same routers and the same tests run against both.
"""

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from data.real import COMPETITION_SORTS, PERSON_SORTS, RESULT_SORTS
from errors import BadInput, Conflict, NotFound

DATA = Path(__file__).resolve().parent.parent / "mock_data"
TODAY = date.today()


@lru_cache(maxsize=None)
def _load(table):
    return json.loads((DATA / f"{table}.json").read_text(encoding="utf-8"))


def _reset():
    """Drop every fixture and derived cache so one test cannot leak into the next."""
    _load.cache_clear()
    _reset_derived()


# --- helpers ---------------------------------------------------------------


def _as_date(value):
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _as_datetime(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value))


def _competition_status(comp):
    if comp["Cancelled_At"]:
        return "cancelled"
    start = _as_date(comp["Start_Date"])
    end = _as_date(comp["End_Date"])
    if end < TODAY:
        return "past"
    if start <= TODAY <= end:
        return "in_progress"
    return "upcoming"


def _matches(value, needle):
    if not needle:
        return True
    if not value:
        return False
    return needle.casefold() in str(value).casefold()


def _page(rows, page, page_size):
    if page < 1:
        raise BadInput("Page must be 1 or greater.", "invalid_page")
    if not 1 <= page_size <= 100:
        raise BadInput("Page size must be between 1 and 100.", "invalid_page_size")
    total = len(rows)
    start = (page - 1) * page_size
    return {"items": rows[start : start + page_size], "total": total, "page": page,
            "page_size": page_size}


def _sort_key(sorts, sort, default):
    if sort is None:
        sort = default
    if sort not in sorts:
        raise BadInput(f"Unknown sort '{sort}'.", "invalid_sort")
    return sort


# --- lookup tables ---------------------------------------------------------


@lru_cache(maxsize=None)
def _persons():
    return {p["Person_No"]: p for p in _load("persons")}


@lru_cache(maxsize=None)
def _countries():
    return {c["Country_ID"]: c for c in _load("countries")}


@lru_cache(maxsize=None)
def _continents():
    return {c["Continent_ID"]: c for c in _load("continents")}


@lru_cache(maxsize=None)
def _events():
    return {e["Event_ID"]: e for e in _load("events")}


@lru_cache(maxsize=None)
def _formats():
    return {f["Format_ID"]: f for f in _load("formats")}


@lru_cache(maxsize=None)
def _competitions():
    return {c["Competition_ID"]: c for c in _load("competitions")}


@lru_cache(maxsize=None)
def _championship_types():
    return {c["Competition_ID"]: c["Championship_Type"] for c in _load("championship_types")}


@lru_cache(maxsize=None)
def _delegate_status():
    return {d["Person_No"]: d["Delegate_Status"] for d in _load("delegate")}


def _resolve_person(person_ref):
    """Accept a Person_No or a WCA ID, like the real layer will."""
    persons = _persons()
    if isinstance(person_ref, int) or (isinstance(person_ref, str) and person_ref.isdigit()):
        person = persons.get(int(person_ref))
    else:
        person = next(
            (p for p in persons.values() if p["WCA_ID"] == str(person_ref).upper()), None
        )
    if person is None:
        raise NotFound("Person not found.", "person_not_found")
    return person


def _person_name(person_no):
    person = _persons().get(person_no)
    return person["Romanized_Name"] if person else None


def _country_name(country_id):
    country = _countries().get(country_id)
    return country["Name"] if country else country_id


def _result_key(result):
    return (result["Competition_ID"], result["Event_ID"], result["Round_Number"])


@lru_cache(maxsize=None)
def _final_rounds():
    finals = {}
    for r in _load("rounds"):
        key = (r["Competition_ID"], r["Event_ID"])
        finals[key] = max(finals.get(key, 0), r["Round_Number"])
    return finals


@lru_cache(maxsize=None)
def _attempts_by_result():
    out = {}
    for a in _load("attempts"):
        out.setdefault(a["Result_ID"], []).append(a)
    for values in out.values():
        values.sort(key=lambda a: a["Attempt_No"])
    return out


@lru_cache(maxsize=None)
def _selects_by_registration():
    out = {}
    for s in _load("selects"):
        out.setdefault((s["Competition_ID"], s["Registrant_No"]), []).append(s["Event_ID"])
    for values in out.values():
        values.sort()
    return out


@lru_cache(maxsize=None)
def _registered_counts():
    """Accepted registrations per competition, the number the UI shows as 'registered'."""
    out = {}
    for r in _load("registrations"):
        if r["Status"] == "accepted":
            out[r["Competition_ID"]] = out.get(r["Competition_ID"], 0) + 1
    return out


def _competition_row(comp):
    country = _countries().get(comp["Country_ID"])
    return {
        "competition_id": comp["Competition_ID"],
        "name": comp["Name"],
        "city": comp["City"],
        "country_id": comp["Country_ID"],
        "country_name": _country_name(comp["Country_ID"]),
        "continent_id": country["Continent_ID"] if country else None,
        "start_date": comp["Start_Date"],
        "end_date": comp["End_Date"],
        "status": _competition_status(comp),
        "competitor_limit": comp["Competitor_Limit"],
        "registered_count": _registered_counts().get(comp["Competition_ID"], 0),
        "main_event_id": comp["Main_Event_ID"],
        "championship_type": _championship_types().get(comp["Competition_ID"]),
    }


# --- reads: search ---------------------------------------------------------


def search_all(q, limit=5):
    needle = (q or "").strip()
    if not needle:
        raise BadInput("Enter something to search for.", "empty_query")
    if len(needle) > 60:
        raise BadInput("Search text is too long (60 characters max).", "query_too_long")

    competitions = [
        {
            "competition_id": c["Competition_ID"],
            "name": c["Name"],
            "city": c["City"],
            "country_id": c["Country_ID"],
            "start_date": c["Start_Date"],
        }
        for c in _load("competitions")
        if _matches(c["Name"], needle)
        or _matches(c["City"], needle)
        or _matches(c["Venue_Name"], needle)
    ]
    competitions.sort(key=lambda c: (-int(c["start_date"].replace("-", "")), c["competition_id"]))

    persons = []
    for p in _load("persons"):
        if _matches(p["Romanized_Name"], needle) or _matches(p["Local_Name"], needle) or (
            p["WCA_ID"] and p["WCA_ID"].upper().startswith(needle.upper())
        ):
            persons.append(
                {
                    "person_no": p["Person_No"],
                    "wca_id": p["WCA_ID"],
                    "name": p["Romanized_Name"],
                    "country_id": p["Country_ID"],
                }
            )
    persons.sort(key=lambda p: (p["name"].casefold(), p["person_no"]))

    return {"competitions": competitions[:limit], "persons": persons[:limit]}


# --- reads: competitions ---------------------------------------------------


def list_competitions(
    q=None,
    country_id=None,
    continent_id=None,
    year=None,
    status=None,
    event_id=None,
    sort="date_desc",
    page=1,
    page_size=20,
):
    sort = _sort_key(COMPETITION_SORTS, sort, "date_desc")
    countries = _countries()
    event_comps = None
    if event_id:
        event_comps = {r["Competition_ID"] for r in _load("rounds") if r["Event_ID"] == event_id}

    rows = []
    for comp in _load("competitions"):
        if country_id and comp["Country_ID"] != country_id:
            continue
        if continent_id:
            country = countries.get(comp["Country_ID"])
            if not country or country["Continent_ID"] != continent_id:
                continue
        if year and int(comp["Start_Date"][:4]) != int(year):
            continue
        if event_comps is not None and comp["Competition_ID"] not in event_comps:
            continue
        row = _competition_row(comp)
        if status and row["status"] != status:
            continue
        if q and not (
            _matches(comp["Name"], q)
            or _matches(comp["City"], q)
            or _matches(comp["Venue_Name"], q)
        ):
            continue
        rows.append(row)

    if sort == "name":
        rows.sort(key=lambda r: (r["name"].casefold(), r["competition_id"]))
    elif sort == "date_asc":
        rows.sort(key=lambda r: (r["start_date"], r["competition_id"]))
    elif sort == "competitors":
        rows.sort(key=lambda r: (-r["registered_count"], r["start_date"]), reverse=False)
    else:
        rows.sort(key=lambda r: r["start_date"], reverse=True)

    return _page(rows, page, page_size)


def get_competition(competition_id):
    comp = _competitions().get(competition_id)
    if comp is None:
        raise NotFound("Competition not found.", "competition_not_found")

    by_event = {}
    for r in _load("rounds"):
        if r["Competition_ID"] != competition_id:
            continue
        by_event.setdefault(r["Event_ID"], []).append(r)

    events = []
    for event_id, rounds in by_event.items():
        event = _events().get(event_id)
        rounds.sort(key=lambda r: r["Round_Number"])
        events.append(
            {
                "event_id": event_id,
                "event_name": event["Event_Name"] if event else event_id,
                "result_kind": event["Result_Kind"] if event else "time",
                "rounds": [
                    {
                        "round_number": r["Round_Number"],
                        "format_id": r["Format_ID"],
                        "format_name": _formats().get(r["Format_ID"], {}).get(
                            "Format_Name", r["Format_ID"]
                        ),
                        "per_attempt": r["Per_Attempt"],
                        "cutoff_attempts": r["Cutoff_Attempts"],
                        "cutoff_value": r["Cutoff_Value"],
                        "adv_type": r["Adv_Type"],
                        "adv_level": r["Adv_Level"],
                        "is_dual": bool(r["Is_Dual"]),
                        "is_head_to_head": bool(r["Is_Head_to_Head"]),
                        "last_day": r["Last_Day"],
                    }
                    for r in rounds
                ],
            }
        )
    events.sort(key=lambda e: _events().get(e["event_id"], {}).get("Display_Rank", 999))

    def people(pairs):
        out = []
        for pair in sorted(pairs, key=lambda p: _person_name(p["Person_No"]) or ""):
            person = _persons().get(pair["Person_No"])
            if person:
                out.append(
                    {
                        "person_no": person["Person_No"],
                        "name": person["Romanized_Name"],
                        "wca_id": person["WCA_ID"],
                    }
                )
        return out

    detail = _competition_row(comp)
    detail.update(
        {
            "short_name": comp["Short_Name"],
            "venue_name": comp["Venue_Name"],
            "street_address": comp["Street_Address"],
            "venue_details": comp["Venue_Details"],
            "latitude": comp["Latitude"],
            "longitude": comp["Longitude"],
            "website": comp["Website"],
            "opens_at": comp["Opens_At"],
            "closes_at": comp["Closes_At"],
            "amount": comp["Amount"],
            "currency_code": comp["Currency_Code"],
            "refund_policy_percent": comp["Refund_Policy_Percent"],
            "announced_at": comp["Announced_At"],
            "cancelled_at": comp["Cancelled_At"],
            "results_posted_at": comp["Results_Posted_At"],
            "events": events,
            "delegates": people(
                [d for d in _load("competition_delegates") if d["Competition_ID"] == competition_id]
            ),
            "organizers": people(
                [
                    o
                    for o in _load("competition_organizers")
                    if o["Competition_ID"] == competition_id
                ]
            ),
            "podiums": [
                {
                    "event_id": row["event_id"],
                    "event_name": _events().get(row["event_id"], {}).get(
                        "Event_Name", row["event_id"]
                    ),
                    "position": row["position"],
                    "person_no": row["person_no"],
                    "name": row["name"],
                    "wca_id": row["wca_id"],
                    "country_id": row["country_id"],
                    "best": row["best"],
                    "average": row["average"],
                    "single_record": row["single_record"],
                    "average_record": row["average_record"],
                }
                for row in _competition_results(competition_id, tab="podiums")
            ],
        }
    )
    return detail


def _competition_results(competition_id, event_id=None, round_number=None, tab="podiums"):
    """Internal: the result rows for one competition, already joined to person names."""
    if tab not in ("podiums", "all", "by_person"):
        raise BadInput(f"Unknown results tab '{tab}'.", "invalid_tab")

    finals = _final_rounds()
    attempts = _attempts_by_result()
    rows = []
    for r in _load("results"):
        if r["Competition_ID"] != competition_id:
            continue
        if event_id and r["Event_ID"] != event_id:
            continue
        if round_number is not None and r["Round_Number"] != int(round_number):
            continue
        if tab == "podiums":
            key = (r["Competition_ID"], r["Event_ID"])
            if r["Round_Number"] != finals.get(key) or r["Position"] not in (1, 2, 3):
                continue
        person = _persons().get(r["Person_No"])
        rows.append(
            {
                "result_id": r["Result_ID"],
                "event_id": r["Event_ID"],
                "round_number": r["Round_Number"],
                "position": r["Position"],
                "person_no": r["Person_No"],
                "name": person["Romanized_Name"] if person else None,
                "wca_id": person["WCA_ID"] if person else None,
                "country_id": r["Country_ID"],
                "best": r["Best"],
                "average": r["Average"],
                "single_record": r["Single_Record"],
                "average_record": r["Average_Record"],
                "solves": [a["Value"] for a in attempts.get(r["Result_ID"], [])],
            }
        )
    return rows


def list_competition_results(
    competition_id,
    event_id=None,
    round_number=None,
    tab="podiums",
    sort=None,
    page=1,
    page_size=20,
):
    if competition_id not in _competitions():
        raise NotFound("Competition not found.", "competition_not_found")
    rows = _competition_results(competition_id, event_id, round_number, tab)

    if tab == "by_person":
        if sort is not None:
            _sort_key(RESULT_SORTS, sort, "position")
        rows.sort(
            key=lambda r: (
                r["name"] or "",
                _events().get(r["event_id"], {}).get("Display_Rank", 999),
                r["round_number"],
            )
        )
        return _page(rows, page, page_size)

    sort = _sort_key(RESULT_SORTS, sort, "position")
    if sort == "best":
        rows.sort(key=lambda r: (r["best"], r["event_id"], r["position"] or 999))
    else:
        rows.sort(
            key=lambda r: (
                _events().get(r["event_id"], {}).get("Display_Rank", 999),
                r["round_number"],
                r["position"] if r["position"] is not None else 999,
            )
        )
    return _page(rows, page, page_size)


# --- reads: persons --------------------------------------------------------


@lru_cache(maxsize=None)
def _person_stats():
    """Competition count and podium count per person, computed once from results."""
    comps, podiums = {}, {}
    finals = _final_rounds()
    for r in _load("results"):
        comps.setdefault(r["Person_No"], set()).add(r["Competition_ID"])
        key = (r["Competition_ID"], r["Event_ID"])
        if r["Round_Number"] == finals.get(key) and r["Position"] in (1, 2, 3):
            podiums[r["Person_No"]] = podiums.get(r["Person_No"], 0) + 1
    return (
        {p: len(c) for p, c in comps.items()},
        podiums,
    )


def list_persons(q=None, country_id=None, sort="name", page=1, page_size=20):
    sort = _sort_key(PERSON_SORTS, sort, "name")
    comp_counts, podium_counts = _person_stats()

    rows = []
    for p in _load("persons"):
        if country_id and p["Country_ID"] != country_id:
            continue
        if q and not (_matches(p["Romanized_Name"], q) or _matches(p["Local_Name"], q)):
            continue
        rows.append(
            {
                "person_no": p["Person_No"],
                "wca_id": p["WCA_ID"],
                "name": p["Romanized_Name"],
                "country_id": p["Country_ID"],
                "country_name": _country_name(p["Country_ID"]),
                "competitions_count": comp_counts.get(p["Person_No"], 0),
                "podiums_count": podium_counts.get(p["Person_No"], 0),
            }
        )

    if sort == "competitions":
        rows.sort(key=lambda r: (-r["competitions_count"], r["name"].casefold()))
    elif sort == "podiums":
        rows.sort(key=lambda r: (-r["podiums_count"], r["name"].casefold()))
    else:
        rows.sort(key=lambda r: (r["name"].casefold(), r["person_no"]))
    return _page(rows, page, page_size)


def _personal_records(person_no):
    """Per-event best single and average, with world/continental/national ranks."""
    mine = {}
    for r in _load("results"):
        if r["Person_No"] != person_no or not r["Best"] or r["Best"] <= 0:
            continue
        entry = mine.setdefault(r["Event_ID"], {"best": None, "average": None})
        if entry["best"] is None or r["Best"] < entry["best"]:
            entry["best"] = r["Best"]
        if r["Average"] and r["Average"] > 0:
            if entry["average"] is None or r["Average"] < entry["average"]:
                entry["average"] = r["Average"]

    person = _persons()[person_no]
    country = _countries().get(person["Country_ID"])
    continent_id = country["Continent_ID"] if country else None

    global_best, global_avg = {}, {}
    for r in _load("results"):
        if not r["Best"] or r["Best"] <= 0:
            continue
        event = r["Event_ID"]
        if global_best.get(event) is None or r["Best"] < global_best[event]:
            global_best[event] = r["Best"]
        if r["Average"] and r["Average"] > 0:
            if global_avg.get(event) is None or r["Average"] < global_avg[event]:
                global_avg[event] = r["Average"]

    def count_better(event, value, key, scope=None):
        seen = set()
        target = key
        for r in _load("results"):
            candidate = r[target]
            if r["Event_ID"] != event or not candidate or candidate <= 0:
                continue
            if key == "Average" and (not r["Average"] or r["Average"] <= 0):
                continue
            if candidate >= value:
                continue
            if scope == "continent" and continent_id:
                rc = _countries().get(r["Country_ID"])
                if not rc or rc["Continent_ID"] != continent_id:
                    continue
            if scope == "country" and r["Country_ID"] != person["Country_ID"]:
                continue
            seen.add(r["Person_No"])
        return len(seen) + 1

    rows = []
    for event_id in sorted(
        mine, key=lambda e: _events().get(e, {}).get("Display_Rank", 999)
    ):
        event = _events().get(event_id, {})
        records = mine[event_id]
        rows.append(
            {
                "event_id": event_id,
                "event_name": event.get("Event_Name", event_id),
                "best": records["best"],
                "average": records["average"],
                "world_rank": (
                    count_better(event_id, records["best"], "Best")
                    if records["best"]
                    else None
                ),
                "continental_rank": (
                    count_better(event_id, records["best"], "Best", "continent")
                    if records["best"]
                    else None
                ),
                "national_rank": (
                    count_better(event_id, records["best"], "Best", "country")
                    if records["best"]
                    else None
                ),
            }
        )
    return rows


def get_person(person_ref):
    person = _resolve_person(person_ref)
    comp_counts, podium_counts = _person_stats()
    return {
        "person_no": person["Person_No"],
        "wca_id": person["WCA_ID"],
        "name": person["Romanized_Name"],
        "local_name": person["Local_Name"],
        "gender": person["Gender"],
        "country_id": person["Country_ID"],
        "country_name": _country_name(person["Country_ID"]),
        "since_date": person["Since_Date"],
        "delegate_status": _delegate_status().get(person["Person_No"]),
        "competitions_count": comp_counts.get(person["Person_No"], 0),
        "podiums_count": podium_counts.get(person["Person_No"], 0),
        "personal_records": _personal_records(person["Person_No"]),
    }


def list_person_results(person_ref, event_id=None, page=1, page_size=20):
    person = _resolve_person(person_ref)
    attempts = _attempts_by_result()
    rows = []
    for r in _load("results"):
        if r["Person_No"] != person["Person_No"]:
            continue
        if event_id and r["Event_ID"] != event_id:
            continue
        comp = _competitions().get(r["Competition_ID"], {})
        rows.append(
            {
                "result_id": r["Result_ID"],
                "competition_id": r["Competition_ID"],
                "competition_name": comp.get("Name"),
                "event_id": r["Event_ID"],
                "round_number": r["Round_Number"],
                "position": r["Position"],
                "best": r["Best"],
                "average": r["Average"],
                "single_record": r["Single_Record"],
                "average_record": r["Average_Record"],
                "country_id": r["Country_ID"],
                "solves": [a["Value"] for a in attempts.get(r["Result_ID"], [])],
            }
        )
    rows.sort(key=lambda r: (r["competition_name"] or "", r["event_id"], r["round_number"]))
    return _page(rows, page, page_size)


# --- reads: rankings -------------------------------------------------------


def list_rankings(
    event_id, kind="single", country_id=None, continent_id=None, page=1, page_size=100
):
    event = _events().get(event_id)
    if event is None:
        raise NotFound("Event not found.", "event_not_found")
    if event["Status"] != "official":
        raise BadInput("This event is retired.", "event_retired")
    if kind not in ("single", "average"):
        raise BadInput("Rankings type must be 'single' or 'average'.", "invalid_kind")

    field = "Best" if kind == "single" else "Average"
    best = {}
    for r in _load("results"):
        if r["Event_ID"] != event_id:
            continue
        value = r[field]
        if not value or value <= 0:
            continue
        current = best.get(r["Person_No"])
        if current is None or value < current[field]:
            best[r["Person_No"]] = r

    countries = _countries()

    def in_scope(row):
        if country_id and row["Country_ID"] != country_id:
            return False
        if continent_id:
            country = countries.get(row["Country_ID"])
            if not country or country["Continent_ID"] != continent_id:
                return False
        return True

    ranked = sorted(
        (r for r in best.values() if in_scope(r)),
        key=lambda r: (r[field], r["Person_No"]),
    )

    # Ranks are computed over the in-scope rows, the way a window function would.
    continent_of = {
        r["Person_No"]: (countries.get(r["Country_ID"]) or {}).get("Continent_ID")
        for r in ranked
    }

    rows = []
    previous = None
    rank = 0
    for position, r in enumerate(ranked, start=1):
        value = r[field]
        if previous is None or value != previous:
            rank = position
            previous = value
        person = _persons().get(r["Person_No"], {})
        comp = _competitions().get(r["Competition_ID"], {})
        continent = continent_of.get(r["Person_No"])

        continental = 1 + sum(
            1
            for other in ranked
            if other[field] < value and continent_of.get(other["Person_No"]) == continent
        )
        national = 1 + sum(
            1
            for other in ranked
            if other[field] < value and other["Country_ID"] == r["Country_ID"]
        )

        rows.append(
            {
                "rank": rank,
                "person_no": r["Person_No"],
                "name": person.get("Romanized_Name"),
                "wca_id": person.get("WCA_ID"),
                "country_id": r["Country_ID"],
                "country_name": _country_name(r["Country_ID"]),
                "best": r["Best"],
                "average": r["Average"],
                "competition_id": r["Competition_ID"],
                "competition_name": comp.get("Name"),
                "continental_rank": continental,
                "national_rank": national,
            }
        )
    return _page(rows, page, page_size)


def list_countries():
    return [
        {
            "country_id": c["Country_ID"],
            "iso2": c["ISO2"],
            "name": c["Name"],
            "continent_id": c["Continent_ID"],
            "continent_name": _continents().get(c["Continent_ID"], {}).get("Name", c["Continent_ID"]),
        }
        for c in sorted(_load("countries"), key=lambda c: c["Name"].casefold())
    ]


def get_country(country_id):
    for row in list_countries():
        if row["country_id"] == country_id:
            return row
    raise NotFound("Country not found.", "country_not_found")


def list_events(include_retired=False):
    rows = [
        {
            "event_id": e["Event_ID"],
            "event_name": e["Event_Name"],
            "result_kind": e["Result_Kind"],
            "status": e["Status"],
        }
        for e in _load("events")
        if include_retired or e["Status"] == "official"
    ]
    return sorted(rows, key=lambda e: _events()[e["event_id"]]["Display_Rank"])


# --- reads: registrations --------------------------------------------------


def _registration_row(reg):
    person = _persons().get(reg["Person_No"], {})
    return {
        "competition_id": reg["Competition_ID"],
        "registrant_no": reg["Registrant_No"],
        "person_no": reg["Person_No"],
        "name": person.get("Romanized_Name"),
        "wca_id": person.get("WCA_ID"),
        "status": reg["Status"],
        "registered_at": reg["Registered_At"],
        "guests": reg["Guests"],
        "guardian_consent": bool(reg["Guardian_Consent"]),
        "events": list(
            _selects_by_registration().get((reg["Competition_ID"], reg["Registrant_No"]), [])
        ),
    }


def list_registrations(competition_id, status=None, page=1, page_size=100):
    if competition_id not in _competitions():
        raise NotFound("Competition not found.", "competition_not_found")
    rows = [
        _registration_row(r)
        for r in _load("registrations")
        if r["Competition_ID"] == competition_id and (not status or r["Status"] == status)
    ]
    rows.sort(key=lambda r: r["registrant_no"])
    return _page(rows, page, page_size)


def get_registration(competition_id, registrant_no):
    for reg in _load("registrations"):
        if reg["Competition_ID"] == competition_id and reg["Registrant_No"] == int(registrant_no):
            return _registration_row(reg)
    raise NotFound("Registration not found.", "registration_not_found")


# --- reads: stats ----------------------------------------------------------


def stats_medals():
    finals = _final_rounds()
    medals = {}
    for r in _load("results"):
        if r["Position"] not in (1, 2, 3):
            continue
        key = (r["Competition_ID"], r["Event_ID"])
        if r["Round_Number"] != finals.get(key):
            continue
        entry = medals.setdefault(
            r["Country_ID"], {"gold": 0, "silver": 0, "bronze": 0}
        )
        entry[["", "gold", "silver", "bronze"][r["Position"]]] += 1

    rows = []
    for country_id, counts in medals.items():
        country = _countries().get(country_id)
        rows.append(
            {
                "country_id": country_id,
                "country_name": _country_name(country_id),
                "continent_id": country["Continent_ID"] if country else None,
                "gold": counts["gold"],
                "silver": counts["silver"],
                "bronze": counts["bronze"],
                "total": counts["gold"] + counts["silver"] + counts["bronze"],
            }
        )
    rows.sort(key=lambda r: (-r["gold"], -r["silver"], -r["bronze"], r["country_name"]))
    return rows


def stats_competitions_by_country_year(year_from=None, year_to=None):
    counts = {}
    for comp in _load("competitions"):
        year = int(comp["Start_Date"][:4])
        if year_from and year < int(year_from):
            continue
        if year_to and year > int(year_to):
            continue
        key = (comp["Country_ID"], year)
        counts[key] = counts.get(key, 0) + 1
    rows = [
        {
            "country_id": country_id,
            "country_name": _country_name(country_id),
            "year": year,
            "competition_count": n,
        }
        for (country_id, year), n in counts.items()
    ]
    rows.sort(key=lambda r: (-r["year"], -r["competition_count"], r["country_name"]))
    return rows


def stats_records():
    counts = {}
    for r in _load("results"):
        for field, kind in (("Single_Record", "single"), ("Average_Record", "average")):
            code = r[field]
            if not code:
                continue
            key = (r["Event_ID"], kind, code)
            counts[key] = counts.get(key, 0) + 1
    rows = [
        {
            "event_id": event_id,
            "event_name": _events().get(event_id, {}).get("Event_Name", event_id),
            "kind": kind,
            "record_code": code,
            "count": n,
        }
        for (event_id, kind, code), n in counts.items()
    ]
    rows.sort(
        key=lambda r: (
            _events().get(r["event_id"], {}).get("Display_Rank", 999),
            r["kind"],
            r["record_code"],
        )
    )
    return rows


# --- writes ----------------------------------------------------------------


def _competition_for_write(competition_id):
    comp = _competitions().get(competition_id)
    if comp is None:
        raise NotFound("Competition not found.", "competition_not_found")
    return comp


def _is_registration_open(comp):
    if _competition_status(comp) == "cancelled":
        return False
    opens = _as_datetime(comp["Opens_At"])
    closes = _as_datetime(comp["Closes_At"])
    now = datetime.now()
    if opens and now < opens:
        return False
    if closes and now > closes:
        return False
    return True


def _offered_events(competition_id):
    return {
        r["Event_ID"] for r in _load("rounds") if r["Competition_ID"] == competition_id
    }


def create_registration(competition_id, person_no, event_ids, guests=0):
    comp = _competition_for_write(competition_id)
    if not _is_registration_open(comp):
        raise Conflict(
            "Registration for this competition is closed.", "registration_closed"
        )

    person = _persons().get(int(person_no))
    if person is None:
        raise NotFound("Person not found.", "person_not_found")

    wanted = list(dict.fromkeys(event_ids))
    if not wanted:
        raise BadInput("Select at least one event.", "no_events")
    offered = _offered_events(competition_id)
    unknown = [e for e in wanted if e not in _events()]
    if unknown:
        raise BadInput(f"Unknown event '{unknown[0]}'.", "unknown_event")
    missing = [e for e in wanted if e not in offered]
    if missing:
        name = _events()[missing[0]]["Event_Name"]
        raise BadInput(
            f"This competition does not offer {name}.", "event_not_offered"
        )

    registrations = _load("registrations")
    if any(
        r["Competition_ID"] == competition_id and r["Person_No"] == person["Person_No"]
        for r in registrations
    ):
        raise Conflict("This person is already registered.", "already_registered")

    limit = comp["Competitor_Limit"]
    accepted = _registered_counts().get(competition_id, 0)
    status = "waiting_list" if limit is not None and accepted >= limit else "accepted"

    registrant_no = max(
        (r["Registrant_No"] for r in registrations if r["Competition_ID"] == competition_id),
        default=0,
    ) + 1
    reg = {
        "Competition_ID": competition_id,
        "Registrant_No": registrant_no,
        "Person_No": person["Person_No"],
        "Status": status,
        "Registered_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Guests": int(guests),
        "Guardian_Consent": False,
    }
    registrations.append(reg)
    for event_id in wanted:
        _load("selects").append(
            {
                "Competition_ID": competition_id,
                "Registrant_No": registrant_no,
                "Event_ID": event_id,
            }
        )
    _reset_derived()
    return _registration_row(reg)


def set_registration_status(competition_id, registrant_no, status):
    comp = _competition_for_write(competition_id)
    registrations = _load("registrations")
    target = next(
        (
            r
            for r in registrations
            if r["Competition_ID"] == competition_id
            and r["Registrant_No"] == int(registrant_no)
        ),
        None,
    )
    if target is None:
        raise NotFound("Registration not found.", "registration_not_found")
    if status not in ("accepted", "waiting_list", "pending", "cancelled", "rejected"):
        raise BadInput(f"Unknown status '{status}'.", "invalid_status")
    if target["Status"] == status:
        raise BadInput("This registration already has that status.", "status_unchanged")

    target["Status"] = status
    promoted = None

    limit = comp["Competitor_Limit"]
    accepted = sum(
        1
        for r in registrations
        if r["Competition_ID"] == competition_id and r["Status"] == "accepted"
    )
    if limit is None or accepted < limit:
        waiting = sorted(
            (
                r
                for r in registrations
                if r["Competition_ID"] == competition_id
                and r["Status"] == "waiting_list"
                and r["Registrant_No"] != target["Registrant_No"]
            ),
            key=lambda r: (r["Registered_At"], r["Registrant_No"]),
        )
        if waiting:
            earliest = waiting[0]
            earliest["Status"] = "accepted"
            promoted = {
                "registrant_no": earliest["Registrant_No"],
                "person_no": earliest["Person_No"],
                "name": _person_name(earliest["Person_No"]),
            }

    _reset_derived()
    return {"registration": _registration_row(target), "promoted": promoted}


def delete_registration(competition_id, registrant_no):
    if competition_id not in _competitions():
        raise NotFound("Competition not found.", "competition_not_found")
    registrations = _load("registrations")
    index = next(
        (
            i
            for i, r in enumerate(registrations)
            if r["Competition_ID"] == competition_id
            and r["Registrant_No"] == int(registrant_no)
        ),
        None,
    )
    if index is None:
        raise NotFound("Registration not found.", "registration_not_found")

    reg = registrations[index]
    has_results = any(
        r["Competition_ID"] == competition_id and r["Person_No"] == reg["Person_No"]
        for r in _load("results")
    )
    if has_results:
        raise Conflict(
            "Cannot delete this registration because the competitor already has "
            "results in this competition.",
            "registration_has_results",
        )

    registrations.pop(index)
    for table in ("selects",):
        rows = _load(table)
        rows[:] = [
            r
            for r in rows
            if not (
                r["Competition_ID"] == competition_id
                and r["Registrant_No"] == reg["Registrant_No"]
            )
        ]
    _reset_derived()
    return None


def update_person_country(person_ref, country_id):
    person = _resolve_person(person_ref)
    if country_id not in _countries():
        raise NotFound("Country not found.", "country_not_found")
    if person["Country_ID"] == country_id:
        raise BadInput(
            f"This person already represents {_country_name(country_id)}.",
            "same_country",
        )

    since = _as_date(person["Since_Date"])
    if since is not None:
        twelve_months_ago = TODAY.replace(year=TODAY.year - 1)
        if since > twelve_months_ago:
            raise Conflict(
                f"This person changed country on {since.isoformat()}; the 12-month "
                "rule still applies.",
                "country_change_too_recent",
            )

    person["Country_ID"] = country_id
    person["Since_Date"] = TODAY.isoformat()
    _reset_derived()
    return get_person(person["Person_No"])


def _reset_derived():
    for fn in (
        _persons,
        _countries,
        _continents,
        _events,
        _formats,
        _competitions,
        _championship_types,
        _delegate_status,
        _final_rounds,
        _attempts_by_result,
        _selects_by_registration,
        _registered_counts,
        _person_stats,
    ):
        fn.cache_clear()
