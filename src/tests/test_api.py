"""DEV ONLY - delete before submission (runs against the mock while USE_MOCK=1).

Status codes, the {detail, code} error shape and query validation at the edge.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app import app
from errors import NotFound

USING_MOCK = os.getenv("USE_MOCK") == "1"

# raise_server_exceptions=False so the catch-all 500 handler can be asserted.
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset():
    if USING_MOCK:
        import data

        data.mock._reset()
    yield


def test_every_documented_route_exists():
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {
        "/api/search",
        "/api/competitions",
        "/api/competitions/{competition_id}",
        "/api/competitions/{competition_id}/results",
        "/api/competitions/{competition_id}/registrations",
        "/api/competitions/{competition_id}/registrations/{registrant_no}",
        "/api/persons",
        "/api/persons/{person_ref}",
        "/api/persons/{person_ref}/results",
        "/api/persons/{person_ref}/country",
        "/api/rankings/{event_id}",
        "/api/countries",
        "/api/countries/{country_id}",
        "/api/countries/{country_id}/persons",
        "/api/events",
        "/api/stats/medals",
        "/api/stats/competitions-by-country",
        "/api/stats/records",
    } <= paths
    assert all(path.startswith("/api/") for path in paths)


@pytest.mark.parametrize(
    "url",
    [
        "/api/search?q=park",
        "/api/competitions",
        "/api/competitions?country_id=India&sort=name",
        "/api/competitions/WC2025",
        "/api/competitions/WC2025/results",
        "/api/competitions/DCHydCubeOpenNovember2026/registrations",
        "/api/persons",
        "/api/persons/2012PARK03",
        "/api/persons/2012PARK03/results",
        "/api/rankings/333",
        "/api/countries",
        "/api/countries/India",
        "/api/countries/India/persons",
        "/api/events",
        "/api/stats/medals",
        "/api/stats/competitions-by-country",
        "/api/stats/records",
    ],
)
def test_reads_return_200(url):
    response = client.get(url)
    assert response.status_code == 200, response.text


def test_list_envelope_shape():
    body = client.get("/api/competitions?page=1&page_size=3").json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert len(body["items"]) == 3
    assert body["page"] == 1 and body["page_size"] == 3


def test_error_shape_is_detail_and_code():
    response = client.get("/api/competitions/NoSuchCompetition")
    assert response.status_code == 404
    body = response.json()
    assert body == {
        "detail": "Competition not found.",
        "code": "competition_not_found",
    }


def test_not_found_for_each_resource():
    for url, code in [
        ("/api/competitions/Nope", "competition_not_found"),
        ("/api/persons/999999", "person_not_found"),
        ("/api/countries/Atlantis", "country_not_found"),
        ("/api/rankings/nope", "event_not_found"),
    ]:
        response = client.get(url)
        assert response.status_code == 404, url
        assert response.json()["code"] == code


def test_validation_errors_are_flattened_to_one_message():
    response = client.get("/api/search")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_input"
    assert "q" in body["detail"]


def test_query_validation_bounds():
    for url in (
        "/api/competitions?page=0",
        "/api/competitions?page_size=101",
        "/api/competitions?year=1990",
        "/api/competitions?status=maybe",
        "/api/competitions/WC2025/results?tab=nope",
        "/api/rankings/333?kind=median",
        "/api/search?q=",
        "/api/persons/1/results?page_size=0",
    ):
        assert client.get(url).status_code == 422, url


def test_data_layer_errors_are_not_500s():
    response = client.get("/api/competitions?sort=id;DROP+TABLE+persons")
    assert response.status_code == 422
    assert response.json()["code"] in ("invalid_sort", "invalid_input")


def test_create_returns_201_with_location():
    response = client.post(
        "/api/competitions/DCHydCubeOpenNovember2026/registrations",
        json={"person_no": 1, "events": ["333", "222"], "guests": 2},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["events"] == ["222", "333"]
    assert response.headers["location"].endswith(f"/{body['registrant_no']}")


def test_create_conflict_and_validation():
    duplicate = client.post(
        "/api/competitions/DCHydCubeOpenNovember2026/registrations",
        json={"person_no": 182, "events": ["333"]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "already_registered"

    for payload in (
        {"person_no": 1, "events": []},
        {"person_no": 0, "events": ["333"]},
        {"person_no": 1, "events": ["333"], "guests": 99},
        {"events": ["333"]},
    ):
        assert client.post(
            "/api/competitions/DCHydCubeOpenNovember2026/registrations", json=payload
        ).status_code == 422, payload


def test_patch_returns_registration_and_promotion():
    response = client.patch(
        "/api/competitions/DCHydCubeOpenNovember2026/registrations/1",
        json={"status": "cancelled"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["registration"]["status"] == "cancelled"
    assert body["promoted"] is not None


def test_delete_returns_204_then_404():
    url = "/api/competitions/CubeXWinterOpenBengaluru2026/registrations/58"
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 404


def test_delete_blocked_is_409_with_readable_message():
    response = client.delete("/api/competitions/BengalCubeOpen2025/registrations/1")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "registration_has_results"
    assert "results" in body["detail"].lower()


def test_update_person_country():
    response = client.put("/api/persons/125/country", json={"country_id": "India"})
    assert response.status_code == 200
    assert response.json()["country_id"] == "India"

    blocked = client.put("/api/persons/251/country", json={"country_id": "USA"})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "country_change_too_recent"


def test_confidential_fields_never_leave_the_api():
    for url in ("/api/persons/2012PARK03", "/api/persons?page_size=5"):
        text = client.get(url).text.lower()
        assert "date_of_birth" not in text
        assert "@example.com" not in text
        assert '"email"' not in text


def test_unhandled_error_returns_500_shape(monkeypatch):
    import data

    def explode(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(data, "list_countries", explode)
    response = client.get("/api/countries")
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Something went wrong on the server.",
        "code": "server_error",
    }


def test_static_frontend_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
