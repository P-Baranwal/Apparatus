from typing import Optional

from fastapi import APIRouter, Query

import data
import schemas

router = APIRouter(tags=["rankings"])


@router.get("/rankings/{event_id}", response_model=schemas.Page[schemas.RankingItem])
def list_rankings(
    event_id: str,
    kind: schemas.ResultKind = "single",
    country_id: Optional[str] = Query(default=None, max_length=60),
    continent_id: Optional[str] = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
):
    return data.list_rankings(
        event_id,
        kind=kind,
        country_id=country_id,
        continent_id=continent_id,
        page=page,
        page_size=page_size,
    )
