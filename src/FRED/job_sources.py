import sys
from pathlib import Path
from psycopg2.extras import execute_values

SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from db_manager import get_db_cursor
from FRED.fred_client import fetch_fred_json


def run_scheduled_job():
    print("Fetching FRED sources...")
    payload = fetch_fred_json("sources")
    sources = payload.get("sources", [])

    records = [
        (
            s["id"],
            s.get("realtime_start"),
            s.get("realtime_end"),
            s.get("name"),
            s.get("link"),
            s.get("notes"),
        )
        for s in sources
    ]

    query = """
    INSERT INTO fred.sources (id, realtime_start, realtime_end, name, link, notes)
    VALUES %s
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        link = EXCLUDED.link,
        notes = EXCLUDED.notes,
        realtime_start = EXCLUDED.realtime_start,
        realtime_end = EXCLUDED.realtime_end;
    """
    with get_db_cursor(commit=True) as cur:
        execute_values(cur, query, records)

    print(f"[fred.sources] Synced {len(records)} sources.")


if __name__ == "__main__":
    run_scheduled_job()