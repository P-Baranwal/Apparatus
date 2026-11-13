from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from errors import register_error_handlers
from routers import competitions, lookups, persons, rankings, search, stats

BASE = Path(__file__).parent

app = FastAPI(title="WCA-inspired Mini World API")
register_error_handlers(app)

for r in (search.router, competitions.router, persons.router, rankings.router,
          lookups.router, stats.router):
    app.include_router(r, prefix="/api")

# Mounted last so /api/* routes win.
app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
