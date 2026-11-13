"""Raw queries against the real database.

Signatures are final (docs/feature_specs.md); bodies land in Phase 6 once the DB
teammate delivers the paradigm and schema. Every function raises NotFound / Conflict /
BadInput and returns plain dicts.
"""

from typing import Optional, Union

COMPETITION_SORTS = {
    "date_desc": "Start_Date DESC, Competition_ID ASC",
    "date_asc": "Start_Date ASC, Competition_ID ASC",
    "name": "Name ASC, Competition_ID ASC",
    "competitors": "registered_count DESC, Start_Date DESC",
}

PERSON_SORTS = {
    "name": "Romanized_Name ASC, Person_No ASC",
    "competitions": "competitions_count DESC, Romanized_Name ASC",
    "podiums": "podiums_count DESC, Romanized_Name ASC",
}

RESULT_SORTS = {
    "position": "Position ASC, Best ASC",
    "best": "Best ASC, Position ASC",
}


# --- reads -----------------------------------------------------------------


def search_all(q: str, limit: int = 5) -> dict:
    raise NotImplementedError


def list_competitions(
    q: Optional[str] = None,
    country_id: Optional[str] = None,
    continent_id: Optional[str] = None,
    year: Optional[int] = None,
    status: Optional[str] = None,
    event_id: Optional[str] = None,
    sort: str = "date_desc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    raise NotImplementedError


def get_competition(competition_id: str) -> dict:
    raise NotImplementedError


def list_competition_results(
    competition_id: str,
    event_id: Optional[str] = None,
    round_number: Optional[int] = None,
    tab: str = "podiums",
    sort: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    raise NotImplementedError


def list_persons(
    q: Optional[str] = None,
    country_id: Optional[str] = None,
    sort: str = "name",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    raise NotImplementedError


def get_person(person_ref: Union[int, str]) -> dict:
    """`person_ref` is a Person_No or a WCA ID; both resolve to one person."""
    raise NotImplementedError


def list_person_results(
    person_ref: Union[int, str],
    event_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    raise NotImplementedError


def list_rankings(
    event_id: str,
    kind: str = "single",
    country_id: Optional[str] = None,
    continent_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    raise NotImplementedError


def list_countries() -> list:
    raise NotImplementedError


def list_events(include_retired: bool = False) -> list:
    raise NotImplementedError


def list_registrations(
    competition_id: str,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    raise NotImplementedError


def get_registration(competition_id: str, registrant_no: int) -> dict:
    raise NotImplementedError


def stats_medals() -> list:
    raise NotImplementedError


def stats_competitions_by_country_year(
    year_from: Optional[int] = None, year_to: Optional[int] = None
) -> list:
    raise NotImplementedError


def stats_records() -> list:
    raise NotImplementedError


# --- writes ----------------------------------------------------------------


def create_registration(
    competition_id: str, person_no: int, event_ids: list, guests: int = 0
) -> dict:
    raise NotImplementedError


def set_registration_status(
    competition_id: str, registrant_no: int, status: str
) -> dict:
    raise NotImplementedError


def delete_registration(competition_id: str, registrant_no: int) -> None:
    raise NotImplementedError


def update_person_country(person_ref: Union[int, str], country_id: str) -> dict:
    raise NotImplementedError
