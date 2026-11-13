from fastapi import APIRouter, Query

import data
import schemas

router = APIRouter(tags=["lookups"])


@router.get("/countries", response_model=list[schemas.CountryItem])
def list_countries():
    return data.list_countries()


@router.get("/countries/{country_id}", response_model=schemas.CountryItem)
def get_country(country_id: str):
    return data.get_country(country_id)


@router.get(
    "/countries/{country_id}/persons",
    response_model=schemas.Page[schemas.PersonListItem],
)
def list_country_persons(
    country_id: str,
    sort: str = Query(default="name", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return data.list_persons(
        country_id=country_id, sort=sort, page=page, page_size=page_size
    )


@router.get("/events", response_model=list[schemas.EventItem])
def list_events(include_retired: bool = False):
    return data.list_events(include_retired)
