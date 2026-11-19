"""Raw SQL against the MySQL schema delivered by the DB teammate.

Every function here runs parameterised SQL through the PyMySQL driver and returns
plain JSON-safe dicts. Filtering, sorting, ranking, aggregation and pagination all
happen in the database; this module only names columns and groups nested rows.
"""

from typing import Optional, Union

import pymysql

import db
from errors import BadInput, Conflict, NotFound
from serialization import to_jsonable

COMPETITION_SORTS = {
    "date_desc": "Start_Date DESC, Competition_ID ASC",
    "date_asc": "Start_Date ASC, Competition_ID ASC",
    "name": "Name ASC, Competition_ID ASC",
    "competitors": "registered_count DESC, Start_Date DESC",
}

PERSON_SORTS = {
    "name": "Romanized_Name ASC, Person_No ASC",
    "competitions": "competitions_count DESC, Romanized_Name ASC",
    "podiums": "podiums_count DESC, Romanized_Name ASC",
}

RESULT_SORTS = {
    "position": "Position ASC, Best ASC",
    "best": "Best ASC, Position ASC",
}

COMPETITION_SORT_SQL = {
    "date_desc": "c.Start_Date DESC, c.Competition_ID ASC",
    "date_asc": "c.Start_Date ASC, c.Competition_ID ASC",
    "name": "c.Name ASC, c.Competition_ID ASC",
    "competitors": "registered_count DESC, c.Start_Date DESC",
}

PERSON_SORT_SQL = {
    "name": "LOWER(p.Romanized_Name) ASC, p.Person_No ASC",
    "competitions": "competitions_count DESC, LOWER(p.Romanized_Name) ASC",
    "podiums": "podiums_count DESC, LOWER(p.Romanized_Name) ASC",
}

RESULT_ORDER_SQL = {
    "position": "e.Display_Rank ASC, r.Round_Number ASC, COALESCE(r.Position, 999) ASC, r.Event_ID ASC",
    "best": "r.Best ASC, r.Event_ID ASC, COALESCE(r.Position, 999) ASC",
    "by_person": "LOWER(p.Romanized_Name) ASC, e.Display_Rank ASC, r.Round_Number ASC, r.Event_ID ASC",
}

STATUS_SQL = """CASE
    WHEN c.Cancelled_At IS NOT NULL THEN 'cancelled'
    WHEN c.End_Date < CURDATE() THEN 'past'
    WHEN c.Start_Date <= CURDATE() THEN 'in_progress'
    ELSE 'upcoming'
  END"""

COMPETITION_FROM = """
  FROM competitions c
  JOIN countries co ON co.Country_ID = c.Country_ID
  LEFT JOIN (
    SELECT Competition_ID, COUNT(*) AS cnt
    FROM registrations
    WHERE Status = 'accepted'
    GROUP BY Competition_ID
  ) reg ON reg.Competition_ID = c.Competition_ID
"""

FINAL_ROUNDS = """
  SELECT Competition_ID, Event_ID, MAX(Round_Number) AS Final
  FROM rounds
  GROUP BY Competition_ID, Event_ID
"""

REGISTRATION_SELECT = """
  SELECT reg.Competition_ID AS competition_id,
         reg.Registrant_No AS registrant_no,
         reg.Person_No AS person_no,
         p.Romanized_Name AS name,
         p.WCA_ID AS wca_id,
         reg.Status AS status,
         reg.Registered_At AS registered_at,
         reg.Guests AS guests,
         reg.Guardian_Consent AS guardian_consent,
         (SELECT GROUP_CONCAT(s.Event_ID ORDER BY s.Event_ID SEPARATOR ',')
            FROM selects s
           WHERE s.Competition_ID = reg.Competition_ID
             AND s.Registrant_No = reg.Registrant_No) AS event_csv
    FROM registrations reg
    JOIN persons p ON p.Person_No = reg.Person_No
"""


# --- helpers ---------------------------------------------------------------


def _paging(page, page_size):
    if page < 1:
        raise BadInput("Page must be 1 or greater.", "invalid_page")
    if not 1 <= page_size <= 100:
        raise BadInput("Page size must be between 1 and 100.", "invalid_page_size")
    return int(page), int(page_size), (int(page) - 1) * int(page_size)


def _checked_sort(whitelist, sort, default):
    if sort is None:
        sort = default
    if sort not in whitelist:
        raise BadInput(f"Unknown sort '{sort}'.", "invalid_sort")
    return sort


def _like_contains(text):
    escaped = str(text).replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"


def _like_prefix(text):
    escaped = str(text).replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"{escaped}%"


def _solves(csv):
    return [int(value) for value in csv.split(",")] if csv else []


def _event_list(csv):
    return csv.split(",") if csv else []


def _competition_exists(cur, competition_id):
    cur.execute(
        "SELECT 1 AS found FROM competitions WHERE Competition_ID = %s",
        (competition_id,),
    )
    if cur.fetchone() is None:
        raise NotFound("Competition not found.", "competition_not_found")


def _resolve_person(cur, person_ref):
    if isinstance(person_ref, int) or str(person_ref).isdigit():
        cur.execute(
            "SELECT Person_No, Country_ID, Since_Date, Romanized_Name"
            " FROM persons WHERE Person_No = %s",
            (int(person_ref),),
        )
    else:
        cur.execute(
            "SELECT Person_No, Country_ID, Since_Date, Romanized_Name"
            " FROM persons WHERE WCA_ID = %s",
            (str(person_ref).upper(),),
        )
    row = cur.fetchone()
    if row is None:
        raise NotFound("Person not found.", "person_not_found")
    return row


def _registration_dict(row):
    row = dict(row)
    events = _event_list(row.pop("event_csv"))
    row["guardian_consent"] = bool(row["guardian_consent"])
    row["events"] = events
    return row


def _registration_row(cur, competition_id, registrant_no):
    cur.execute(
        REGISTRATION_SELECT
        + " WHERE reg.Competition_ID = %s AND reg.Registrant_No = %s",
        (competition_id, int(registrant_no)),
    )
    row = cur.fetchone()
    if row is None:
        raise NotFound("Registration not found.", "registration_not_found")
    return _registration_dict(row)


def _raise_write_error(exc):
    code = exc.args[0] if exc.args else None
    message = exc.args[1] if len(exc.args) > 1 else ""
    if code == 1062:
        raise Conflict("That value already exists.", "duplicate")
    if code in (1451, 1452):
        raise Conflict("This record is still in use by other data.", "reference_violation")
    if code == 1644:
        raise Conflict(
            message or "This change is not allowed.", "constraint_violation"
        )
    if code in (3819, 4025):
        raise BadInput(message or "Invalid value.", "invalid_value")
    if code in (1264, 1406, 1292):
        raise BadInput(message or "Value out of range.", "invalid_value")
    raise


# --- reads: search ---------------------------------------------------------


def search_all(q: str, limit: int = 5) -> dict:
    needle = (q or "").strip()
    if not needle:
        raise BadInput("Enter something to search for.", "empty_query")
    if len(needle) > 60:
        raise BadInput("Search text is too long (60 characters max).", "query_too_long")

    limit = int(limit)
    contains = _like_contains(needle)
    prefix = _like_prefix(needle)

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT c.Competition_ID AS competition_id,
                   c.Name AS name,
                   c.City AS city,
                   c.Country_ID AS country_id,
                   c.Start_Date AS start_date
              FROM competitions c
             WHERE c.Name LIKE %s ESCAPE '!'
                OR c.City LIKE %s ESCAPE '!'
                OR c.Venue_Name LIKE %s ESCAPE '!'
             ORDER BY c.Start_Date DESC, c.Competition_ID ASC
             LIMIT %s
            """,
            (contains, contains, contains, limit),
        )
        competitions = cur.fetchall()

        cur.execute(
            """
            SELECT p.Person_No AS person_no,
                   p.WCA_ID AS wca_id,
                   p.Romanized_Name AS name,
                   p.Country_ID AS country_id
              FROM persons p
             WHERE p.Romanized_Name LIKE %s ESCAPE '!'
                OR p.Local_Name LIKE %s ESCAPE '!'
                OR (p.WCA_ID IS NOT NULL AND p.WCA_ID LIKE %s ESCAPE '!')
             ORDER BY LOWER(p.Romanized_Name) ASC, p.Person_No ASC
             LIMIT %s
            """,
            (contains, contains, prefix, limit),
        )
        persons = cur.fetchall()

    return to_jsonable({"competitions": competitions, "persons": persons})


# --- reads: competitions ---------------------------------------------------


def _competition_filters(
    q=None,
    country_id=None,
    continent_id=None,
    year=None,
    status=None,
    event_id=None,
):
    where, params = [], []
    if q:
        pattern = _like_contains(q)
        where.append(
            "(c.Name LIKE %s ESCAPE '!' OR c.City LIKE %s ESCAPE '!'"
            " OR c.Venue_Name LIKE %s ESCAPE '!')"
        )
        params += [pattern, pattern, pattern]
    if country_id:
        where.append("c.Country_ID = %s")
        params.append(country_id)
    if continent_id:
        where.append("co.Continent_ID = %s")
        params.append(continent_id)
    if year:
        where.append("YEAR(c.Start_Date) = %s")
        params.append(int(year))
    if status:
        where.append(f"({STATUS_SQL}) = %s")
        params.append(status)
    if event_id:
        where.append(
            "EXISTS (SELECT 1 FROM rounds rx"
            " WHERE rx.Competition_ID = c.Competition_ID AND rx.Event_ID = %s)"
        )
        params.append(event_id)
    return (" WHERE " + " AND ".join(where)) if where else "", params


def list_competitions(
    q: Optional[str] = None,
    country_id: Optional[str] = None,
    continent_id: Optional[str] = None,
    year: Optional[int] = None,
    status: Optional[str] = None,
    event_id: Optional[str] = None,
    sort: str = "date_desc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    sort = _checked_sort(COMPETITION_SORTS, sort, "date_desc")
    page, page_size, offset = _paging(page, page_size)
    where_sql, params = _competition_filters(
        q, country_id, continent_id, year, status, event_id
    )

    with db.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS total {COMPETITION_FROM} {where_sql}", params
        )
        total = int(cur.fetchone()["total"])

        cur.execute(
            f"""
            SELECT c.Competition_ID AS competition_id,
                   c.Name AS name,
                   c.City AS city,
                   c.Country_ID AS country_id,
                   co.Name AS country_name,
                   co.Continent_ID AS continent_id,
                   c.Start_Date AS start_date,
                   c.End_Date AS end_date,
                   {STATUS_SQL} AS status,
                   c.Competitor_Limit AS competitor_limit,
                   COALESCE(reg.cnt, 0) AS registered_count,
                   c.Main_Event_ID AS main_event_id,
                   (SELECT MIN(ct.Championship_Type) FROM championship_types ct
                     WHERE ct.Competition_ID = c.Competition_ID) AS championship_type
            {COMPETITION_FROM}
            {where_sql}
             ORDER BY {COMPETITION_SORT_SQL[sort]}
             LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        items = cur.fetchall()

    return to_jsonable(
        {"items": items, "total": total, "page": page, "page_size": page_size}
    )


def get_competition(competition_id: str) -> dict:
    with db.cursor() as cur:
        cur.execute(
            f"""
            SELECT c.Competition_ID AS competition_id,
                   c.Name AS name,
                   c.City AS city,
                   c.Country_ID AS country_id,
                   co.Name AS country_name,
                   co.Continent_ID AS continent_id,
                   c.Start_Date AS start_date,
                   c.End_Date AS end_date,
                   {STATUS_SQL} AS status,
                   c.Competitor_Limit AS competitor_limit,
                   COALESCE(reg.cnt, 0) AS registered_count,
                   c.Main_Event_ID AS main_event_id,
                   (SELECT MIN(ct.Championship_Type) FROM championship_types ct
                     WHERE ct.Competition_ID = c.Competition_ID) AS championship_type,
                   c.Short_Name AS short_name,
                   c.Venue_Name AS venue_name,
                   c.Street_Address AS street_address,
                   c.Venue_Details AS venue_details,
                   c.Latitude AS latitude,
                   c.Longitude AS longitude,
                   c.Website AS website,
                   c.Opens_At AS opens_at,
                   c.Closes_At AS closes_at,
                   c.Amount AS amount,
                   c.Currency_Code AS currency_code,
                   c.Refund_Policy_Percent AS refund_policy_percent,
                   c.Announced_At AS announced_at,
                   c.Cancelled_At AS cancelled_at,
                   c.Results_Posted_At AS results_posted_at
            {COMPETITION_FROM}
             WHERE c.Competition_ID = %s
            """,
            (competition_id,),
        )
        detail = cur.fetchone()
        if detail is None:
            raise NotFound("Competition not found.", "competition_not_found")

        cur.execute(
            """
            SELECT r.Event_ID AS event_id,
                   e.Event_Name AS event_name,
                   e.Result_Kind AS result_kind,
                   r.Round_Number AS round_number,
                   r.Format_ID AS format_id,
                   f.Format_Name AS format_name,
                   r.Per_Attempt AS per_attempt,
                   r.Cutoff_Attempts AS cutoff_attempts,
                   r.Cutoff_Value AS cutoff_value,
                   r.Adv_Type AS adv_type,
                   r.Adv_Level AS adv_level,
                   r.Is_Dual AS is_dual,
                   r.Is_Head_to_Head AS is_head_to_head,
                   r.Last_Day AS last_day
              FROM rounds r
              JOIN events e ON e.Event_ID = r.Event_ID
              JOIN formats f ON f.Format_ID = r.Format_ID
             WHERE r.Competition_ID = %s
             ORDER BY e.Display_Rank ASC, r.Event_ID ASC, r.Round_Number ASC
            """,
            (competition_id,),
        )
        events = []
        by_event = {}
        for row in cur.fetchall():
            event_id = row["event_id"]
            if event_id not in by_event:
                entry = {
                    "event_id": event_id,
                    "event_name": row["event_name"],
                    "result_kind": row["result_kind"],
                    "rounds": [],
                }
                by_event[event_id] = entry
                events.append(entry)
            by_event[event_id]["rounds"].append(
                {
                    "round_number": row["round_number"],
                    "format_id": row["format_id"],
                    "format_name": row["format_name"],
                    "per_attempt": row["per_attempt"],
                    "cutoff_attempts": row["cutoff_attempts"],
                    "cutoff_value": row["cutoff_value"],
                    "adv_type": row["adv_type"],
                    "adv_level": row["adv_level"],
                    "is_dual": bool(row["is_dual"]),
                    "is_head_to_head": bool(row["is_head_to_head"]),
                    "last_day": row["last_day"],
                }
            )

        cur.execute(
            """
            SELECT p.Person_No AS person_no,
                   p.Romanized_Name AS name,
                   p.WCA_ID AS wca_id
              FROM competition_delegates cd
              JOIN persons p ON p.Person_No = cd.Person_No
             WHERE cd.Competition_ID = %s
             ORDER BY LOWER(p.Romanized_Name) ASC, p.Person_No ASC
            """,
            (competition_id,),
        )
        delegates = cur.fetchall()

        cur.execute(
            """
            SELECT p.Person_No AS person_no,
                   p.Romanized_Name AS name,
                   p.WCA_ID AS wca_id
              FROM competition_organizers org
              JOIN persons p ON p.Person_No = org.Person_No
             WHERE org.Competition_ID = %s
             ORDER BY LOWER(p.Romanized_Name) ASC, p.Person_No ASC
            """,
            (competition_id,),
        )
        organizers = cur.fetchall()

        cur.execute(
            """
            SELECT r.Event_ID AS event_id,
                   e.Event_Name AS event_name,
                   r.Position AS position,
                   r.Person_No AS person_no,
                   p.Romanized_Name AS name,
                   p.WCA_ID AS wca_id,
                   r.Country_ID AS country_id,
                   r.Best AS best,
                   r.Average AS average,
                   r.Single_Record AS single_record,
                   r.Average_Record AS average_record
              FROM results r
              JOIN events e ON e.Event_ID = r.Event_ID
              JOIN persons p ON p.Person_No = r.Person_No
             WHERE r.Competition_ID = %s
               AND r.Position BETWEEN 1 AND 3
               AND NOT EXISTS (
                     SELECT 1 FROM rounds r2
                      WHERE r2.Competition_ID = r.Competition_ID
                        AND r2.Event_ID = r.Event_ID
                        AND r2.Round_Number > r.Round_Number)
             ORDER BY e.Display_Rank ASC, r.Event_ID ASC, r.Position ASC
            """,
            (competition_id,),
        )
        podiums = cur.fetchall()

    detail = dict(detail)
    detail["events"] = events
    detail["delegates"] = delegates
    detail["organizers"] = organizers
    detail["podiums"] = podiums
    return to_jsonable(detail)


def list_competition_results(
    competition_id: str,
    event_id: Optional[str] = None,
    round_number: Optional[int] = None,
    tab: str = "podiums",
    sort: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    if tab not in ("podiums", "all", "by_person"):
        raise BadInput(f"Unknown results tab '{tab}'.", "invalid_tab")
    page, page_size, offset = _paging(page, page_size)
    _checked_sort(RESULT_SORTS, sort, "position")

    where = ["r.Competition_ID = %s"]
    params = [competition_id]
    if event_id:
        where.append("r.Event_ID = %s")
        params.append(event_id)
    if round_number is not None:
        where.append("r.Round_Number = %s")
        params.append(int(round_number))
    if tab == "podiums":
        where.append("r.Position BETWEEN 1 AND 3")
        where.append(
            "NOT EXISTS (SELECT 1 FROM rounds r2"
            " WHERE r2.Competition_ID = r.Competition_ID"
            " AND r2.Event_ID = r.Event_ID"
            " AND r2.Round_Number > r.Round_Number)"
        )
    where_sql = " WHERE " + " AND ".join(where)
    order_sql = RESULT_ORDER_SQL["by_person" if tab == "by_person" else (sort or "position")]

    with db.cursor() as cur:
        _competition_exists(cur, competition_id)

        cur.execute(
            f"""
            SELECT COUNT(*) AS total
              FROM results r
              JOIN persons p ON p.Person_No = r.Person_No
              JOIN events e ON e.Event_ID = r.Event_ID
            {where_sql}
            """,
            params,
        )
        total = int(cur.fetchone()["total"])

        cur.execute(
            f"""
            SELECT CAST(r.Result_ID AS CHAR) AS result_id,
                   r.Event_ID AS event_id,
                   r.Round_Number AS round_number,
                   r.Position AS position,
                   r.Person_No AS person_no,
                   p.Romanized_Name AS name,
                   p.WCA_ID AS wca_id,
                   r.Country_ID AS country_id,
                   r.Best AS best,
                   r.Average AS average,
                   r.Single_Record AS single_record,
                   r.Average_Record AS average_record,
                   (SELECT GROUP_CONCAT(a.Value ORDER BY a.Attempt_No SEPARATOR ',')
                      FROM attempts a WHERE a.Result_ID = r.Result_ID) AS solve_csv
              FROM results r
              JOIN persons p ON p.Person_No = r.Person_No
              JOIN events e ON e.Event_ID = r.Event_ID
            {where_sql}
             ORDER BY {order_sql}
             LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        items = []
        for row in cur.fetchall():
            row = dict(row)
            row["solves"] = _solves(row.pop("solve_csv"))
            items.append(row)

    return to_jsonable(
        {"items": items, "total": total, "page": page, "page_size": page_size}
    )


# --- reads: persons --------------------------------------------------------


def _person_filters(q=None, country_id=None):
    where, params = [], []
    if country_id:
        where.append("p.Country_ID = %s")
        params.append(country_id)
    if q:
        pattern = _like_contains(q)
        where.append(
            "(p.Romanized_Name LIKE %s ESCAPE '!' OR p.Local_Name LIKE %s ESCAPE '!')"
        )
        params += [pattern, pattern]
    return (" WHERE " + " AND ".join(where)) if where else "", params


def _person_stats_sql(person_filter):
    return f"""
      SELECT COUNT(DISTINCT r.Competition_ID) AS competitions_count,
             CAST(COALESCE(SUM(
               CASE WHEN fr.Final = r.Round_Number AND r.Position BETWEEN 1 AND 3
                    THEN 1 ELSE 0 END), 0) AS SIGNED) AS podiums_count
        FROM results r
        LEFT JOIN ({FINAL_ROUNDS}) fr
          ON fr.Competition_ID = r.Competition_ID AND fr.Event_ID = r.Event_ID
       WHERE {person_filter}
    """


def list_persons(
    q: Optional[str] = None,
    country_id: Optional[str] = None,
    sort: str = "name",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    sort = _checked_sort(PERSON_SORTS, sort, "name")
    page, page_size, offset = _paging(page, page_size)
    where_sql, params = _person_filters(q, country_id)

    with db.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM persons p {where_sql}", params)
        total = int(cur.fetchone()["total"])

        cur.execute(
            f"""
            SELECT p.Person_No AS person_no,
                   p.WCA_ID AS wca_id,
                   p.Romanized_Name AS name,
                   p.Country_ID AS country_id,
                   co.Name AS country_name,
                   COUNT(DISTINCT r.Competition_ID) AS competitions_count,
                   CAST(COALESCE(SUM(
                     CASE WHEN fr.Final = r.Round_Number
                               AND r.Position BETWEEN 1 AND 3
                          THEN 1 ELSE 0 END), 0) AS SIGNED) AS podiums_count
              FROM persons p
              JOIN countries co ON co.Country_ID = p.Country_ID
              LEFT JOIN results r ON r.Person_No = p.Person_No
              LEFT JOIN ({FINAL_ROUNDS}) fr
                ON fr.Competition_ID = r.Competition_ID AND fr.Event_ID = r.Event_ID
            {where_sql}
             GROUP BY p.Person_No, p.WCA_ID, p.Romanized_Name, p.Country_ID, co.Name
             ORDER BY {PERSON_SORT_SQL[sort]}
             LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        items = cur.fetchall()

    return to_jsonable(
        {"items": items, "total": total, "page": page, "page_size": page_size}
    )


def _personal_records(cur, person_no):
    cur.execute(
        """
        SELECT pr.Event_ID AS event_id,
               e.Event_Name AS event_name,
               pr.best AS best,
               pr.average AS average,
               (SELECT 1 + COUNT(DISTINCT r2.Person_No)
                  FROM results r2
                 WHERE r2.Event_ID = pr.Event_ID
                   AND r2.Best > 0 AND r2.Best < pr.best) AS world_rank,
               (SELECT 1 + COUNT(DISTINCT r2.Person_No)
                  FROM results r2
                  JOIN countries c2 ON c2.Country_ID = r2.Country_ID
                 WHERE r2.Event_ID = pr.Event_ID
                   AND r2.Best > 0 AND r2.Best < pr.best
                   AND c2.Continent_ID = pc.Continent_ID) AS continental_rank,
               (SELECT 1 + COUNT(DISTINCT r2.Person_No)
                  FROM results r2
                 WHERE r2.Event_ID = pr.Event_ID
                   AND r2.Best > 0 AND r2.Best < pr.best
                   AND r2.Country_ID = p.Country_ID) AS national_rank
          FROM (
            SELECT Event_ID,
                   MIN(CASE WHEN Best > 0 THEN Best END) AS best,
                   MIN(CASE WHEN Average > 0 THEN Average END) AS average
              FROM results
             WHERE Person_No = %s
             GROUP BY Event_ID
          ) pr
          JOIN events e ON e.Event_ID = pr.Event_ID
          JOIN persons p ON p.Person_No = %s
          JOIN countries pc ON pc.Country_ID = p.Country_ID
         WHERE pr.best IS NOT NULL
         ORDER BY e.Display_Rank ASC
        """,
        (person_no, person_no),
    )
    return cur.fetchall()


def get_person(person_ref: Union[int, str]) -> dict:
    with db.cursor() as cur:
        person = _resolve_person(cur, person_ref)
        person_no = person["Person_No"]

        cur.execute(
            """
            SELECT p.Person_No AS person_no,
                   p.WCA_ID AS wca_id,
                   p.Romanized_Name AS name,
                   p.Local_Name AS local_name,
                   p.Gender AS gender,
                   p.Country_ID AS country_id,
                   co.Name AS country_name,
                   p.Since_Date AS since_date,
                   d.Delegate_Status AS delegate_status
              FROM persons p
              JOIN countries co ON co.Country_ID = p.Country_ID
              LEFT JOIN delegate d ON d.Person_No = p.Person_No
             WHERE p.Person_No = %s
            """,
            (person_no,),
        )
        detail = cur.fetchone()

        cur.execute(
            _person_stats_sql("r.Person_No = %s"),
            (person_no,),
        )
        stats = cur.fetchone()

        records = _personal_records(cur, person_no)

    detail = dict(detail)
    detail["competitions_count"] = int(stats["competitions_count"])
    detail["podiums_count"] = int(stats["podiums_count"])
    detail["personal_records"] = records
    return to_jsonable(detail)


def list_person_results(
    person_ref: Union[int, str],
    event_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size, offset = _paging(page, page_size)

    with db.cursor() as cur:
        person = _resolve_person(cur, person_ref)
        person_no = person["Person_No"]

        where = ["r.Person_No = %s"]
        params = [person_no]
        if event_id:
            where.append("r.Event_ID = %s")
            params.append(event_id)
        where_sql = " WHERE " + " AND ".join(where)

        cur.execute(f"SELECT COUNT(*) AS total FROM results r {where_sql}", params)
        total = int(cur.fetchone()["total"])

        cur.execute(
            f"""
            SELECT CAST(r.Result_ID AS CHAR) AS result_id,
                   r.Competition_ID AS competition_id,
                   c.Name AS competition_name,
                   r.Event_ID AS event_id,
                   r.Round_Number AS round_number,
                   r.Position AS position,
                   r.Best AS best,
                   r.Average AS average,
                   r.Single_Record AS single_record,
                   r.Average_Record AS average_record,
                   r.Country_ID AS country_id,
                   (SELECT GROUP_CONCAT(a.Value ORDER BY a.Attempt_No SEPARATOR ',')
                      FROM attempts a WHERE a.Result_ID = r.Result_ID) AS solve_csv
              FROM results r
              JOIN competitions c ON c.Competition_ID = r.Competition_ID
            {where_sql}
             ORDER BY c.Name ASC, r.Event_ID ASC, r.Round_Number ASC
             LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        items = []
        for row in cur.fetchall():
            row = dict(row)
            row["solves"] = _solves(row.pop("solve_csv"))
            items.append(row)

    return to_jsonable(
        {"items": items, "total": total, "page": page, "page_size": page_size}
    )


# --- reads: rankings -------------------------------------------------------


def list_rankings(
    event_id: str,
    kind: str = "single",
    country_id: Optional[str] = None,
    continent_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    page, page_size, offset = _paging(page, page_size)

    with db.cursor() as cur:
        cur.execute(
            "SELECT Status FROM events WHERE Event_ID = %s", (event_id,)
        )
        event = cur.fetchone()
        if event is None:
            raise NotFound("Event not found.", "event_not_found")
        if event["Status"] != "official":
            raise BadInput("This event is retired.", "event_retired")
        if kind not in ("single", "average"):
            raise BadInput(
                "Rankings type must be 'single' or 'average'.", "invalid_kind"
            )

        field = "Best" if kind == "single" else "Average"
        filter_sql, filter_params = [], []
        if country_id:
            filter_sql.append("f.Country_ID = %s")
            filter_params.append(country_id)
        if continent_id:
            filter_sql.append("f.Continent_ID = %s")
            filter_params.append(continent_id)
        filter_where = (" AND " + " AND ".join(filter_sql)) if filter_sql else ""

        cte = f"""
        WITH best AS (
          SELECT r.Person_No AS Person_No,
                 r.Best AS Best,
                 r.Average AS Average,
                 r.Competition_ID AS Competition_ID,
                 r.Country_ID AS Country_ID,
                 co.Continent_ID AS Continent_ID,
                 ROW_NUMBER() OVER (
                   PARTITION BY r.Person_No ORDER BY r.{field}, r.Result_ID
                 ) AS rn
            FROM results r
            JOIN countries co ON co.Country_ID = r.Country_ID
           WHERE r.Event_ID = %s AND r.{field} > 0
        ),
        filtered AS (
          SELECT * FROM best f WHERE rn = 1{filter_where}
        )
        """
        base_params = [event_id] + filter_params

        cur.execute(
            cte + "SELECT COUNT(*) AS total FROM filtered", base_params
        )
        total = int(cur.fetchone()["total"])

        cur.execute(
            cte
            + f"""
            , ranked AS (
              SELECT f.*,
                     RANK() OVER (ORDER BY f.{field}) AS rnk,
                     RANK() OVER (
                       PARTITION BY f.Continent_ID ORDER BY f.{field}
                     ) AS cont_rank,
                     RANK() OVER (
                       PARTITION BY f.Country_ID ORDER BY f.{field}
                     ) AS nat_rank
                FROM filtered f
            )
            SELECT ranked.rnk AS `rank`,
                   ranked.Person_No AS person_no,
                   p.Romanized_Name AS name,
                   p.WCA_ID AS wca_id,
                   ranked.Country_ID AS country_id,
                   co.Name AS country_name,
                   ranked.Best AS best,
                   ranked.Average AS average,
                   ranked.Competition_ID AS competition_id,
                   c.Name AS competition_name,
                   ranked.cont_rank AS continental_rank,
                   ranked.nat_rank AS national_rank
              FROM ranked
              JOIN persons p ON p.Person_No = ranked.Person_No
              JOIN countries co ON co.Country_ID = ranked.Country_ID
              JOIN competitions c ON c.Competition_ID = ranked.Competition_ID
             ORDER BY ranked.{field} ASC, ranked.Person_No ASC
             LIMIT %s OFFSET %s
            """,
            base_params + [page_size, offset],
        )
        items = cur.fetchall()

    return to_jsonable(
        {"items": items, "total": total, "page": page, "page_size": page_size}
    )


# --- reads: lookups and stats ---------------------------------------------


def list_countries() -> list:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT c.Country_ID AS country_id,
                   c.ISO2 AS iso2,
                   c.Name AS name,
                   c.Continent_ID AS continent_id,
                   ct.Name AS continent_name
              FROM countries c
              JOIN continents ct ON ct.Continent_ID = c.Continent_ID
             ORDER BY LOWER(c.Name) ASC, c.Country_ID ASC
            """
        )
        rows = cur.fetchall()
    return to_jsonable(rows)


def get_country(country_id: str) -> dict:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT c.Country_ID AS country_id,
                   c.ISO2 AS iso2,
                   c.Name AS name,
                   c.Continent_ID AS continent_id,
                   ct.Name AS continent_name
              FROM countries c
              JOIN continents ct ON ct.Continent_ID = c.Continent_ID
             WHERE c.Country_ID = %s
            """,
            (country_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise NotFound("Country not found.", "country_not_found")
    return to_jsonable(row)


def list_events(include_retired: bool = False) -> list:
    where = "" if include_retired else " WHERE Status = 'official'"
    with db.cursor() as cur:
        cur.execute(
            f"""
            SELECT Event_ID AS event_id,
                   Event_Name AS event_name,
                   Result_Kind AS result_kind,
                   Status AS status
              FROM events
            {where}
             ORDER BY Display_Rank ASC
            """
        )
        rows = cur.fetchall()
    return to_jsonable(rows)


def list_registrations(
    competition_id: str,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    page, page_size, offset = _paging(page, page_size)
    where = ["reg.Competition_ID = %s"]
    params = [competition_id]
    if status:
        where.append("reg.Status = %s")
        params.append(status)
    where_sql = " WHERE " + " AND ".join(where)

    with db.cursor() as cur:
        _competition_exists(cur, competition_id)

        cur.execute(
            f"SELECT COUNT(*) AS total FROM registrations reg {where_sql}", params
        )
        total = int(cur.fetchone()["total"])

        cur.execute(
            REGISTRATION_SELECT
            + f"{where_sql} ORDER BY reg.Registrant_No ASC LIMIT %s OFFSET %s",
            params + [page_size, offset],
        )
        items = [_registration_dict(row) for row in cur.fetchall()]

    return to_jsonable(
        {"items": items, "total": total, "page": page, "page_size": page_size}
    )


def get_registration(competition_id: str, registrant_no: int) -> dict:
    with db.cursor() as cur:
        return to_jsonable(_registration_row(cur, competition_id, registrant_no))


def stats_medals() -> list:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT r.Country_ID AS country_id,
                   co.Name AS country_name,
                   co.Continent_ID AS continent_id,
                   CAST(SUM(CASE WHEN r.Position = 1 THEN 1 ELSE 0 END) AS SIGNED) AS gold,
                   CAST(SUM(CASE WHEN r.Position = 2 THEN 1 ELSE 0 END) AS SIGNED) AS silver,
                   CAST(SUM(CASE WHEN r.Position = 3 THEN 1 ELSE 0 END) AS SIGNED) AS bronze,
                   CAST(COUNT(*) AS SIGNED) AS total
              FROM results r
              JOIN countries co ON co.Country_ID = r.Country_ID
             WHERE r.Position BETWEEN 1 AND 3
               AND NOT EXISTS (
                     SELECT 1 FROM rounds r2
                      WHERE r2.Competition_ID = r.Competition_ID
                        AND r2.Event_ID = r.Event_ID
                        AND r2.Round_Number > r.Round_Number)
             GROUP BY r.Country_ID, co.Name, co.Continent_ID
             ORDER BY gold DESC, silver DESC, bronze DESC, LOWER(co.Name) ASC
            """
        )
        rows = cur.fetchall()
    return to_jsonable(rows)


def stats_competitions_by_country_year(
    year_from: Optional[int] = None, year_to: Optional[int] = None
) -> list:
    where, params = [], []
    if year_from:
        where.append("YEAR(c.Start_Date) >= %s")
        params.append(int(year_from))
    if year_to:
        where.append("YEAR(c.Start_Date) <= %s")
        params.append(int(year_to))
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    with db.cursor() as cur:
        cur.execute(
            f"""
            SELECT c.Country_ID AS country_id,
                   co.Name AS country_name,
                   YEAR(c.Start_Date) AS year,
                   CAST(COUNT(*) AS SIGNED) AS competition_count
              FROM competitions c
              JOIN countries co ON co.Country_ID = c.Country_ID
            {where_sql}
             GROUP BY c.Country_ID, co.Name, YEAR(c.Start_Date)
             ORDER BY year DESC, competition_count DESC, LOWER(co.Name) ASC
            """,
            params,
        )
        rows = cur.fetchall()
    return to_jsonable(rows)


def stats_records() -> list:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT event_id, event_name, kind, record_code, cnt AS count
              FROM (
                SELECT r.Event_ID AS event_id,
                       e.Event_Name AS event_name,
                       'single' AS kind,
                       r.Single_Record AS record_code,
                       CAST(COUNT(*) AS SIGNED) AS cnt,
                       e.Display_Rank AS display_rank
                  FROM results r
                  JOIN events e ON e.Event_ID = r.Event_ID
                 WHERE r.Single_Record IS NOT NULL
                 GROUP BY r.Event_ID, e.Event_Name, r.Single_Record, e.Display_Rank
                UNION ALL
                SELECT r.Event_ID AS event_id,
                       e.Event_Name AS event_name,
                       'average' AS kind,
                       r.Average_Record AS record_code,
                       CAST(COUNT(*) AS SIGNED) AS cnt,
                       e.Display_Rank AS display_rank
                  FROM results r
                  JOIN events e ON e.Event_ID = r.Event_ID
                 WHERE r.Average_Record IS NOT NULL
                 GROUP BY r.Event_ID, e.Event_Name, r.Average_Record, e.Display_Rank
              ) t
             ORDER BY display_rank ASC, kind ASC, record_code ASC
            """
        )
        rows = cur.fetchall()
    return to_jsonable(rows)


# --- writes ----------------------------------------------------------------


def create_registration(
    competition_id: str, person_no: int, event_ids: list, guests: int = 0
) -> dict:
    wanted = list(dict.fromkeys(event_ids))
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT Competitor_Limit AS competitor_limit,
                       (Cancelled_At IS NOT NULL
                        OR (Opens_At IS NOT NULL AND NOW() < Opens_At)
                        OR (Closes_At IS NOT NULL AND NOW() > Closes_At)) AS closed
                  FROM competitions
                 WHERE Competition_ID = %s
                """,
                (competition_id,),
            )
            comp = cur.fetchone()
            if comp is None:
                raise NotFound("Competition not found.", "competition_not_found")
            if comp["closed"]:
                raise Conflict(
                    "Registration for this competition is closed.",
                    "registration_closed",
                )

            cur.execute(
                "SELECT Person_No FROM persons WHERE Person_No = %s",
                (int(person_no),),
            )
            if cur.fetchone() is None:
                raise NotFound("Person not found.", "person_not_found")

            if not wanted:
                raise BadInput("Select at least one event.", "no_events")

            placeholders = ", ".join(["%s"] * len(wanted))
            cur.execute(
                f"SELECT Event_ID FROM events WHERE Event_ID IN ({placeholders})",
                wanted,
            )
            known = {row["Event_ID"] for row in cur.fetchall()}
            unknown = [event_id for event_id in wanted if event_id not in known]
            if unknown:
                raise BadInput(
                    f"Unknown event '{unknown[0]}'.", "unknown_event"
                )

            cur.execute(
                "SELECT Event_ID FROM rounds WHERE Competition_ID = %s",
                (competition_id,),
            )
            offered = {row["Event_ID"] for row in cur.fetchall()}
            missing = [event_id for event_id in wanted if event_id not in offered]
            if missing:
                cur.execute(
                    "SELECT Event_Name FROM events WHERE Event_ID = %s",
                    (missing[0],),
                )
                name = cur.fetchone()["Event_Name"]
                raise BadInput(
                    f"This competition does not offer {name}.", "event_not_offered"
                )

            cur.execute(
                "SELECT 1 AS found FROM registrations"
                " WHERE Competition_ID = %s AND Person_No = %s",
                (competition_id, int(person_no)),
            )
            if cur.fetchone() is not None:
                raise Conflict(
                    "This person is already registered.", "already_registered"
                )

            cur.execute(
                "SELECT COUNT(*) AS n FROM registrations"
                " WHERE Competition_ID = %s AND Status = 'accepted'",
                (competition_id,),
            )
            accepted = int(cur.fetchone()["n"])
            limit = comp["competitor_limit"]
            status = (
                "waiting_list"
                if limit is not None and accepted >= int(limit)
                else "accepted"
            )

            cur.execute(
                "SELECT COALESCE(MAX(Registrant_No), 0) + 1 AS next_no"
                " FROM registrations WHERE Competition_ID = %s",
                (competition_id,),
            )
            registrant_no = int(cur.fetchone()["next_no"])

            cur.execute(
                """
                INSERT INTO registrations
                  (Competition_ID, Registrant_No, Person_No, Status,
                   Registered_At, Guests, Guardian_Consent)
                VALUES (%s, %s, %s, %s, NOW(), %s, 0)
                """,
                (competition_id, registrant_no, int(person_no), status, int(guests)),
            )
            for event_id in wanted:
                cur.execute(
                    "INSERT INTO selects (Competition_ID, Registrant_No, Event_ID)"
                    " VALUES (%s, %s, %s)",
                    (competition_id, registrant_no, event_id),
                )

            return to_jsonable(
                _registration_row(cur, competition_id, registrant_no)
            )
    except pymysql.err.MySQLError as exc:
        _raise_write_error(exc)


def set_registration_status(
    competition_id: str, registrant_no: int, status: str
) -> dict:
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT Competitor_Limit AS competitor_limit FROM competitions"
                " WHERE Competition_ID = %s",
                (competition_id,),
            )
            comp = cur.fetchone()
            if comp is None:
                raise NotFound("Competition not found.", "competition_not_found")

            cur.execute(
                "SELECT Status FROM registrations"
                " WHERE Competition_ID = %s AND Registrant_No = %s",
                (competition_id, int(registrant_no)),
            )
            current = cur.fetchone()
            if current is None:
                raise NotFound("Registration not found.", "registration_not_found")

            if status not in (
                "accepted",
                "waiting_list",
                "pending",
                "cancelled",
                "rejected",
            ):
                raise BadInput(f"Unknown status '{status}'.", "invalid_status")
            if current["Status"] == status:
                raise BadInput(
                    "This registration already has that status.", "status_unchanged"
                )

            cur.execute(
                "UPDATE registrations SET Status = %s"
                " WHERE Competition_ID = %s AND Registrant_No = %s",
                (status, competition_id, int(registrant_no)),
            )

            promoted = None
            cur.execute(
                "SELECT COUNT(*) AS n FROM registrations"
                " WHERE Competition_ID = %s AND Status = 'accepted'",
                (competition_id,),
            )
            accepted = int(cur.fetchone()["n"])
            limit = comp["competitor_limit"]
            if limit is None or accepted < int(limit):
                cur.execute(
                    """
                    SELECT reg.Registrant_No AS registrant_no,
                           reg.Person_No AS person_no,
                           p.Romanized_Name AS name
                      FROM registrations reg
                      JOIN persons p ON p.Person_No = reg.Person_No
                     WHERE reg.Competition_ID = %s
                       AND reg.Status = 'waiting_list'
                       AND reg.Registrant_No <> %s
                     ORDER BY reg.Registered_At ASC, reg.Registrant_No ASC
                     LIMIT 1
                    """,
                    (competition_id, int(registrant_no)),
                )
                candidate = cur.fetchone()
                if candidate is not None:
                    cur.execute(
                        "UPDATE registrations SET Status = 'accepted'"
                        " WHERE Competition_ID = %s AND Registrant_No = %s",
                        (competition_id, candidate["registrant_no"]),
                    )
                    promoted = {
                        "registrant_no": candidate["registrant_no"],
                        "person_no": candidate["person_no"],
                        "name": candidate["name"],
                    }

            return to_jsonable(
                {
                    "registration": _registration_row(
                        cur, competition_id, registrant_no
                    ),
                    "promoted": promoted,
                }
            )
    except pymysql.err.MySQLError as exc:
        _raise_write_error(exc)


def delete_registration(competition_id: str, registrant_no: int) -> None:
    try:
        with db.cursor() as cur:
            _competition_exists(cur, competition_id)

            cur.execute(
                "SELECT Person_No FROM registrations"
                " WHERE Competition_ID = %s AND Registrant_No = %s",
                (competition_id, int(registrant_no)),
            )
            registration = cur.fetchone()
            if registration is None:
                raise NotFound("Registration not found.", "registration_not_found")

            cur.execute(
                "SELECT 1 AS found FROM results"
                " WHERE Competition_ID = %s AND Person_No = %s LIMIT 1",
                (competition_id, registration["Person_No"]),
            )
            if cur.fetchone() is not None:
                raise Conflict(
                    "Cannot delete this registration because the competitor "
                    "already has results in this competition.",
                    "registration_has_results",
                )

            cur.execute(
                "DELETE FROM registrations"
                " WHERE Competition_ID = %s AND Registrant_No = %s",
                (competition_id, int(registrant_no)),
            )
    except pymysql.err.MySQLError as exc:
        _raise_write_error(exc)


def update_person_country(person_ref: Union[int, str], country_id: str) -> dict:
    try:
        with db.cursor() as cur:
            person = _resolve_person(cur, person_ref)

            cur.execute(
                "SELECT Name FROM countries WHERE Country_ID = %s", (country_id,)
            )
            country = cur.fetchone()
            if country is None:
                raise NotFound("Country not found.", "country_not_found")

            if person["Country_ID"] == country_id:
                raise BadInput(
                    f"This person already represents {country['Name']}.",
                    "same_country",
                )

            if person["Since_Date"] is not None:
                cur.execute(
                    "SELECT (%s > DATE_SUB(CURDATE(), INTERVAL 1 YEAR)) AS recent",
                    (person["Since_Date"],),
                )
                if cur.fetchone()["recent"]:
                    since = person["Since_Date"].isoformat()
                    raise Conflict(
                        f"This person changed country on {since}; the 12-month "
                        "rule still applies.",
                        "country_change_too_recent",
                    )

            cur.execute(
                "UPDATE persons SET Country_ID = %s, Since_Date = CURDATE()"
                " WHERE Person_No = %s",
                (country_id, person["Person_No"]),
            )
            person_no = person["Person_No"]
    except pymysql.err.MySQLError as exc:
        _raise_write_error(exc)

    return get_person(person_no)
