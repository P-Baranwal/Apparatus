from fastapi import APIRouter, Query

import data
import schemas

router = APIRouter(tags=["search"])


@router.get("/search", response_model=schemas.SearchResults)
def search(
    q: str = Query(min_length=1, max_length=60),
    limit: int = Query(default=5, ge=1, le=20),
):
    return data.search_all(q, limit)
