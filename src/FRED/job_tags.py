import sys
from pathlib import Path
from psycopg2.extras import execute_values

SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from db_manager import get_db_cursor
from FRED.fred_client import fetch_fred_json


def run_scheduled_job():
    print("Fetching FRED tags...")
    limit = 1000
    offset = 0
    total_tags = 0

    query = """
    INSERT INTO fred.tags (name, group_id, notes, created, popularity, series_count)
    VALUES %s
    ON CONFLICT (name) DO UPDATE SET
        group_id = EXCLUDED.group_id,
        notes = EXCLUDED.notes,
        popularity = EXCLUDED.popularity,
        series_count = EXCLUDED.series_count;
    """

    with get_db_cursor(commit=True) as cur:
        while True:
            params = {
                "limit": limit,
                "offset": offset,
                "order_by": "series_count",
                "sort_order": "desc",
            }
            payload = fetch_fred_json("tags", params=params)
            tags = payload.get("tags", [])

            if not tags:
                break

            records = [
                (
                    t["name"],
                    t.get("group_id"),
                    t.get("notes"),
                    t.get("created"),
                    t.get("popularity"),
                    t.get("series_count"),
                )
                for t in tags
            ]

            execute_values(cur, query, records)
            batch_len = len(records)
            total_tags += batch_len

            if batch_len < limit:
                break

            offset += limit

    print(f"[fred.tags] Synced {total_tags} tags.")


if __name__ == "__main__":
    run_scheduled_job()