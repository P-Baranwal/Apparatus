"""DEV ONLY - delete before submission.

Builds src/mock_data/*.json from the delivered CSVs in data/ so the mock layer uses
real WCA-shaped values. Confidential columns (persons.Date_of_Birth, persons.Email,
delegate.WCA_Email) are dropped here, so they can never leak into the UI.

    uv run --no-project python scripts/make_mock_data.py
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data"
OUT = ROOT / "src" / "mock_data"

INT = "int"
FLOAT = "float"
BOOL = "bool"
STR = "str"

SPEC = {
    "continents": {"Continent_ID": STR, "Name": STR, "Record_Code": STR},
    "countries": {"Country_ID": STR, "ISO2": STR, "Name": STR, "Continent_ID": STR},
    "events": {
        "Event_ID": STR,
        "Event_Name": STR,
        "Display_Rank": INT,
        "Result_Kind": STR,
        "Status": STR,
    },
    "formats": {
        "Format_ID": STR,
        "Format_Name": STR,
        "Expected_Attempts": INT,
        "Sort_By": STR,
        "Trimmed_Per_Side": INT,
    },
    "championship_types": {"Competition_ID": STR, "Championship_Type": STR},
    "regions": {"Region_ID": INT, "Region_Name": STR, "Parent_Region_ID": INT},
    "teams": {"Team_ID": STR, "Team_Name": STR, "Kind": STR, "Contact_Email": STR},
    "persons": {
        "Person_No": INT,
        "WCA_ID": STR,
        "Romanized_Name": STR,
        "Local_Name": STR,
        "Gender": STR,
        "Country_ID": STR,
        "Since_Date": STR,
    },
    "previous_identities": {
        "Person_No": INT,
        "Old_Name": STR,
        "Old_Country_ID": STR,
        "Valid_Until": STR,
    },
    "delegate": {
        "Person_No": INT,
        "Delegate_Status": STR,
        "Appointed_On": STR,
        "Supervisor_Person_No": INT,
        "Region_ID": INT,
    },
    "member_of": {
        "Person_No": INT,
        "Team_ID": STR,
        "Role": STR,
        "Start_Date": STR,
        "End_Date": STR,
    },
    "competitions": {
        "Competition_ID": STR,
        "Name": STR,
        "Short_Name": STR,
        "Venue_Name": STR,
        "Street_Address": STR,
        "Venue_Details": STR,
        "City": STR,
        "Latitude": FLOAT,
        "Longitude": FLOAT,
        "Start_Date": STR,
        "End_Date": STR,
        "Opens_At": STR,
        "Closes_At": STR,
        "Amount": INT,
        "Currency_Code": STR,
        "Competitor_Limit": INT,
        "Refund_Policy_Percent": INT,
        "Website": STR,
        "Announced_At": STR,
        "Cancelled_At": STR,
        "Results_Posted_At": STR,
        "Country_ID": STR,
        "Main_Event_ID": STR,
    },
    "competition_delegates": {"Person_No": INT, "Competition_ID": STR},
    "competition_organizers": {"Person_No": INT, "Competition_ID": STR},
    "rounds": {
        "Competition_ID": STR,
        "Event_ID": STR,
        "Round_Number": INT,
        "Format_ID": STR,
        "Per_Attempt": INT,
        "Cutoff_Attempts": INT,
        "Cutoff_Value": INT,
        "Adv_Type": STR,
        "Adv_Level": INT,
        "Is_Dual": BOOL,
        "Is_Head_to_Head": BOOL,
        "Last_Day": STR,
    },
    "registrations": {
        "Competition_ID": STR,
        "Registrant_No": INT,
        "Person_No": INT,
        "Status": STR,
        "Registered_At": STR,
        "Guests": INT,
        "Guardian_Consent": BOOL,
    },
    "selects": {"Competition_ID": STR, "Registrant_No": INT, "Event_ID": STR},
    "results": {
        "Result_ID": STR,
        "Competition_ID": STR,
        "Event_ID": STR,
        "Round_Number": INT,
        "Person_No": INT,
        "Country_ID": STR,
        "Best": INT,
        "Average": INT,
        "Position": INT,
        "Single_Record": STR,
        "Average_Record": STR,
    },
    "attempts": {"Result_ID": STR, "Attempt_No": INT, "Value": INT},
}


def coerce(raw, kind):
    if raw == "":
        return None
    if kind == INT:
        return int(raw)
    if kind == FLOAT:
        return float(raw)
    if kind == BOOL:
        return raw == "1"
    return raw


def build(table, columns):
    with (SRC / f"{table}.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [
            {col: coerce(row[col], kind) for col, kind in columns.items()}
            for row in reader
        ]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for table, columns in SPEC.items():
        rows = build(table, columns)
        path = OUT / f"{table}.json"
        path.write_text(
            json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        print(f"{table:24} {len(rows):6} rows  {path.stat().st_size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
