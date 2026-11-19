"""Shared test setup.

Mock runs reset the in-memory fixtures. Real runs snapshot the three tables the
writes touch and restore them before every test, so the suite is order-independent
and can be re-run against the same database.
"""

import os

import pytest

USING_MOCK = os.getenv("USE_MOCK") == "1"

SNAPSHOTS = [
    (
        "_seed_persons",
        "SELECT Person_No, Country_ID, Since_Date FROM persons",
        "Person_No",
    ),
    (
        "_seed_registrations",
        "SELECT * FROM registrations",
        "Competition_ID, Registrant_No",
    ),
    (
        "_seed_selects",
        "SELECT * FROM selects",
        "Competition_ID, Registrant_No, Event_ID",
    ),
]


def _restore():
    import db

    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE persons p JOIN _seed_persons s ON s.Person_No = p.Person_No
               SET p.Country_ID = s.Country_ID, p.Since_Date = s.Since_Date
            """
        )
        cur.execute(
            """
            DELETE r FROM registrations r
            LEFT JOIN _seed_registrations s
              ON s.Competition_ID = r.Competition_ID
             AND s.Registrant_No = r.Registrant_No
            WHERE s.Registrant_No IS NULL
            """
        )
        cur.execute(
            """
            UPDATE registrations r
              JOIN _seed_registrations s
                ON s.Competition_ID = r.Competition_ID
               AND s.Registrant_No = r.Registrant_No
               SET r.Person_No = s.Person_No,
                   r.Status = s.Status,
                   r.Registered_At = s.Registered_At,
                   r.Guests = s.Guests,
                   r.Guardian_Consent = s.Guardian_Consent
            """
        )
        cur.execute(
            """
            INSERT INTO registrations
            SELECT s.* FROM _seed_registrations s
            LEFT JOIN registrations r
              ON r.Competition_ID = s.Competition_ID
             AND r.Registrant_No = s.Registrant_No
            WHERE r.Registrant_No IS NULL
            """
        )
        cur.execute(
            """
            DELETE x FROM selects x
            LEFT JOIN _seed_selects s
              ON s.Competition_ID = x.Competition_ID
             AND s.Registrant_No = x.Registrant_No
             AND s.Event_ID = x.Event_ID
            WHERE s.Event_ID IS NULL
            """
        )
        cur.execute(
            """
            INSERT INTO selects
            SELECT s.* FROM _seed_selects s
            LEFT JOIN selects x
              ON x.Competition_ID = s.Competition_ID
             AND x.Registrant_No = s.Registrant_No
             AND x.Event_ID = s.Event_ID
            WHERE x.Event_ID IS NULL
            """
        )


@pytest.fixture(scope="session", autouse=True)
def snapshot_db():
    if not USING_MOCK:
        import db

        with db.cursor() as cur:
            for name, select, key in SNAPSHOTS:
                cur.execute(f"DROP TABLE IF EXISTS {name}")
                cur.execute(f"CREATE TABLE {name} AS {select}")
                cur.execute(f"ALTER TABLE {name} ADD PRIMARY KEY ({key})")
    yield
    if not USING_MOCK:
        import db

        _restore()
        with db.cursor() as cur:
            for name, _, _ in SNAPSHOTS:
                cur.execute(f"DROP TABLE IF EXISTS {name}")


@pytest.fixture(autouse=True)
def reset():
    if USING_MOCK:
        import data

        data.mock._reset()
        yield
        return
    _restore()
    yield
