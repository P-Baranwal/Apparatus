# Phase 4 Plan: Backend and Frontend (FastAPI + plain HTML/CSS/JS, managed with uv)

Scope: everything in Phase 4 Part B that does **not** depend on the database teammate's work. The plan is paradigm-agnostic (MySQL, MongoDB or Neo4j) and uses a stable data-layer contract so the DB can be plugged in later without touching routers or the frontend.

---

## 1. What I own vs. what is blocked

| Area | Status | Notes |
|---|---|---|
| Project scaffold, uv setup, folder layout | Can start now | |
| FastAPI app, routers, Pydantic models, error handling | Can start now | Runs against a mock data layer |
| Frontend pages, CSS, JS, UX flows | Can start now | Needs the website's layout, not the DB |
| Mock data layer + contract tests | Can start now | Dev-only, removed before submission |
| README sections (stack, setup, feature list) | Can start now | |
| Video demo script | Can start now | |
| `schema.*`, `populate.*` | **DB teammate** | |
| `data/real.py` (raw queries) | **Blocked** on paradigm + schema | Signatures are ready from day one; bodies come later |
| `db.py` driver connection | **Blocked** on paradigm | Three templates are in section 5 |
| Design Changes / Schema Mapping README sections | **DB teammate** | |

---

## 2. Decisions to lock now

Make these calls early; everything else follows from them.

1. **Serving model:** one FastAPI process serves `/api/*` (JSON) and the static frontend. No CORS, one command to run.
2. **Routing model:** multi-page static HTML, with parameters in the query string (`detail.html?id=42`). It is simple, URLs are shareable, and it is easy to demo. Not an SPA.
3. **Sync vs async:** plain `def` endpoints (PyMySQL, pymongo and the Neo4j driver are used in blocking mode; FastAPI runs `def` routes in a threadpool).
4. **Where errors are translated:** inside the data layer. `data/real.py` catches driver exceptions and raises domain errors (`NotFound`, `Conflict`, `BadInput`). Routers and the frontend never see driver types.
5. **IDs:** always strings in JSON (works for ints, ObjectIds and Neo4j ids/element ids alike).
6. **Feature list ordering:** the order in the README = the order in the video. Fix it in section 7 and don't reshuffle later.

---

## 3. Setup with uv

The project root for uv is `src/`, so `src/` is self-contained and matches the submission layout.

```bash
mkdir -p src && cd src
uv init --bare --python 3.12          # creates pyproject.toml only
uv python pin 3.12                     # writes .python-version
uv add fastapi "uvicorn[standard]"
uv add --dev pytest httpx              # httpx is needed by FastAPI's TestClient

# Added LATER, once the paradigm is known (pick one):
# uv add pymysql cryptography          # cryptography is needed for MySQL 8 caching_sha2_password auth
# uv add pymongo
# uv add neo4j

uv run uvicorn app:app --reload --port 5000
```

**Edit `pyproject.toml`** so `requires-python = ">=3.10"` (graders may not have 3.12).

**The spec requires `requirements.txt`**, and graders will run `pip install -r requirements.txt`. Regenerate it every time dependencies change:

```bash
uv export --no-hashes --no-dev --no-emit-project -o requirements.txt
```

Verify in a clean environment before submitting:

```bash
python -m venv /tmp/verify && /tmp/verify/bin/pip install -r requirements.txt
/tmp/verify/bin/uvicorn app:app --port 5001   # should boot
```

Commit `pyproject.toml`, `uv.lock` and `.python-version`; add `.venv/`, `.env`, `__pycache__/` to `.gitignore`. Ship `.env.example` with placeholder credentials.

---

## 4. Architecture and folder layout

```
src/
├── app.py                 # FastAPI app (required entry point): handlers, routers, static mount
├── config.py              # settings from env vars with safe defaults
├── errors.py              # AppError hierarchy + exception handlers
├── serialization.py       # Decimal/date/ObjectId/neo4j.time -> JSON-safe
├── schemas.py             # Pydantic request/response models
├── db.py                  # driver connection helper            [BLOCKED: paradigm]
├── data/
│   ├── __init__.py        # picks real or mock implementation via USE_MOCK
│   ├── real.py            # ALL raw SQL / MQL / Cypher lives here [BLOCKED: schema]
│   └── mock.py            # dev-only in-memory implementation (do NOT ship)
├── mock_data/             # dev-only JSON fixtures (do NOT ship)
├── routers/
│   ├── search.py          # one router per feature area
│   ├── items.py
│   └── stats.py
├── static/
│   ├── index.html         # home
│   ├── search.html
│   ├── browse.html
│   ├── detail.html
│   ├── form.html          # create/edit (or separate create.html / edit.html)
│   ├── stats.html
│   ├── css/style.css
│   └── js/
│       ├── api.js         # fetch wrapper
│       ├── ui.js          # toast, modal, render helpers, escaping
│       └── pages/         # one module per page
├── tests/
│   ├── test_contract.py   # same tests run against mock now, real later
│   └── test_api.py
├── schema.(sql|js|cypher) # DB teammate
├── populate.(sql|js|cypher)
├── pyproject.toml, uv.lock, .python-version, requirements.txt, .env.example
```

**Layering rule:** `routers → data (via data/__init__) → real.py/mock.py`. Routers hold no query strings; `data/real.py` holds nothing but queries and error translation.

### `data/__init__.py` (swap mock/real with one env var)

```python
import os
from importlib import import_module

_impl = import_module("data.mock" if os.getenv("USE_MOCK") == "1" else "data.real")

def __getattr__(name):          # data.search_items(...) -> _impl.search_items(...)
    return getattr(_impl, name)
```

Run with the mock: `USE_MOCK=1 uv run uvicorn app:app --reload --port 5000`.

### `config.py`

```python
import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))      # 27017 for Mongo, 7687 for Neo4j
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "miniworld")
```

### `errors.py`

```python
import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("app")

class AppError(Exception):
    status_code = 500
    def __init__(self, detail: str, code: str | None = None):
        self.detail, self.code = detail, code

class NotFound(AppError):  status_code = 404
class Conflict(AppError):  status_code = 409   # duplicate key, FK / restrict violation
class BadInput(AppError):  status_code = 422   # validator / CHECK / enum violation

def register_error_handlers(app):
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse({"detail": exc.detail, "code": exc.code}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        # Flatten FastAPI's default list into one readable string
        msg = "; ".join(f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors())
        return JSONResponse({"detail": msg or "Invalid input.", "code": "invalid_input"}, status_code=422)

    @app.exception_handler(Exception)
    async def fallback(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse({"detail": "Something went wrong on the server.", "code": "server_error"}, status_code=500)
```

### `app.py`

```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from errors import register_error_handlers
from routers import search, items, stats

BASE = Path(__file__).parent
app = FastAPI(title="Mini World API")
register_error_handlers(app)

for r in (search.router, items.router, stats.router):
    app.include_router(r, prefix="/api")

# Mount LAST so /api/* routes win
app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
```

### `serialization.py`

```python
from decimal import Decimal
from datetime import date, datetime, time

def to_jsonable(o):
    if isinstance(o, dict):  return {k: to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)): return [to_jsonable(v) for v in o]
    if isinstance(o, Decimal): return float(o)
    if isinstance(o, (datetime, date, time)): return o.isoformat()
    if hasattr(o, "to_native"): return to_jsonable(o.to_native())   # neo4j.time.*
    if o.__class__.__name__ == "ObjectId": return str(o)            # pymongo, no import needed
    return o
```

Call `to_jsonable()` on every result inside `data/real.py` before returning, so routers always get plain dicts.

---

## 5. Data-layer contract

This is the handshake with the DB teammate. `data/mock.py` and `data/real.py` expose **identical function names, parameters and return shapes**. Fill this table in during Phase 1 of the work plan; it also becomes the README feature list skeleton.

**Rules for every function**

- Takes primitives (str/int/float/date/None), returns plain dicts and lists of dicts.
- List functions return `{"items": [...], "total": int}`, doing filtering, sorting, `LIMIT/OFFSET` and counting **in the database**.
- Detail functions raise `NotFound` for a missing record.
- Write functions return the affected record (create/update) or `None` (delete), and raise `Conflict` / `BadInput` for constraint violations.
- Sorting uses a **whitelist dict** (`SORTS = {"name": "name ASC", ...}`); `ORDER BY` can never be parameterised.
- LIKE wildcards in user input (`%`, `_`) are escaped before being used as a parameter.

**Driver error translation** (lives in `real.py`):

| Situation | MySQL (PyMySQL) | MongoDB (pymongo) | Neo4j | Raise |
|---|---|---|---|---|
| Duplicate key | `IntegrityError` 1062 | `DuplicateKeyError` | `ConstraintError` | `Conflict` |
| FK violation / delete blocked | `IntegrityError` 1451 / 1452 | app-level check you write | app-level check (count rels first) | `Conflict` |
| CHECK / enum / validator | `IntegrityError` 3819 / `DataError` | `WriteError` code 121 | app-level check | `BadInput` |
| Row not found | `rowcount == 0` / no row | `matched_count == 0` | empty result | `NotFound` |

### `db.py` templates (pick one when the paradigm is known)

```python
# --- MySQL ---
import pymysql, config
from contextlib import contextmanager

@contextmanager
def cursor():
    conn = pymysql.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER,
                           password=config.DB_PASSWORD, database=config.DB_NAME,
                           cursorclass=pymysql.cursors.DictCursor, autocommit=False)
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
```

```python
# --- MongoDB ---
from pymongo import MongoClient
import config
_client = MongoClient(config.DB_HOST, config.DB_PORT)
db = _client[config.DB_NAME]
```

```python
# --- Neo4j ---
from neo4j import GraphDatabase
import config
driver = GraphDatabase.driver(f"bolt://{config.DB_HOST}:{config.DB_PORT}",
                              auth=(config.DB_USER, config.DB_PASSWORD))
# usage: with driver.session(database=config.DB_NAME) as s: s.run(CYPHER, name=value)
```

---

## 6. API conventions

- Prefix `/api`; resource-style paths (`GET /api/items`, `GET /api/items/{id}`, `POST /api/items`, `PUT /api/items/{id}`, `DELETE /api/items/{id}`).
- Lists accept `q`, filter params, `sort`, `page` (default 1), `page_size` (default 20, max 100) and return `{items, total, page, page_size}`.
- Success codes: 200 reads/updates, 201 create (with `Location` or the created record), 204 delete.
- Errors always return `{"detail": "<human readable message>", "code": "<machine code>"}`.
- Dates are ISO strings; money as numbers; IDs as strings.
- Pydantic models in `schemas.py` enforce types, lengths, ranges and enums at the edge (`Field(min_length=1, max_length=100)`, `Literal[...]`, `ge/le`). This is a first line of defence; the DB constraints still decide.
- Use FastAPI's `/docs` page to exercise every endpoint before any frontend exists. Take screenshots later as backup demo evidence.

---

## 7. Feature plan

The spec needs **at least 5 queries and 3 writes (one create, one update, one delete)**, each reachable through a natural UI interaction. Plan for **6-7 queries and 4 writes** so that one broken feature doesn't sink the minimum.

### Recommended feature patterns (map each onto the real website once it's known)

| # | Type | Pattern | UI trigger | Why it's a good demo |
|---|---|---|---|---|
| Q1 | Query | **Search by name/keyword** | Search bar in header | Simple, expected on any site |
| Q2 | Query | **Browse with filters + sort + pagination** | Filter panel and sort dropdown on `browse.html` | Shows `WHERE`/`ORDER BY`/`LIMIT` in DB |
| Q3 | Query | **Detail page with related data** (join / `$lookup` / pattern match) | Click an item | Demonstrates the schema's relationships |
| Q4 | Query | **Aggregate / stats** (top N, counts per category, averages) | `stats.html` or a home-page widget | `GROUP BY` / `$group` / aggregation |
| Q5 | Query | **Relationship-heavy** (e.g., "related items", "everything connected to X", multi-hop) | Section on the detail page | The most database-flavoured query |
| Q6 | Query | **Entity-specific list** (e.g., all items under a parent/category/person) | Click a category or person | Reuses Q2's skeleton cheaply |
| W1 | Create | **Add a record (and its link, if many-to-many)** | "Add" form with validation | Before/after demo is easy |
| W2 | Update | **Edit a record** | "Edit" form prefilled from Q3 | |
| W3 | Delete | **Delete a record** with confirm modal | Delete button on detail page | Also demo the blocked-delete message |
| W4 | Create/Update | **Secondary write** (e.g., submit a rating/review, toggle a status) | Inline control | Buffer in case another write fails |

### Per-feature spec template (copy one block per feature)

```
### F<n>: <name>
- Type: query | create | update | delete
- UI location: <page / URL>
- Trigger: <what the user does>
- Endpoint: <METHOD /api/...>
- Inputs: <params + validation rules>
- data-layer function: <name(args) -> shape>
- Success result: <what the page shows>
- Failure cases: <not found / duplicate / constraint> -> <message shown>
- Demo before/after DB query: <the shell query to run in the video>
```

### Ordering (README list and video follow this order)

1. Home and global search (Q1)
2. Browse + filters + sort (Q2)
3. Detail page (Q3, Q5)
4. Stats page (Q4)
5. Entity-specific list (Q6)
6. Create (W1)
7. Update (W2)
8. Delete, including the blocked-delete case (W3)
9. Secondary write (W4)

---

## 8. Error handling and validation

| Layer | Responsibility |
|---|---|
| Pydantic (`schemas.py`) | Types, required fields, lengths, ranges, enums. Returns 422 with a flattened message. |
| `data/real.py` | Translates driver errors into `NotFound` / `Conflict` / `BadInput`. |
| `errors.py` | Converts domain errors and unexpected exceptions to `{detail, code}` JSON. |
| `api.js` | Throws `Error(detail)` on any non-2xx response. |
| `ui.js` | Shows the message in a toast or inline banner; never fails silently. |

Messages should be written for humans: *"Cannot delete this item because 3 records still reference it."* beats *"IntegrityError 1451"*.

---

## 9. Frontend plan

### Pages (adjust to mirror the real website's navigation)

1. **Home**: hero + search bar, featured/top items (Q4), category tiles.
2. **Search results**: results as cards or rows, pagination, empty state.
3. **Browse**: filter sidebar, sort dropdown, results grid, pagination.
4. **Detail**: main info, related items, edit and delete actions.
5. **Create/Edit form**: shared form component, inline field errors, prefilled in edit mode.
6. **Stats**: tables or simple CSS bar charts (no chart library needed).
7. **404 / error state**: a friendly fallback.

### Shared pieces

- **Header/nav + search bar** injected on every page by `ui.js` (avoids copy-paste drift).
- **Toast / banner** for success and error messages.
- **Confirm modal** for destructive actions (use `<dialog>`).
- **Pagination component.**
- **Loading, empty and error states** for every data-fetching view.
- **Record IDs shown subtly** (small grey text on cards/detail) so before/after DB queries in the video are easy to match.

### `js/api.js`

```js
export async function api(path, { method = "GET", body, params } = {}) {
  const url = new URL("/api" + path, location.origin);
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== "" && v != null) url.searchParams.set(k, v);
  }
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Cannot reach the server. Is it running?");
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail ?? `Request failed (${res.status})`);
  return data;
}
```

### `js/ui.js` essentials

```js
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function toast(message, kind = "info") { /* append to #toasts, auto-dismiss */ }
export function confirmDialog(message) { /* returns Promise<boolean> using <dialog> */ }
```

**Always escape data inserted via `innerHTML`** (or use `textContent`). The data comes from a DB and from users, so this prevents XSS.

### Styling

- One `style.css` with CSS custom properties (colours, spacing, radius, font) so the theme can be changed in one place.
- Take the colour palette, typography feel and layout cues from the real website; no need to clone it.
- Mobile-friendly with CSS grid/flexbox; light touch, no framework.
- Visible focus states, labels on every input, sufficient contrast.

### Page module pattern

Each HTML page loads `<script type="module" src="/js/pages/<page>.js">`. Each module: read URL params → call `api()` → render → wire events → catch errors into `toast()`.

---

## 10. Mock data strategy (dev-only)

- `mock_data/*.json` mirrors the contract's return shapes and includes edge cases: an item with no related records, a long name, a missing optional field, a record that "cannot be deleted".
- `data/mock.py` implements every contract function in memory, including pagination, sort whitelists and the same `NotFound`/`Conflict` errors.
- The mock exists to unblock UI work. It may filter in Python because it is not the submission path.
- **Delete `data/mock.py` and `mock_data/` before zipping** so the submission contains no Python-side filtering that could be misread as violating "do the work in the database."

---

## 11. Testing

1. **Contract tests** (`tests/test_contract.py`) call `data.*` functions directly and assert shapes, pagination bounds, not-found and conflict behaviour. Run them first against the mock, then unchanged against the real layer, which is the main integration safety net.
2. **API tests** (`tests/test_api.py`) use `fastapi.testclient.TestClient` to check status codes, error JSON shape and validation messages.
3. **Manual pass** via `/docs`, then the UI, for every feature in section 7.
4. **Fresh-environment test**: new venv, `pip install -r requirements.txt`, run `schema` then `populate`, start the app, click through every feature.

```bash
uv run pytest -q
USE_MOCK=1 uv run pytest -q
```

---

## 12. Spec-compliance checklist (code level)

- [ ] No ORM, ODM, OGM, query builder or pandas for DB access.
- [ ] Every query is a raw string / dict / pipeline in `data/real.py`.
- [ ] User input is **always** passed as parameters (`%s`, `$name`, typed filter dicts); no f-strings in queries, no `$where`, no raw user JSON as a Mongo filter.
- [ ] `ORDER BY` / sort field chosen through a whitelist.
- [ ] Filtering, joining, aggregation and pagination happen in the database.
- [ ] The browser never talks to the DB; only the backend does, via the official driver.
- [ ] No endpoint accepts a free-text raw query.
- [ ] Credentials come from `config.py` / env vars, with none hard-coded in routers.
- [ ] All output escaped in the frontend.
- [ ] Errors rendered as clear messages for constraint violations, missing records and invalid input.

---

## 13. Work breakdown

Effort is relative; order matters more than hours. Items marked **[B]** are blocked until DB input arrives.

### Phase 0: Alignment (do first, ~30 min)
- [ ] Share this plan with the team; confirm serving model and conventions in section 2.
- [ ] Ask the DB teammate for the items in section 15.
- [ ] Open the real website; screenshot its main pages and note navigation and flows.

### Phase 1: Scaffold
- [ ] Create `src/`, run uv setup (section 3), `.gitignore`, `.env.example`.
- [ ] Add `app.py`, `config.py`, `errors.py`, `serialization.py`, empty routers.
- [ ] Add `data/__init__.py` with the mock/real switch.
- [ ] Confirm `uv run uvicorn app:app` boots and `/docs` loads.

### Phase 2: Feature spec and contract
- [ ] Choose features from section 7's patterns, fitted to the real website and the Phase 3 entities (needs the entity list, not the DB itself).
- [ ] Fill one spec block per feature.
- [ ] Define `schemas.py` and the data-layer function signatures; share them with the DB teammate.

### Phase 3: Mock layer + API
- [ ] Write `mock_data/` fixtures and `data/mock.py`.
- [ ] Implement routers against the data layer; test through `/docs`.
- [ ] Write contract and API tests.

### Phase 4: Frontend
- [ ] `style.css` tokens, layout, components.
- [ ] `api.js`, `ui.js` (header, toast, modal, pagination, escape helper).
- [ ] Pages in this order: Home/Search → Browse → Detail → Create/Edit → Delete flow → Stats.
- [ ] Loading, empty and error states everywhere.
- [ ] Responsive check at ~375px, ~768px and desktop widths.

### Phase 5: Docs and demo prep (parallel with Phase 4)
- [ ] Draft README sections owned by me (section 16).
- [ ] Write the video script (section 17) and the list of before/after shell queries (placeholders until the schema exists).

### Phase 6: Integration **[B]**
- [ ] Choose the `db.py` template; add the driver with `uv add`; regenerate `requirements.txt`.
- [ ] Implement `data/real.py` function by function, in the order of section 7.
- [ ] Run the contract tests against real data after each function (`USE_MOCK` unset).
- [ ] Fix mismatches in field names/shapes, preferring changes in `real.py` over changes to routers or the frontend.
- [ ] Test every write against real constraints (duplicate, FK, delete-restricted).

### Phase 7: Hardening
- [ ] Remove `data/mock.py` and `mock_data/`; delete the mock branch in `data/__init__.py`.
- [ ] Run the section 12 checklist line by line.
- [ ] Fresh-venv test (section 3), then full run from empty DB: `schema` → `populate` → app.
- [ ] Final README pass; confirm the feature list matches the video order.

### Phase 8: Recording and packaging
- [ ] Record the video (section 17), at most 10 minutes.
- [ ] Build the zip (section 18) and unzip it somewhere else to verify it runs.

---

## 14. Integration-day playbook

1. Pull the final `schema` and `populate`; load them into a fresh DB.
2. Write one `real.py` function, run its contract test, fix, repeat.
3. When a field name differs from the mock, rename in `real.py` (aliasing in SQL `AS`, Mongo `$project`, Cypher `RETURN x AS name`) rather than touching the frontend.
4. Check each write through the UI **and** the DB shell. Note a before/after query for the video as you go.
5. Make sure the seed data includes at least: a record that is safe to delete, a record whose delete is blocked or cascades, a record that matches no joins (for the empty state), and a record with a long name or special characters (for layout and escaping).

---

## 15. What I need from the DB teammate

- Chosen paradigm, DBMS and **version**.
- The Phase 3 schema (ER diagram + relational schema) and any design changes they plan.
- List of entities, key attributes and relationships (enough to finalise the contract in Phase 2).
- Delete semantics per entity (cascade / restrict / nullify) so the UI messages match.
- A running local instance, credentials, and the expected `schema`/`populate` run commands.
- Seed data covering the cases in section 14, step 5.
- Sample documents / rows / nodes for each entity to align field names.

**What they get from me:** the function signatures and return shapes (section 5), the sort whitelists and filter parameters for each list query, and the list of before/after queries needed for the video.

---

## 16. README sections I will draft

```markdown
## Stack
- Backend: FastAPI (Python 3.x), Uvicorn, <driver + version>
- Frontend: plain HTML / CSS / JavaScript (ES modules), served by FastAPI
- Package management: uv (a pinned requirements.txt is also provided)

## Setup and run
1. Load the schema:   <command>
2. Load the data:     <command>
3. Install deps:      `cd src && pip install -r requirements.txt`   (or `uv sync`)
4. Configure DB access: copy `.env.example` to `.env` or export DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
5. Start the app:     `uvicorn app:app --port 5000`   (or `uv run uvicorn app:app --port 5000`)
6. Open:              http://localhost:5000

## Features (same order as the video)
1. <Name>: <page/URL>, <how to trigger>, <what it does>.
2. ...
```

The Design Changes and Schema Mapping sections stay with the DB teammate; the feature list needs my input per feature (page, trigger, behaviour).

---

## 17. Video demo script (max 10 minutes)

Two windows side by side: browser on the left, DB shell on the right.

1. **Opening (30-60 s):** name the website the UI is modelled on; tour home, browse, detail, stats and the forms.
2. **Queries:** run each query feature from the UI, in feature-list order, and show the data is correct (briefly cross-check one or two against the shell).
3. **Create:** shell query *before* → add through the form → re-run the same query *after*.
4. **Update:** shell query *before* → edit through the form → same query *after*.
5. **Delete:** shell query *before* → delete via the button + confirm → same query *after*.
6. **Blocked delete / validation error:** show a constraint violation rendered as a clear message.
7. **Wrap-up (10 s):** mention the README feature list.

Preparation: keep the "before/after" shell queries in a text file ready to paste; use records that are safe to delete; do one full dry run before recording; keep IDs visible in the UI.

---

## 18. Final packaging checklist

```
<team_number>.zip
├── <team_number>.mp4
├── phase3.pdf
├── README.md
└── src/
    ├── schema.* , populate.*
    ├── app.py , requirements.txt (+ pyproject.toml, uv.lock, .python-version)
    ├── config.py, db.py, errors.py, serialization.py, schemas.py
    ├── data/ (real.py only), routers/, static/, tests/
    └── .env.example
```

- [ ] Zip is named `<team_number>.zip`, with the four required items at the **root**.
- [ ] No `.env`, `.venv/`, `__pycache__/`, mock files or real credentials in the zip.
- [ ] README has: paradigm/DBMS + versions, stack, Design Changes, setup/run steps, Schema Mapping (if Mongo/Neo4j), numbered feature list matching the video.
- [ ] Unzip on a clean directory and follow only the README to confirm the app starts.

---

## 19. Risks and mitigations

| Risk | Mitigation |
|---|---|
| DB input arrives late | Contract + mock let the whole UI be finished and testable first; integration is mechanical |
| Field names/shapes differ from mock | Adapt in `real.py` via aliasing; contract tests catch it |
| A write feature breaks on real constraints | Build 4 writes; test each against duplicate/FK/validator cases early |
| `requirements.txt` out of sync with uv | Re-export after every `uv add`; fresh-venv test before packaging |
| MySQL 8 auth error with PyMySQL | `uv add cryptography` alongside `pymysql` |
| Python-side filtering sneaks in | Contract rule + code review against section 12 |
| Mock code accidentally shipped | Phase 7 removal step and the packaging checklist |
| Video runs over 10 minutes | Script and dry run; prefer one clear example per feature |
