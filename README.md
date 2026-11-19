# Apparatus: a WCA Mini World (Team 54)

Arush Sharma (2025101011), Pranjal Baranwal (2025114004), Sai Sreemayee Sistla (2025114013),
Vinayak Sharma (2025114002)

The web application is modelled on the World Cube Association website,
<https://www.worldcubeassociation.org>. All data in the database is real WCA data.

## Technology

- **Database:** relational, MySQL 8.4 (needs MySQL 8.0.16 or later), queried with raw SQL through PyMySQL 1.2.4
- **Backend:** Python 3.10+ with FastAPI 0.162 and Uvicorn
- **Frontend:** plain HTML, CSS and JavaScript, served by FastAPI, which gets all data from the backend's JSON API at `/api`

## Setup and run

```bash
# 1. Start MySQL (Docker)
docker run -d --name wca-mysql -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -p 3306:3306 mysql:8.4

# 2. Create the schema and load the data (from the repository root)
docker exec -i wca-mysql mysql -uroot < src/schema.sql
docker exec -i wca-mysql mysql -uroot < src/populate.sql

# 3. Install dependencies and start the app
cd src
pip install -r requirements.txt
uvicorn app:app --port 5000
```

Open <http://localhost:5000>.

The app connects as `root` with no password to `127.0.0.1:3306`, database `wca_db`. To use different settings, set
`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` or `DB_NAME`.

## Design Changes

Phase 2 (EER) was done by **Team 50** and Phase 3 (relational schema) by **Team 41**. We implemented Team 41's Stage D
schema: 27 tables, 39 foreign keys, and the same keys.

| Change | Reason |
|---|---|
| `scramble_sequences`: added `Seq_Index` and used it in the primary key in place of `Sequence` | `Sequence` is long text that cannot be part of a MySQL key, and a scramble can have several sequences |
| `delegate.WCA_Email` made nullable (still unique) | 128 trainee Delegates have no published e-mail |
| `persons.Since_Date` made nullable | 8 competitors from 1982 have no recorded start date for their current country |
| Some optional details made nullable: `persons.Gender`, `results.Position`, and the venue, fee, registration-window and website columns of `competitions` | The WCA sources can leave these values out |
| `results` Best, Average, Position and record columns are loaded from WCA data, not kept up to date by triggers | The app never writes results, so the official values are stored as they are |
| Added a trigger that blocks deleting a registration once the person has results in that competition | Enforces this WCA rule in the database |

## Features

Features 1–9 are queries. Features 10–13 are writes: one create, two updates and one delete. The video shows them in this order.

1. **Search**
   - **Where:** the search box in the header (`/search.html?q=...`)
   - **What:** finds competitions by name or city, and persons by name or WCA ID.
2. **Browse competitions**
   - **Where:** `/competitions.html`
   - **What:** filter by text, country, region, event, year and status (upcoming, past or cancelled), then sort and page through the results.
3. **Competition page**
   - **Where:** click a competition (`/competition.html?id=WC2025`)
   - **What:**
     - **General Info:** dates, venue, organisers and Delegates
     - **Events:** each event's rounds with format, time limit and cutoff
     - **Results:** podiums, all results or by person, with every attempt and the records set
     - **Registrations:** the list of registrations
4. **Browse persons**
   - **Where:** `/persons.html`
   - **What:** search by name, filter by country, and sort by name, podiums or competitions.
5. **Person page**
   - **Where:** click a person (`/person.html?id=2012PARK03`)
   - **What:** personal records with world, continental and national ranks, and the results history.
6. **Rankings**
   - **Where:** `/rankings.html`
   - **What:** choose an event and single or average, and optionally a continent or country. Each row shows the world, continental and national rank.
7. **Country page**
   - **Where:** click a country (`/country.html?country_id=India`)
   - **What:** the persons and competitions of that country.
8. **Records**
   - **Where:** `/records.html`
   - **What:** counts of world, continental and national records per event.
9. **Statistics**
   - **Where:** `/stats.html`
   - **What:** a medal table by country, the number of competitions per country and year, and record counts.
10. **Register a person** (INSERT)
    - **Where:** on a competition whose registration is open, the Registrations tab, **Register a person** form
    - **How:** search for the person, tick events, then click Register.
    - **What it changes:** adds a row to `registrations` and one row per event to `selects`. The new registration is `accepted`, or `waiting_list` when the competition is full.
11. **Accept or waitlist a registration** (UPDATE)
    - **Where:** the Registrations tab, **Accept** or **Waitlist** button on a row
    - **What it changes:** updates the registration's status. If that frees a place, the earliest waiting-list registration is promoted to accepted.
12. **Change represented country** (UPDATE)
    - **Where:** a person's page, **Change represented country** form
    - **What it changes:** updates `persons.Country_ID` and `Since_Date`.
13. **Delete a registration** (DELETE)
    - **Where:** the Registrations tab, **Delete** button on a row, then confirm
    - **What it changes:** removes the registration, and its `selects` rows with it (cascade).

All SQL is in `src/data/real.py`, and every user input is passed as a `%s` parameter.
