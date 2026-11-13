from typing import Optional

from fastapi import APIRouter, Query

import data
import schemas

router = APIRouter(tags=["persons"])


@router.get("/persons", response_model=schemas.Page[schemas.PersonListItem])
def list_persons(
    q: Optional[str] = Query(default=None, max_length=60),
    country_id: Optional[str] = Query(default=None, max_length=60),
    sort: str = Query(default="name", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return data.list_persons(
        q=q, country_id=country_id, sort=sort, page=page, page_size=page_size
    )


@router.get("/persons/{person_ref}", response_model=schemas.PersonDetail)
def get_person(person_ref: str):
    return data.get_person(person_ref)


@router.get(
    "/persons/{person_ref}/results",
    response_model=schemas.Page[schemas.PersonResultItem],
)
def list_person_results(
    person_ref: str,
    event_id: Optional[str] = Query(default=None, max_length=10),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return data.list_person_results(
        person_ref, event_id=event_id, page=page, page_size=page_size
    )


@router.put("/persons/{person_ref}/country", response_model=schemas.PersonDetail)
def update_person_country(person_ref: str, payload: schemas.PersonCountryUpdate):
    return data.update_person_country(person_ref, payload.country_id)
