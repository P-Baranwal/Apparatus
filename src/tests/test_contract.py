"""DEV ONLY - delete before submission.

Runs the data-layer contract against whichever implementation USE_MOCK selects.
Against the real layer, set USE_MOCK unset and drop the `reset` fixture.
"""

import os

import pytest

import data
from errors import BadInput, Conflict, NotFound

USING_MOCK = os.getenv("USE_MOCK") == "1"


@pytest.fixture(autouse=True)
def reset():
    """Isolate every test: the mock mutates fixtures in place."""
    if USING_MOCK:
        data.mock._reset()
    yield


def test_search_groups_competitions_and_persons():
    result = data.search_all("park")
    assert set(result) == {"competitions", "persons"}
    assert any("Park" in p["name"] for p in result["persons"])


def test_search_by_wca_id_prefix():
    persons = data.search_all("2012PARK")["persons"]
    assert [p["wca_id"] for p in persons] == ["2012PARK03"]


def test_search_rejects_empty_query():
    with pytest.raises(BadInput):
        data.search_all("   ")


def test_search_respects_limit():
    result = data.search_all("a", limit=3)
    assert len(result["persons"]) <= 3
    assert len(result["competitions"]) <= 3


def test_search_does_not_treat_like_wildcards_as_patterns():
    assert data.search_all("%")["persons"] == []


def test_list_competitions_shape_and_paging():
    first = data.list_competitions(page=1, page_size=5)
    assert set(first) == {"items", "total", "page", "page_size"}
    assert len(first["items"]) == 5
    assert first["total"] == 15

    second = data.list_competitions(page=2, page_size=5)
    ids = {c["competition_id"] for c in first["items"]}
    assert ids.isdisjoint({c["competition_id"] for c in second["items"]})


def test_list_competitions_filters():
    upcoming = data.list_competitions(status="upcoming")["items"]
    assert upcoming and all(c["status"] == "upcoming" for c in upcoming)

    india = data.list_competitions(country_id="India")["items"]
    assert india and all(c["country_id"] == "India" for c in india)

    asia = data.list_competitions(continent_id="_Asia")["items"]
    assert asia and all(c["continent_id"] == "_Asia" for c in asia)

    by_event = data.list_competitions(event_id="333mbf")["items"]
    assert all(
        "333mbf" in {r["event_id"] for r in data.get_competition(c["competition_id"])["events"]}
        for c in by_event
    )


def test_list_competitions_rejects_unknown_sort():
    with pytest.raises(BadInput):
        data.list_competitions(sort="name; DROP TABLE persons")


def test_list_competitions_paging_bounds():
    with pytest.raises(BadInput):
        data.list_competitions(page=0)
    with pytest.raises(BadInput):
        data.list_competitions(page_size=101)


def test_competition_detail_has_related_data():
    detail = data.get_competition("WC2025")
    assert detail["competition_id"] == "WC2025"
    assert detail["events"], "a championship must list its events"
    assert detail["delegates"] and detail["organizers"]
    assert detail["podiums"]
    assert all(1 <= p["position"] <= 3 for p in detail["podiums"])


def test_competition_detail_never_exposes_confidential_fields():
    for competition_id in ("WC2025", "BengalCubeOpen2025"):
        blob = str(data.get_competition(competition_id)).lower()
        assert "date_of_birth" not in blob and "email" not in blob


def test_missing_competition_raises_not_found():
    with pytest.raises(NotFound):
        data.get_competition("NoSuchCompetition")
    with pytest.raises(NotFound):
        data.list_competition_results("NoSuchCompetition")
    with pytest.raises(NotFound):
        data.list_registrations("NoSuchCompetition")


def test_competition_results_tabs():
    podiums = data.list_competition_results("BengalCubeOpen2025", tab="podiums")
    assert podiums["items"] and all(1 <= r["position"] <= 3 for r in podiums["items"])

    everything = data.list_competition_results("BengalCubeOpen2025", tab="all", page_size=100)
    assert everything["total"] > podiums["total"]

    by_person = data.list_competition_results("BengalCubeOpen2025", tab="by_person", page_size=100)
    names = [r["name"] for r in by_person["items"]]
    assert names == sorted(names, key=lambda n: (n or "").casefold())


def test_competition_result_attempts_are_ordered():
    rows = data.list_competition_results("BengalCubeOpen2025", tab="all", page_size=100)["items"]
    with_attempts = [r for r in rows if r["solves"]]
    assert with_attempts, "3x3x3 rounds must carry attempts"
    assert all(len(r["solves"]) <= 5 and r["solves"] for r in with_attempts)


def test_competition_results_rejects_unknown_tab():
    with pytest.raises(BadInput):
        data.list_competition_results("BengalCubeOpen2025", tab="nonsense")


def test_persons_list_shape_and_sorting():
    by_name = data.list_persons(page_size=10)["items"]
    assert [p["name"].casefold() for p in by_name] == sorted(
        p["name"].casefold() for p in by_name
    )

    by_podiums = data.list_persons(sort="podiums", page_size=10)["items"]
    counts = [p["podiums_count"] for p in by_podiums]
    assert counts == sorted(counts, reverse=True)


def test_persons_filter_by_country_and_query():
    indians = data.list_persons(country_id="India", page_size=100)["items"]
    assert indians and all(p["country_id"] == "India" for p in indians)

    matches = data.list_persons(q="sharma", page_size=100)["items"]
    assert matches and all("sharma" in p["name"].casefold() for p in matches)


def test_person_resolves_by_number_and_wca_id():
    by_wca = data.get_person("2012PARK03")
    by_number = data.get_person(by_wca["person_no"])
    assert by_wca == by_number
    assert by_wca["name"] == "Max Park"


def test_person_detail_never_exposes_confidential_fields():
    person = data.get_person("2012PARK03")
    assert "date_of_birth" not in person
    assert "email" not in person
    assert "email" not in str(person).lower()


def test_person_personal_records_have_ranks():
    records = data.get_person("2012PARK03")["personal_records"]
    assert records
    for record in records:
        assert set(record) == {
            "event_id", "event_name", "best", "average",
            "world_rank", "continental_rank", "national_rank",
        }
        if record["best"]:
            assert record["world_rank"] >= 1
            assert record["national_rank"] >= 1


def test_missing_person_raises_not_found():
    with pytest.raises(NotFound):
        data.get_person(999999)
    with pytest.raises(NotFound):
        data.get_person("9999ZZZZ99")


def test_person_results_for_newcomer_is_empty_not_an_error():
    result = data.list_person_results(1)
    assert result["items"] == [] and result["total"] == 0


def test_rankings_order_and_ties():
    rows = data.list_rankings("333", kind="single", page_size=100)["items"]
    values = [r["best"] for r in rows]
    assert values == sorted(values)
    assert rows[0]["rank"] == 1
    for previous, current in zip(rows, rows[1:]):
        assert current["rank"] >= previous["rank"]
        if current["best"] == previous["best"]:
            assert current["rank"] == previous["rank"]


def test_rankings_filter_by_country():
    rows = data.list_rankings("333", country_id="India", page_size=100)["items"]
    assert rows and all(r["country_id"] == "India" for r in rows)
    assert min(r["national_rank"] for r in rows) == 1


def test_rankings_reject_retired_event_and_bad_kind():
    with pytest.raises(BadInput):
        data.list_rankings("magic")
    with pytest.raises(BadInput):
        data.list_rankings("333", kind="median")
    with pytest.raises(NotFound):
        data.list_rankings("nope")


def test_countries_and_events():
    countries = data.list_countries()
    assert len(countries) == 108
    assert data.get_country("India")["iso2"] == "IN"
    with pytest.raises(NotFound):
        data.get_country("Atlantis")

    official = data.list_events()
    assert official and all(e["status"] == "official" for e in official)
    assert len(data.list_events(include_retired=True)) > len(official)


def test_registrations_list_and_filter():
    rows = data.list_registrations("DCHydCubeOpenNovember2026", page_size=100)["items"]
    assert rows and all(r["competition_id"] == "DCHydCubeOpenNovember2026" for r in rows)
    waiting = data.list_registrations(
        "DCHydCubeOpenNovember2026", status="waiting_list"
    )["items"]
    assert waiting and all(r["status"] == "waiting_list" for r in waiting)
    assert all(r["events"] for r in waiting)


def test_stats_shapes():
    medals = data.stats_medals()
    assert medals and {"gold", "silver", "bronze", "total"} <= set(medals[0])
    assert all(m["total"] == m["gold"] + m["silver"] + m["bronze"] for m in medals)
    totals = [m["gold"] for m in medals]
    assert totals == sorted(totals, reverse=True)

    by_year = data.stats_competitions_by_country_year(year_from=2025)
    assert by_year and all(row["year"] >= 2025 for row in by_year)

    records = data.stats_records()
    assert records and all(r["count"] >= 1 for r in records)
    assert {r["record_code"] for r in records} <= {"WR", "CR", "NR", "AsR", "ER", "NAR",
                                                   "SAR", "AfR", "OcR"}


def test_create_registration_and_selects():
    before = data.list_registrations("DCHydCubeOpenNovember2026", page_size=100)["total"]
    created = data.create_registration(
        "DCHydCubeOpenNovember2026", 1, ["333", "222"], guests=1
    )
    assert created["status"] in ("accepted", "waiting_list")
    assert created["events"] == ["222", "333"]
    assert created["guests"] == 1

    after = data.list_registrations("DCHydCubeOpenNovember2026", page_size=100)["total"]
    assert after == before + 1
    assert data.get_registration("DCHydCubeOpenNovember2026", created["registrant_no"])


def test_create_registration_duplicate_is_conflict():
    with pytest.raises(Conflict):
        data.create_registration("DCHydCubeOpenNovember2026", 182, ["333"])


def test_create_registration_validations():
    with pytest.raises(Conflict):
        data.create_registration("BengalCubeOpen2025", 1, ["333"])
    with pytest.raises(BadInput):
        data.create_registration("DCHydCubeOpenNovember2026", 1, [])
    with pytest.raises(BadInput):
        data.create_registration("IndianPBQChampionship2026", 1, ["333"])
    with pytest.raises(NotFound):
        data.create_registration("DCHydCubeOpenNovember2026", 999999, ["333"])


def test_status_change_promotes_earliest_waiting_registration():
    waiting = data.list_registrations(
        "DCHydCubeOpenNovember2026", status="waiting_list", page_size=100
    )["items"]
    earliest = min(waiting, key=lambda r: (r["registered_at"], r["registrant_no"]))

    result = data.set_registration_status(
        "DCHydCubeOpenNovember2026", 1, "cancelled"
    )
    assert result["registration"]["status"] == "cancelled"
    assert result["promoted"] is not None
    assert result["promoted"]["registrant_no"] == earliest["registrant_no"]

    promoted = data.get_registration(
        "DCHydCubeOpenNovember2026", earliest["registrant_no"]
    )
    assert promoted["status"] == "accepted"


def test_status_change_to_waiting_list_does_not_promote_itself():
    result = data.set_registration_status(
        "DCHydCubeOpenNovember2026", 1, "waiting_list"
    )
    assert result["registration"]["status"] == "waiting_list"
    assert result["promoted"] is not None
    assert result["promoted"]["registrant_no"] != 1


def test_status_change_without_waiting_list_promotes_nobody():
    result = data.set_registration_status("BengalCubeOpen2025", 1, "cancelled")
    assert result["promoted"] is None


def test_status_change_validations():
    with pytest.raises(BadInput):
        data.set_registration_status("DCHydCubeOpenNovember2026", 1, "accepted")
    with pytest.raises(BadInput):
        data.set_registration_status("DCHydCubeOpenNovember2026", 1, "sideways")
    with pytest.raises(NotFound):
        data.set_registration_status("DCHydCubeOpenNovember2026", 9999, "cancelled")


def test_delete_registration_removes_selects():
    before = data.list_registrations("CubeXWinterOpenBengaluru2026", page_size=100)["total"]
    data.delete_registration("CubeXWinterOpenBengaluru2026", 58)
    after = data.list_registrations("CubeXWinterOpenBengaluru2026", page_size=100)["total"]
    assert after == before - 1
    with pytest.raises(NotFound):
        data.get_registration("CubeXWinterOpenBengaluru2026", 58)
    with pytest.raises(NotFound):
        data.delete_registration("CubeXWinterOpenBengaluru2026", 58)


def test_delete_registration_blocked_by_results():
    with pytest.raises(Conflict) as excinfo:
        data.delete_registration("BengalCubeOpen2025", 1)
    assert "results" in str(excinfo.value.detail).lower()


def test_update_person_country_sets_date():
    before = data.get_person(125)
    assert before["country_id"] != "India"
    updated = data.update_person_country(125, "India")
    assert updated["country_id"] == "India"
    assert updated["since_date"] is not None
    assert updated["since_date"] > before["since_date"]


def test_update_person_country_validations():
    current = data.get_person(151)["country_id"]
    with pytest.raises(BadInput):
        data.update_person_country(151, current)
    with pytest.raises(NotFound):
        data.update_person_country(151, "Atlantis")
    with pytest.raises(Conflict):
        data.update_person_country(251, "USA")
