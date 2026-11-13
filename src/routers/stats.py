from typing import Optional

from fastapi import APIRouter, Query

import data
import schemas

router = APIRouter(tags=["stats"])


@router.get("/stats/medals", response_model=list[schemas.MedalRow])
def stats_medals():
    return data.stats_medals()


@router.get(
    "/stats/competitions-by-country",
    response_model=list[schemas.CountryYearRow],
)
def stats_competitions_by_country(
    year_from: Optional[int] = Query(default=None, ge=2003, le=2100),
    year_to: Optional[int] = Query(default=None, ge=2003, le=2100),
):
    return data.stats_competitions_by_country_year(year_from, year_to)


@router.get("/stats/records", response_model=list[schemas.RecordRow])
def stats_records():
    return data.stats_records()
