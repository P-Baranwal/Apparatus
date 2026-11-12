# AGENTS.md

Guidance for AI coding agents working in this repository. Read this first, then `phase4_backend_frontend_plan.md` (the "plan"), which is the source of truth for architecture, code skeletons and the work breakdown. References like "Plan §5" point into it. If this file and the plan disagree, the plan wins, except for the items under **Deviations from the plan** at the bottom. `AGENTS.md` lives at the repo root; application code lives in `src/`.

---

## 1. Project at a glance

- **What:** Phase 4 of the CS4.301 Data and Applications project (Team 54, "Apparatus"): a populated database plus a Python web app modelled on the World Cube Association website (worldcubeassociation.org).
- **Mini-world:** WCA competitions, events, rounds, registrations, results and attempts, records and rankings, persons, delegates. See section 8.
- **Owned by this work (agents may build):** FastAPI backend, plain HTML/CSS/JS frontend, mock data layer, tests, README sections (stack, setup, feature list), video script.
- **Owned by the DB teammate (do not create or edit unless asked):** `schema.*`, `populate.*`, paradigm choice, the Design Changes and Schema Mapping README sections.
- **Blocked until the DB teammate delivers:** the paradigm, `db.py`, and the bodies of `data/real.py`. Until then everything runs against `data/mock.py` with `USE_MOCK=1`.
- **Deadline deliverable:** `54.zip` containing `54.mp4` (max 10 min), `phase3.pdf`, `README.md`, `src/` (see section 11).
- **Minimum to pass the spec:** at least 5 distinct queries and 3 writes (one create, one update, one delete), each reachable through a natural UI interaction. We build 6-7 queries and 4 writes as a buffer.

## 2. Stack

- Python 3.10+ (pinned to 3.12 locally), FastAPI, Uvicorn, managed with **uv**.
- DB driver added later, matching the chosen paradigm: `pymysql` + `cryptography` (MySQL), `pymongo` (MongoDB) or `neo4j` (Neo4j).
- Frontend: plain HTML, CSS and JavaScript (ES modules), served by the same FastAPI process. No framework, no npm, no build step, no chart library.
- One process serves `/api/*` (JSON) and the static frontend. No CORS.

## 3. Commands (run from `src/`)

```bash
uv sync                                                   # install deps (incl. dev)
USE_MOCK=1 uv run uvicorn app:app --reload --port 5000    # dev server on the mock layer
uv run uvicorn app:app --reload --port 5000               # dev server on the real DB
USE_MOCK=1 uv run pytest -q                               # tests against the mock (run first)
uv run pytest -q                                          # same tests against the real DB
uv add <pkg>                                              # add a dependency, then re-export:
uv export --no-hashes --no-dev --no-emit-project -o requirements.txt
```

API docs for manual testing: http://localhost:5000/docs. App: http://localhost:5000.

Re-export `requirements.txt` after **every** dependency change; graders run `pip install -r requirements.txt`.

## 4. Layout

```
src/
├── app.py            # FastAPI entry point: handlers, routers, static mount (mounted LAST)
├── config.py         # settings from env vars with safe defaults
├── errors.py         # AppError (NotFound/Conflict/BadInput) + exception handlers
├── serialization.py  # to_jsonable(): Decimal/date/ObjectId/neo4j.time -> JSON-safe
├── schemas.py        # Pydantic request/response models
├── db.py             # driver connection helper            [BLOCKED: paradigm]
├── data/
│   ├── __init__.py   # picks real or mock via USE_MOCK
│   ├── real.py       # ALL raw SQL/MQL/Cypher lives here    [BLOCKED: schema]
│   └── mock.py       # DEV ONLY, deleted before submission
├── mock_data/        # DEV ONLY JSON fixtures, deleted before submission
├── routers/          # one router per feature area, no query strings
├── static/           # *.html, css/style.css, js/{api.js, ui.js, pages/*.js}, 404.html
├── tests/            # test_contract.py, test_api.py
├── schema.*, populate.*          # DB teammate
└── pyproject.toml, uv.lock, .python-version, requirements.txt, .env.example
```

Layering rule: `routers -> data (via data/__init__) -> real.py | mock.py`. Routers contain no queries. `real.py` contains only queries and driver-error translation. Reference implementations of `config.py`, `errors.py`, `app.py`, `serialization.py`, `data/__init__.py`, `db.py` templates, `api.js` and `ui.js` are in Plan §4, §5 and §9; start from those.

## 5. Hard rules (spec compliance, never break these)

1. **No ORM, ODM, OGM, query builder or pandas** for database access. Every query is a raw SQL string, MQL filter/pipeline (Python dicts/lists) or Cypher string, run through the official driver, inside `data/real.py`.
2. **Parameterised queries only.** User input goes in as parameters (`%s`, `$name`, typed filter dicts). No f-strings or concatenation into queries, no `$where`, no user-supplied JSON used directly as a Mongo filter.
3. **`ORDER BY` / sort fields come from a whitelist dict** (`SORTS = {"name": "name ASC", ...}`). LIKE wildcards (`%`, `_`) in user input are escaped before use as a parameter.
4. **The database does the work.** Filtering, joining, aggregation, ranking, counting and pagination happen in the query. Never fetch a full table/collection and filter or sort it in Python (this applies to `real.py`; the mock may cheat).
5. **Only the backend talks to the database.** The browser never does. No endpoint accepts a free-text raw query.
6. **Credentials** come from `config.py` / env vars only. Nothing hard-coded in routers; no `.env` or real credentials in the repo or zip.
7. **Escape all output in the frontend** (`esc()` or `textContent`) wherever data reaches `innerHTML`.
8. **Constraint violations, missing records and invalid input** must render as clear human messages, never raw driver errors or silent failures.
9. **Confidential WCA fields** (`Date_of_Birth`, `Email`; Reg. 2d) must never appear in any API response, mock fixture shown in the UI, or page. Public: name, country, gender, results.

## 6. Conventions

**Data-layer contract (Plan §5).** `mock.py` and `real.py` expose identical function names, parameters and return shapes.

- Take primitives (str/int/float/date/None); return plain dicts and lists of dicts. Call `to_jsonable()` on every result before returning from `real.py`.
- List functions return `{"items": [...], "total": int}`.
- Detail functions raise `NotFound`. Writes return the affected record (create/update) or `None` (delete) and raise `Conflict` (duplicate key, FK/restrict violation) or `BadInput` (CHECK/enum/validator violation).
- `real.py` catches driver exceptions and raises domain errors; routers and the frontend never see driver types (translation table in Plan §5).
- Changing a contract signature affects the DB teammate. Ask first, and prefer adapting field names in `real.py` (SQL `AS`, Mongo `$project`, Cypher `RETURN x AS name`) over changing routers or the frontend.

**API (Plan §6).**

- Prefix `/api`, resource-style paths, plain `def` endpoints (FastAPI runs them in a threadpool; drivers are used in blocking mode).
- Lists accept `q`, filters, `sort`, `page` (default 1) and `page_size` (default 20, max 100); they return `{items, total, page, page_size}`.
- Status codes: 200 reads/updates, 201 create, 204 delete.
- Errors always return `{"detail": "<human message>", "code": "<machine code>"}`.
- IDs are always strings in JSON; dates are ISO strings.
- Pydantic models enforce types, lengths, ranges and enums at the edge; the DB constraints still have the final say.

**Frontend (Plan §9).**

- Multi-page static HTML with parameters in the query string (`detail.html?id=2012PARK03`). Not an SPA.
- Each page loads `<script type="module" src="/js/pages/<page>.js">`: read URL params -> `api()` -> render -> wire events -> catch errors into `toast()`.
- Header, nav and search bar are injected by `ui.js` on every page (no copy-paste drift).
- Every data-fetching view has loading, empty and error states. Destructive actions use a `<dialog>` confirm. Record IDs are shown subtly (small grey text) so before/after shell queries in the video are easy to match.
- One `style.css` with CSS custom properties; take palette and layout cues from the WCA site, no need to clone it. Mobile-friendly (check ~375px, ~768px, desktop), visible focus states, labels on every input.

**Python style.** Code must run on Python 3.10+ (no newer syntax, even though 3.12 is pinned locally). Type hints on data-layer functions. No ORM-style helper layers; keep `real.py` boring and explicit.

## 7. Feature plan and ordering

The README feature list and the video follow this order. Do not reshuffle it (Plan §7).

1. Home and global search (Q1)
2. Browse + filters + sort (Q2)
3. Detail page (Q3, Q5)
4. Stats page (Q4)
5. Entity-specific list (Q6)
6. Create (W1)
7. Update (W2)
8. Delete, including the blocked-delete case (W3)
9. Secondary write (W4)

Write one spec block per feature using the template in Plan §7 (type, UI location, trigger, endpoint, inputs, data-layer function, success result, failure cases, before/after demo query).

## 8. Mini-world notes (WCA)

The Team 54 Phase 1 document (`54.pdf`) is **reference only**. The schema we actually implement is the Phase 3 design of another team, delivered by the DB teammate. Entity and attribute names below come from Phase 1 and may differ; confirm against the delivered schema and contract before relying on them. Never invent schema or fields.

**Identifiers seen in the domain.** Competition `WC2025`; WCA ID `2012PARK03` (pattern `^[0-9]{4}[A-Z]{4}[0-9]{2}$`, NULL for newcomers until their first results are posted, so persons also have a surrogate key); event `333`, `333oh`, `minx`, `333mbf`; round `333-r1` (WCIF style); country `India` with ISO2 `IN`; continent `_Asia`. All IDs travel as strings.

**Result encoding (display helper needed).** Times are centiseconds; `-1` = DNF, `-2` = DNS, `0` = no result; Fewest Moves are move counts (averages x100); Multi-Blind is an encoded number where smaller is better. Add one `formatResult(value, eventId, kind)` helper in `ui.js`: never show raw values; times under 10 minutes show hundredths (`m:ss.cc`), 10 minutes and over show seconds (`m:ss`); DNF/DNS render as "DNF"/"DNS". Valid results must sort before DNF/DNS/0, and that ordering is done in the query (for example `Best > 0`), not in Python.

**Derived data.** Rankings and records are derived from results, not stored. Ties share a rank (Reg. 9f15). Compute ranks in the database (window functions, `$setWindowFields`/`$group`, or ordered Cypher aggregation, depending on paradigm). Retired events (333ft, magic, mmagic, 333mbo) exist in history; default event lists to official events.

**Candidate mapping of the plan's patterns onto WCA pages** (confirm against the schema, then fix in the feature specs):

| # | Pattern | WCA-flavoured feature | Phase 1 ref |
|---|---|---|---|
| Q1 | Search | Header search: persons by name or WCA ID prefix; competitions by name, city, venue | Q1-Q4 |
| Q2 | Browse + filter + sort | Competitions list: country/continent, year, status (upcoming / in progress / past), event; sort by date or name | S1, P2 |
| Q3 | Detail with related data | Competition page (events, round formats, cutoffs, spots left, results) and person page (per-event bests and ranks, history) | P4, S2 |
| Q4 | Aggregate / stats | Medal table, competitions per country per year, record counts | A2, J3 |
| Q5 | Relationship-heavy | Event rankings (single/average) with world/continental/national rank; world-record history with country represented that day | J1, J2 |
| Q6 | Entity-specific list | All competitions or persons for one country; delegates by region | S3, P1 |
| W1 | Create | Register a person for a competition with chosen events (accepted vs waiting list by competitor limit) | I1 |
| W2 | Update | Change a person's represented country (12-month rule) or edit/cancel a competition | U2, U3 |
| W3 | Delete | Delete a withdrawn registration; blocked when the person already has results in that competition | D1, D2 |
| W4 | Secondary write | Cancel/accept a registration, promoting the earliest waiting-list entry when a place frees up | U5 |

Writes are single transactions: if any check fails, nothing is written. A write that violates a rule raises `Conflict` or `BadInput` with a message a person can act on (for example "Cannot delete this registration because the competitor already has results in this competition.").

## 9. Mock layer (dev only)

- `mock_data/*.json` mirrors the contract's shapes and includes edge cases: a record with no related rows, a very long name, a missing optional field, a person with non-Latin local name, a record whose delete is blocked.
- `mock.py` implements every contract function in memory, including pagination, the sort whitelist and the same `NotFound`/`Conflict`/`BadInput` behaviour.
- Put `# DEV ONLY - delete before submission` at the top of every mock file. Nothing outside `data/__init__.py` may import the mock.
- Mock data should look like real WCA data, but real population data is the DB teammate's job; never use `test1`-style placeholders anywhere that could reach `populate.*`.

## 10. Testing and definition of done

1. **Contract tests** (`tests/test_contract.py`) call `data.*` directly and assert shapes, pagination bounds, not-found and conflict behaviour. Run against the mock first, then unchanged against the real layer after each `real.py` function.
2. **API tests** (`tests/test_api.py`) use `TestClient` to check status codes, the `{detail, code}` error shape and validation messages.
3. **Manual pass** through `/docs`, then the UI, for every feature in section 7.
4. **Fresh-environment test:** new venv, `pip install -r requirements.txt`, run `schema` then `populate`, start the app, click through every feature.

A feature is done when: its spec block is filled; the endpoint, contract function (mock and real) and UI all exist; contract and API tests pass; its failure cases render clear messages; a before/after shell query for the video is written down (kept outside `src/`, e.g. `docs/`); and the section 5 rules hold for the code touched.

Work through the phases in Plan §13 in order (scaffold -> feature spec and contract -> mock + API -> frontend -> docs and demo prep -> integration -> hardening -> recording and packaging). Items marked blocked wait for the DB teammate; do not guess their inputs (Plan §15 lists what we need from them).

## 11. Packaging checklist (final phase only)

```
54.zip
├── 54.mp4
├── phase3.pdf
├── README.md
└── src/  (schema.*, populate.*, app.py, requirements.txt, pyproject.toml, uv.lock,
         .python-version, config.py, db.py, errors.py, serialization.py, schemas.py,
         data/ (real.py + __init__.py), routers/, static/, tests/, .env.example)
```

- Delete `data/mock.py` and `mock_data/`, and remove the mock branch from `data/__init__.py` so it imports `real` only.
- No `.env`, `.venv/`, `__pycache__/`, mock files or credentials in the zip.
- README has: paradigm/DBMS with versions, stack, Design Changes, setup/run steps, Schema Mapping (MongoDB/Neo4j only), and a numbered feature list (page/URL, trigger, behaviour) in video order.
- Unzip somewhere clean and follow only the README to confirm the app starts.
- Run the full section 5 checklist line by line before zipping.

## 12. Boundaries

**Always**
- Keep routers free of queries and `real.py` free of anything but queries and error translation.
- Regenerate `requirements.txt` after dependency changes.
- Escape output; show errors as readable messages.
- Update the feature spec and README feature list when a feature's page, trigger or behaviour changes.

**Ask first**
- Changing a data-layer signature or return shape.
- Adding a dependency, a frontend framework, or any build tooling.
- Overriding a locked decision (single process, multi-page static frontend, sync endpoints, errors translated in the data layer, string IDs, feature ordering).
- Touching `schema.*`, `populate.*` or the Design Changes / Schema Mapping README sections.

**Never**
- Introduce an ORM, query builder, pandas or any query-generating library.
- Build a query from user input by string formatting.
- Filter, sort or aggregate in Python on the real path.
- Expose `Date_of_Birth` or `Email`.
- Commit secrets, or ship mock code.
- Add a page or endpoint that runs arbitrary user-typed queries.

## Deviations from the plan

Nothing in the plan was removed or reordered. These are small additions needed to make it work as written:

1. **`pyproject.toml`:** after setting `requires-python = ">=3.10"`, run `uv lock` so `uv.lock` matches. Also add `[tool.pytest.ini_options]` with `pythonpath = ["."]`; with a bare (non-package) uv project, `uv run pytest` otherwise cannot import `app` or `data`.
2. **Error page:** name it `static/404.html`; `StaticFiles(html=True)` serves it automatically for unknown paths.
3. **500 tests:** the catch-all handler in `errors.py` re-raises inside `TestClient` by default. Use `TestClient(app, raise_server_exceptions=False)` when asserting the 500 response shape.
4. **WCA naming:** routers and pages are named after the WCA site (`competitions`, `persons`, `rankings`/`stats`) instead of the generic `items`; the patterns, order and contract rules from Plan §5 and §7 are unchanged.
5. **WCA additions:** the `formatResult` display helper, the rule that valid results sort before DNF/DNS in the query, and the confidentiality rule for `Date_of_Birth` and `Email` (section 8 and rule 9).
6. **Test order:** mock first, then real (Plan §11 lists the commands in the opposite order).
