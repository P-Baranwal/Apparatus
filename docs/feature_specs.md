# Phase 2: Feature spec and data-layer contract

Handshake with the DB teammate. `data/mock.py` and `data/real.py` must expose **identical
names, parameters and return shapes**. Routers and the frontend depend only on this file
and on `src/schemas.py`.

Feature order below is the README order and the video order. Do not reshuffle.

Legend: `[Q]` query, `[W]` write. Every list function returns
`{"items": [...], "total": int}` and does filtering, sorting, counting and paging in the
database.

---

## 1. Data-layer functions

### Reads

| Function | Signature | Returns |
|---|---|---|
| `search_all` | `(q: str, limit: int = 5) -> dict` | `{"competitions": [...], "persons": [...]}` |
| `list_competitions` | `(q=None, country_id=None, continent_id=None, year=None, status=None, event_id=None, sort="date_desc", page=1, page_size=20) -> dict` | list of `CompetitionListItem` |
| `get_competition` | `(competition_id: str) -> dict` | `CompetitionDetail` (events, delegates, organizers, podiums) |
| `list_competition_results` | `(competition_id: str, event_id=None, round_number=None, tab="podiums", sort=None, page=1, page_size=20) -> dict` | list of `CompetitionResultItem` |
| `list_persons` | `(q=None, country_id=None, sort="name", page=1, page_size=20) -> dict` | list of `PersonListItem` |
| `get_person` | `(person_ref: int\|str) -> dict` | `PersonDetail` (competition/podium counts and personal records included) |
| `list_person_results` | `(person_ref: int\|str, event_id=None, page=1, page_size=20) -> dict` | list of `PersonResultItem` |
| `list_rankings` | `(event_id: str, kind: str = "single", country_id=None, continent_id=None, page=1, page_size=100) -> dict` | list of `RankingItem` |
| `list_countries` | `() -> list[dict]` | `CountryItem` |
| `get_country` | `(country_id: str) -> dict` | `CountryItem`; `NotFound` |
| `list_events` | `(include_retired: bool = False) -> list[dict]` | `{event_id, event_name, result_kind, status}` |
| `list_registrations` | `(competition_id: str, status=None, page=1, page_size=100) -> dict` | list of `RegistrationItem` |
| `get_registration` | `(competition_id: str, registrant_no: int) -> dict` | `RegistrationItem` |
| `stats_medals` | `() -> list[dict]` | `MedalRow`, ordered by gold desc, silver, bronze |
| `stats_competitions_by_country_year` | `(year_from=None, year_to=None) -> list[dict]` | `CountryYearRow` |
| `stats_records` | `() -> list[dict]` | `RecordRow` counts by event, kind, record code |

### Writes

| Function | Signature | Returns / raises |
|---|---|---|
| `create_registration` | `(competition_id: str, person_no: int, event_ids: list[str], guests: int = 0) -> dict` | `RegistrationItem`; `NotFound` (competition/person/event), `Conflict` (duplicate, closed, cancelled, limit), `BadInput` (event not offered) |
| `set_registration_status` | `(competition_id: str, registrant_no: int, status: str) -> dict` | `RegistrationChange` (`promoted` = earliest waiting-list entry promoted to accepted, else `None`); `BadInput` (unknown status, same status) |
| `delete_registration` | `(competition_id: str, registrant_no: int) -> None` | `None`; `NotFound`, `Conflict` when the person already has results in that competition |
| `update_person_country` | `(person_ref: int\|str, country_id: str) -> dict` | `PersonDetail`; `NotFound`, `BadInput` (unknown country, same as current), `Conflict` (last country change under 12 months ago) |

### Sort whitelists (never interpolate user input)

```python
COMPETITION_SORTS = {
    "date_desc":  "Start_Date DESC, Competition_ID ASC",
    "date_asc":   "Start_Date ASC, Competition_ID ASC",
    "name":       "Name ASC, Competition_ID ASC",
    "competitors":"registered_count DESC, Start_Date DESC",
}
PERSON_SORTS = {
    "name":         "Romanized_Name ASC, Person_No ASC",
    "competitions": "competitions_count DESC, Romanized_Name ASC",
    "podiums":      "podiums_count DESC, Romanized_Name ASC",
}
RESULT_SORTS = {
    "position": "Position ASC, Best ASC",
    "best":     "Best ASC, Position ASC",
}
```

`q` is matched with `LIKE`/regex after escaping `%` and `_`. User text is always bound as a
parameter and is never formatted into the query.

---

## 2. Feature specs

### F1 `[Q]` Home and global search

- **Type:** query
- **UI location:** header search box on every page; results on `search.html?q=`
- **Trigger:** typing a name, WCA ID prefix, competition name or city and submitting
- **Endpoint:** `GET /api/search?q=&limit=`
- **Inputs:** `q` (1-60 chars, required, trimmed), `limit` (1-20, default 5 per group)
- **Data layer:** `search_all(q, limit)`
- **Success:** two grouped lists, "Competitions" and "Persons", each row linking to
  `competition.html?id=` / `person.html?id=`
- **Failure:** empty query → 422 `invalid_input`; no matches → empty state, not an error
- **Before/after DB query:** none (read only)

### F2 `[Q]` Browse competitions with filters, sort and pagination

- **Type:** query
- **UI location:** `competitions.html`
- **Trigger:** opening the page, then changing any filter, sort or page control
- **Endpoint:** `GET /api/competitions`
- **Inputs:** `q`, `country_id`, `continent_id`, `year` (2003-2100), `status`
  (`upcoming|in_progress|past|cancelled`, nullable), `event_id`, `sort`
  (whitelist keys of `COMPETITION_SORTS`), `page` ≥ 1, `page_size` 1-100 (default 20)
- **Data layer:** `list_competitions(...)`
- **Success:** table of date, name, location, country, events count; result count and a
  pagination bar; empty state when the filters match nothing
- **Failure:** unknown `sort` → 422 (whitelist rejected, never passed through)
- **Before/after DB query:** none (read only)

### F3 `[Q]` Competition detail with related data

- **Type:** query
- **UI location:** `competition.html?id=WC2025`, tabs `info | results | registrations`
- **Trigger:** clicking a competition anywhere in the app
- **Endpoint:** `GET /api/competitions/{competition_id}` and
  `GET /api/competitions/{competition_id}/results?tab=podiums|all|by_person&event_id=&round_number=`
  and `GET /api/competitions/{competition_id}/registrations?status=`
- **Inputs:** `competition_id` (path), `tab`, `event_id`, `round_number` ≥ 1, `status`
- **Data layer:** `get_competition`, `list_competition_results`, `list_registrations`
- **Success:** header (name, date, city, venue, website, status, registration window,
  competitor limit vs registered count), General Info block, Events table with formats
  and cutoffs, Delegates, Organizers, and a results table per `tab` that includes
  attempts (`solves`) and record markers
- **Failure:** unknown id → 404 `"Competition not found."`; cancelled competition renders
  a notice instead of results
- **Before/after DB query:** none (read only)

### F4 `[Q]` Statistics

- **Type:** query
- **UI location:** `stats.html`
- **Trigger:** opening the page / switching the stat tab
- **Endpoint:** `GET /api/stats/medals`, `GET /api/stats/competitions-by-country`,
  `GET /api/stats/records`
- **Inputs:** `year_from`, `year_to` for competitions-by-country (2003-2100)
- **Data layer:** `stats_medals`, `stats_competitions_by_country_year`, `stats_records`
- **Success:** medal table by country (gold/silver/bronze/total, ties share a rank), a
  country × year count table, and record counts by event, kind and record code
- **Failure:** none beyond the standard shape; empty result renders an empty state
- **Before/after DB query:** none (read only)

### F5 `[Q]` Event rankings with regional ranks

- **Type:** query
- **UI location:** `rankings.html?event=333&type=single`
- **Trigger:** choosing an event and single/average, optionally filtering by country or
  continent
- **Endpoint:** `GET /api/rankings/{event_id}?kind=single|average&country_id=&continent_id=`
- **Inputs:** `event_id` (must exist in `events`), `kind` (enum), `country_id`,
  `continent_id`, `page` ≥ 1, `page_size` 1-100
- **Data layer:** `list_rankings(...)`
- **Success:** rank, name, WCA ID, country, best, average, competition, plus continental
  and national rank for each row; ties share a rank
- **Failure:** unknown event → 404; retired event → 400-range `BadInput` ("This event is
  retired.")
- **Before/after DB query:** none (read only)

### F6 `[Q]` Country page: persons and competitions for one country

- **Type:** query
- **UI location:** `country.html?country_id=India` (links from persons, rankings and
  competition rows)
- **Trigger:** clicking a country name anywhere
- **Endpoint:** `GET /api/countries/{country_id}/persons?sort=`, and reuse
  `GET /api/competitions?country_id=`
- **Inputs:** `country_id` (path), `sort` (whitelist keys of `PERSON_SORTS`), paging
- **Data layer:** `list_persons(country_id=...)`, `list_competitions(country_id=...)`,
  `get_country(country_id)` for the header
- **Success:** country header (name, ISO2, continent), its persons table (name, WCA ID,
  competitions, podiums) and its competitions table
- **Failure:** unknown country → 404 `"Country not found."`
- **Before/after DB query:** none (read only)

### F7 `[Q/Detail]` Person detail and results history

- **Type:** query
- **UI location:** `person.html?id=2012PARK03` (also accepts `Person_No` for no-ID persons)
- **Trigger:** clicking a person anywhere
- **Endpoint:** `GET /api/persons/{person_ref}`,
  `GET /api/persons/{person_ref}/results?event_id=`
- **Inputs:** `person_ref` (path; a `Person_No` or a WCA ID), `event_id` (optional), paging
- **Data layer:** `get_person`, `list_person_results`
- **Success:** name (plus local name when present), country, WCA ID, member since,
  delegate status, personal records table per event with world/continental/national ranks,
  and the full results history with record markers
- **Failure:** unknown person → 404; a person with no results shows an empty state
- **Before/after DB query:** none (read only)
- **Note:** `Date_of_Birth` and `Email` are never selected into any return shape.

### F8 `[W]` Register a person for a competition

- **Type:** create
- **UI location:** `competition.html?id=DCHydCubeOpenNovember2026&tab=registrations`, the
  "Register a person" form under the registrations table (the WCA site uses a separate
  `/register` page behind login; we keep the form next to the list it changes)
- **Trigger:** searching for a person, picking them, ticking events, submitting
- **Endpoint:** `POST /api/competitions/{competition_id}/registrations`
- **Inputs (Pydantic `RegistrationCreate`):** `person_no` ≥ 1, `events` 1-17 event ids,
  `guests` 0-10
- **Data layer:** `create_registration(competition_id, person_no, event_ids, guests)`
  writing `registrations` **and** the `selects` rows in one transaction
- **Success:** 201 with the created `RegistrationItem`; the status the backend assigned is
  shown (`accepted`, or `waiting_list` when accepted registrations already reach
  `Competitor_Limit`); the page refreshes the registration list
- **Failure:**
  - competition cancelled or registration window closed → `Conflict` "Registration for
    this competition is closed."
  - person already registered → `Conflict` "This person is already registered."
  - event not offered at this competition → `BadInput` "This competition does not offer
    <event>."
  - unknown person/competition → `NotFound`
- **Before/after DB query:**
  ```sql
  -- before
  SELECT COUNT(*) FROM registrations
   WHERE Competition_ID = 'DCHydCubeOpenNovember2026';
  SELECT * FROM selects WHERE Competition_ID='DCHydCubeOpenNovember2026' AND Registrant_No=31;
  -- after: count is +1, status + selects rows visible
  ```

### F9 `[W]` Change a person's represented country (12-month rule)

- **Type:** update
- **UI location:** `person.html`, "Change country" control next to the details block
- **Trigger:** selecting a country and confirming
- **Endpoint:** `PUT /api/persons/{person_ref}/country`
- **Inputs (Pydantic `PersonCountryUpdate`):** `country_id` (must exist in `countries`)
- **Data layer:** `update_person_country(person_ref, country_id)` updating
  `persons.Country_ID` and `persons.Since_Date`
- **Success:** 200 with the updated `PersonDetail`; toast "Now representing <country>."
- **Failure:**
  - last country change under 12 months ago (`Since_Date`) → `Conflict` "This person
    changed country on <date>; the 12-month rule still applies."
  - same country → `BadInput` "This person already represents <country>."
  - unknown country → `NotFound`
- **Demo keys:** eligible for a change — Person_No 125 (Yuxuan Chen, USA, `Since_Date`
  2015-08-06), 151 (Carlos Pedro Casado de Achával, Italy, 2023-08-12), 525 (Coral Yuxin
  Cai, Hong Kong, 2023-08-12). Blocked by the 12-month rule — Person_No 251 (Anuj Menta,
  India, 2026-10-28), and the 282 persons whose `Since_Date` is on or after 2025-11-12.
- **Before/after DB query:**
  ```sql
  SELECT Person_No, Country_ID, Since_Date FROM persons WHERE Person_No = 125;
  -- after: Country_ID = 'USA' → new value, Since_Date = CURRENT_DATE
  ```

### F10 `[W]` Delete a registration, including the blocked case

- **Type:** delete
- **UI location:** registration row on `competition.html?tab=registrations` and on the
  registration detail view; `<dialog>` confirm first
- **Trigger:** Delete → confirm
- **Endpoint:** `DELETE /api/competitions/{competition_id}/registrations/{registrant_no}`
- **Inputs:** `competition_id`, `registrant_no` ≥ 1
- **Data layer:** `delete_registration(...)`, removing the `selects` rows too
- **Success:** 204, row disappears, toast "Registration deleted."
- **Failure:**
  - the person already has `results` in that competition → `Conflict` "Cannot delete this
    registration because the competitor already has results in this competition."
  - unknown registration → `NotFound`
- **Demo keys:** safe to delete —
  `(CubeXWinterOpenBengaluru2026, 58)`, `(…, 59)`, `(…, 60)`,
  `(DCHydCubeOpenNovember2026, 29)`, `(…, 30)`, `(IndianPBQChampionship2026, 10)`, `(…, 11)`.
  Blocked — any accepted registration in a competition with results, e.g.
  `(BengalCubeOpen2025, 1)`.
- **Before/after DB query:**
  ```sql
  SELECT COUNT(*) FROM registrations WHERE Competition_ID='CubeXWinterOpenBengaluru2026'; -- 60 → 59
  SELECT COUNT(*) FROM selects WHERE Competition_ID='CubeXWinterOpenBengaluru2026'
                                 AND Registrant_No=58;                                  -- n → 0
  ```

### F11 `[W]` Accept or cancel a registration, promoting the waiting list

- **Type:** update (secondary write)
- **UI location:** status control in the registrations table on `competition.html`
- **Trigger:** changing a registration's status, e.g. `pending` → `accepted`, or
  `accepted` → `cancelled`
- **Endpoint:** `PATCH /api/competitions/{competition_id}/registrations/{registrant_no}`
- **Inputs (Pydantic `RegistrationStatusUpdate`):** `status` in
  `accepted|waiting_list|pending|cancelled|rejected`
- **Data layer:** `set_registration_status(...)`; inside the same transaction, whenever a
  place is available (`accepted` count < `Competitor_Limit`) and a `waiting_list`
  registration exists, the earliest one (ordered by `Registered_At` then `Registrant_No`,
  excluding the registration being changed) is promoted to `accepted`. One promotion per
  freed place, until the limit is reached.
- **Success:** 200 with `{registration, promoted}`; toast names the promoted person when
  there is one
- **Failure:** unknown status → 422; no change → `BadInput` "This registration already
  has that status."; unknown registration → `NotFound`
- **Demo keys:** `(DCHydCubeOpenNovember2026, 1)` — 24 accepted against a limit of 30 with
  3 waiting-list entries, so cancelling registrant 1 frees a place and promotes
  registrant 25 (`2026MANI01`, earliest `Registered_At`).
- **Before/after DB query:**
  ```sql
  SELECT Registrant_No, Status FROM registrations
   WHERE Competition_ID='DCHydCubeOpenNovember2026' ORDER BY Registered_At;
  -- before: 1=accepted, 24=accepted, 25=waiting_list
  -- after:  1=cancelled, 25=accepted
  ```

---

## 3. Conventions this contract relies on

- IDs are strings in JSON. The one exception is `Person_No`, which the dataset already
  uses as a numeric surrogate key and which appears as an integer everywhere
  (`person_no`, `Person_No` path segments); it is documented in the README.
- Dates are ISO strings. Result values are raw integers (centiseconds, move counts or
  multi-blind encoding) and are formatted in `ui.js` only.
- `solves` comes from `attempts` ordered by `Attempt_No`; missing attempts are not padded.
- Registrations include their `events` from `selects`.
- `status` for a competition is derived from `Cancelled_At`, `Start_Date`, `End_Date` and
  today's date — in the query, not in Python.
- No response contains `Email` or `Date_of_Birth`.
