import sys
from pathlib import Path
from datetime import date, datetime, timedelta
from psycopg2.extras import execute_values

# Allow imports from src (db_manager)
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from db_manager import get_db_cursor
from FRED.fred_client import fetch_fred_json


def sync_releases_metadata(cur):
    """Upserts release definitions into fred.releases."""
    payload = fetch_fred_json("releases")
    releases = payload.get("releases", [])

    records = [
        (
            r["id"],
            r.get("realtime_start"),
            r.get("realtime_end"),
            r.get("name"),
            r.get("press_release"),
            r.get("link"),
            r.get("notes"),
        )
        for r in releases
    ]

    query = """
    INSERT INTO fred.releases (
        id, realtime_start, realtime_end, name, press_release, link, notes
    )
    VALUES %s
    ON CONFLICT (id) DO UPDATE SET
        realtime_start = EXCLUDED.realtime_start,
        realtime_end = EXCLUDED.realtime_end,
        name = EXCLUDED.name,
        press_release = EXCLUDED.press_release,
        link = EXCLUDED.link,
        notes = EXCLUDED.notes;
    """
    execute_values(cur, query, records)
    print(f"[fred.releases] Synced {len(records)} release definitions.")


def sync_release_dates_window(cur, min_date: date, max_date: date):
    """Paginates fred/releases/dates descending and stores dates in the given window."""
    limit = 1000
    offset = 0
    total_synced = 0
    stop_pagination = False

    query = """
    INSERT INTO fred.release_dates (release_id, date)
    VALUES %s
    ON CONFLICT (release_id, date) DO NOTHING;
    """

    print(f"Syncing release dates targeting window: {min_date} to {max_date}...")

    while not stop_pagination:
        params = {
            "limit": limit,
            "offset": offset,
            "order_by": "release_date",
            "sort_order": "desc",
            "include_release_dates_with_no_data": "true",
        }

        payload = fetch_fred_json("releases/dates", params=params)
        release_dates = payload.get("release_dates", [])

        if not release_dates:
            break

        batch_records = []
        for rd in release_dates:
            rd_date = datetime.strptime(rd["date"], "%Y-%m-%d").date()

            # Include only dates within our target boundary
            if min_date <= rd_date <= max_date:
                batch_records.append((rd["release_id"], rd["date"]))
            elif rd_date < min_date:
                # Because sort_order is desc, any earlier date means we've passed our window
                stop_pagination = True
                break

        if batch_records:
            execute_values(cur, query, batch_records)
            total_synced += len(batch_records)

        # Reached the end of FRED data
        if len(release_dates) < limit:
            break

        offset += limit

    print(f"[fred.release_dates] Synced {total_synced} dates in window [{min_date} to {max_date}].")


def run_scheduled_job():
    """Daily schedule: current_date - 1 to current_date + 14."""
    today = date.today()
    window_start = today - timedelta(days=1)
    window_end = today + timedelta(days=14)

    with get_db_cursor(commit=True) as cur:
        sync_releases_metadata(cur)
        sync_release_dates_window(cur, window_start, window_end)


# ==============================================================================
# BACKFILL FUNCTION (14-day chunks)
# ==============================================================================
# def run_backfill(start_date: date, end_date: date):
#     """Splits a historical range into 14-day chunks and backfills release dates."""
#     print(f"Starting backfill from {start_date} to {end_date}...")
#     current_start = start_date
#     step = timedelta(days=14)
#
#     with get_db_cursor(commit=True) as cur:
#         sync_releases_metadata(cur)
#
#         while current_start <= end_date:
#             current_end = min(current_start + step - timedelta(days=1), end_date)
#             sync_release_dates_window(cur, current_start, current_end)
#             current_start += step
#
#     print("Backfill completed successfully.")


if __name__ == "__main__":
    run_scheduled_job()

    # To backfill, comment out run_scheduled_job() and uncomment:
    # run_backfill(date(2024, 1, 1), date.today())