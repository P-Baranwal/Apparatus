from typing import Optional

from fastapi import APIRouter, Query, Response, status

import data
import schemas

router = APIRouter(tags=["competitions"])


@router.get("/competitions", response_model=schemas.Page[schemas.CompetitionListItem])
def list_competitions(
    q: Optional[str] = Query(default=None, max_length=60),
    country_id: Optional[str] = Query(default=None, max_length=60),
    continent_id: Optional[str] = Query(default=None, max_length=20),
    year: Optional[int] = Query(default=None, ge=2003, le=2100),
    status: Optional[schemas.CompetitionStatus] = None,
    event_id: Optional[str] = Query(default=None, max_length=10),
    sort: str = Query(default="date_desc", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return data.list_competitions(
        q=q,
        country_id=country_id,
        continent_id=continent_id,
        year=year,
        status=status,
        event_id=event_id,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/competitions/{competition_id}", response_model=schemas.CompetitionDetail)
def get_competition(competition_id: str):
    return data.get_competition(competition_id)


@router.get(
    "/competitions/{competition_id}/results",
    response_model=schemas.Page[schemas.CompetitionResultItem],
)
def list_competition_results(
    competition_id: str,
    tab: str = Query(default="podiums", pattern="^(podiums|all|by_person)$"),
    event_id: Optional[str] = Query(default=None, max_length=10),
    round_number: Optional[int] = Query(default=None, ge=1, le=10),
    sort: Optional[str] = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return data.list_competition_results(
        competition_id,
        event_id=event_id,
        round_number=round_number,
        tab=tab,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/competitions/{competition_id}/registrations",
    response_model=schemas.Page[schemas.RegistrationItem],
)
def list_registrations(
    competition_id: str,
    status: Optional[schemas.RegistrationStatus] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
):
    return data.list_registrations(competition_id, status=status, page=page,
                                   page_size=page_size)


@router.get(
    "/competitions/{competition_id}/registrations/{registrant_no}",
    response_model=schemas.RegistrationItem,
)
def get_registration(competition_id: str, registrant_no: int):
    return data.get_registration(competition_id, registrant_no)


@router.post(
    "/competitions/{competition_id}/registrations",
    response_model=schemas.RegistrationItem,
    status_code=status.HTTP_201_CREATED,
)
def create_registration(
    competition_id: str, payload: schemas.RegistrationCreate, response: Response
):
    created = data.create_registration(
        competition_id, payload.person_no, payload.events, payload.guests
    )
    response.headers["Location"] = (
        f"/api/competitions/{competition_id}/registrations/"
        f"{created['registrant_no']}"
    )
    return created


@router.patch(
    "/competitions/{competition_id}/registrations/{registrant_no}",
    response_model=schemas.RegistrationChange,
)
def set_registration_status(
    competition_id: str, registrant_no: int, payload: schemas.RegistrationStatusUpdate
):
    return data.set_registration_status(
        competition_id, registrant_no, payload.status
    )


@router.delete(
    "/competitions/{competition_id}/registrations/{registrant_no}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_registration(competition_id: str, registrant_no: int):
    data.delete_registration(competition_id, registrant_no)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
