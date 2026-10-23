import sys
from pathlib import Path
from datetime import date, timedelta
from psycopg2.extras import execute_values

# Allow imports from src/
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from db_manager import get_db_cursor
from FRED.fred_client import fetch_fred_json

# Core risk-free benchmarks for discount curve & IV calculation
TARGET_SERIES = [
    "DGS1MO",  # DGS: Treasuries
    "DGS3MO",
    "DGS6MO",
    "DGS1",
    "SOFR"
]


def sync_series_rates(cur, series_id: str, start_date: date, end_date: date):
    """Paginates fred/series/observations for a given ticker and upserts into fred.series_rates."""
    limit = 1000
    offset = 0
    total_synced = 0

    query = """
    INSERT INTO fred.series_rates (
        series_id,
        observation_date,
        value,
        realtime_start,
        realtime_end
    )
    VALUES %s
    ON CONFLICT (series_id, observation_date) DO UPDATE SET
        value = EXCLUDED.value,
        realtime_start = EXCLUDED.realtime_start,
        realtime_end = EXCLUDED.realtime_end;
    """

    print(f"  Fetching [{series_id}] from {start_date} to {end_date}...")

    while True:
        params = {
            "series_id": series_id,
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d"),
            "limit": limit,
            "offset": offset,
            "sort_order": "asc"
        }

        payload = fetch_fred_json("series/observations", params=params)
        obs_items = payload.get("observations", [])

        if not obs_items:
            break

        records = []
        for obs in obs_items:
            val_raw = obs.get("value")
            # In FRED, '.' represents missing/market-closed observations
            val = None if val_raw in (None, "", ".") else float(val_raw)

            records.append((
                series_id,
                obs["date"],
                val,
                obs.get("realtime_start"),
                obs.get("realtime_end")
            ))

        execute_values(cur, query, records)
        batch_len = len(records)
        total_synced += batch_len

        if batch_len < limit:
            break

        offset += limit

    print(f"  [{series_id}] Synced {total_synced} observations.")
    return total_synced


def run_scheduled_job():
    """Daily schedule: pulls trailing 14 days to capture revisions and latest prints."""
    today = date.today()
    start_date = today - timedelta(days=14)
    end_date = today

    print(f"Starting Rates sync (trailing window: {start_date} to {end_date})...")
    with get_db_cursor(commit=True) as cur:
        for ticker in TARGET_SERIES:
            sync_series_rates(cur, ticker, start_date, end_date)
    print("Rates sync complete.")


def run_backfill(start_date: date, end_date: date = None):
    """Backfills full historical observations (aligned with dateseries from 2020)."""
    if end_date is None:
        end_date = date.today()

    print(f"Starting Rates historical backfill: {start_date} to {end_date}...")
    with get_db_cursor(commit=True) as cur:
        for ticker in TARGET_SERIES:
            sync_series_rates(cur, ticker, start_date, end_date)
    print("Historical backfill complete.")


if __name__ == "__main__":
    # Standard scheduled run (trailing 14 days)
    run_scheduled_job()

    # To backfill history to match list.dateseries starting at 2020-01-01, comment out above and run:
    # run_backfill(date(2020, 1, 1))