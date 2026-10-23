import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from psycopg2.extras import execute_values

# Allow imports from src/
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from db_manager import get_db_cursor
from FRED.fred_client import fetch_fred_json


def clean_val(val):
    """Converts empty strings or literal '.' dots to None for SQL NULL."""
    if val in (None, "", "."):
        return None
    return val


def sync_unpacked_series_updates(cur, start_dt: datetime, end_dt: datetime):
    """Fetches series updates and inserts unpacked columns into fred.series_updates."""
    limit = 1000
    offset = 0
    total_staged = 0

    # Required format for series/updates: YYYYMMDDHhmm
    start_str = start_dt.strftime("%Y%m%d%H%M")
    end_str = end_dt.strftime("%Y%m%d%H%M")

    query = """
    INSERT INTO fred.series_updates (
        series_id,
        title,
        observation_start,
        observation_end,
        frequency,
        frequency_short,
        units,
        units_short,
        seasonal_adjustment,
        seasonal_adjustment_short,
        popularity,
        last_updated,
        realtime_start,
        realtime_end,
        notes,
        payload_hash
    )
    VALUES %s
    ON CONFLICT (series_id, payload_hash) DO NOTHING;
    """

    print(f"Syncing unpacked series updates [{start_str} to {end_str}]...")

    while True:
        params = {
            "start_time": start_str,
            "end_time": end_str,
            "filter_value": "macro",
            "limit": limit,
            "offset": offset,
        }

        payload = fetch_fred_json("series/updates", params=params)
        series_items = payload.get("seriess", [])

        if not series_items:
            break

        records = []
        for s in series_items:
            series_id = s.get("id")
            if not series_id:
                continue

            raw_str = json.dumps(s, sort_keys=True)
            payload_hash = hashlib.md5(raw_str.encode("utf-8")).hexdigest()

            records.append((
                series_id,
                s.get("title") or "Unknown",
                clean_val(s.get("observation_start")),
                clean_val(s.get("observation_end")),
                clean_val(s.get("frequency")),
                clean_val(s.get("frequency_short")),
                clean_val(s.get("units")),
                clean_val(s.get("units_short")),
                clean_val(s.get("seasonal_adjustment")),
                clean_val(s.get("seasonal_adjustment_short")),
                clean_val(s.get("popularity")),
                clean_val(s.get("last_updated")),
                clean_val(s.get("realtime_start")),
                clean_val(s.get("realtime_end")),
                clean_val(s.get("notes")),
                payload_hash
            ))

        execute_values(cur, query, records)
        batch_len = len(records)
        total_staged += batch_len

        print(f"  Inserted: {batch_len} records (offset={offset})")

        if batch_len < limit:
            break

        offset += limit

    print(f"[fred.series_updates] Done. Total records written: {total_staged}.")


def run_scheduled_job():
    """Daily schedule: look back over the last 48 hours."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=2)
    end_time = now

    with get_db_cursor(commit=True) as cur:
        sync_unpacked_series_updates(cur, start_time, end_time)


if __name__ == "__main__":
    run_scheduled_job()


# ==============================================================================
# BACKFILL FUNCTION (Raw 14-day chunks)
# ==============================================================================
# def run_backfill(start_date: date, end_date: date):
#     """Backfills raw series updates in 14-day chunks."""
#     print(f"Starting raw backfill: {start_date} to {end_date}...")
#     step = timedelta(days=14)
#     current_start = start_date
#
#     with get_db_cursor(commit=True) as cur:
#         while current_start <= end_date:
#             current_end = min(current_start + step - timedelta(days=1), end_date)
#             sync_raw_series_updates(cur, current_start, current_end)
#             current_start += step
#
#     print("Raw backfill completed.")


if __name__ == "__main__":
    run_scheduled_job()

    # To backfill raw payloads:
    # run_backfill(date(2026, 1, 1), date.today())