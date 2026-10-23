import sys
import json
import hashlib
from pathlib import Path
from datetime import date
from psycopg2.extras import execute_values

# Allow imports from src/
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from db_manager import get_db_cursor
from Polygon.polygon_client import fetch_polygon_json

# Core index/equity tickers to pull full option chains for
TARGET_UNDERLYINGS = ["SPY", "QQQ", "IWM"]


def clean_num(val):
    """Converts missing, null, or out-of-bounds numeric fields to None."""
    if val in (None, "", "NaN"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def sync_options_chain_snapshot(cur, underlying: str):
    """Fetches the complete current options chain snapshot for an underlying ticker."""
    endpoint = f"v3/snapshot/options/{underlying}"
    params = {"limit": 250}  # Polygon's maximum page size for chain snapshots
    
    total_staged = 0
    next_url = None

    query = """
    INSERT INTO polygon.stg_options_bars (
        underlying_symbol,
        option_symbol,
        contract_type,
        expiration_date,
        strike_price,
        bar_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        open_interest,
        implied_volatility,
        delta,
        gamma,
        theta,
        vega,
        payload_hash,
        is_processed
    )
    VALUES %s
    ON CONFLICT (option_symbol, bar_date) DO UPDATE SET
        open_price = EXCLUDED.open_price,
        high_price = EXCLUDED.high_price,
        low_price = EXCLUDED.low_price,
        close_price = EXCLUDED.close_price,
        volume = EXCLUDED.volume,
        open_interest = EXCLUDED.open_interest,
        implied_volatility = EXCLUDED.implied_volatility,
        delta = EXCLUDED.delta,
        gamma = EXCLUDED.gamma,
        theta = EXCLUDED.theta,
        vega = EXCLUDED.vega,
        payload_hash = EXCLUDED.payload_hash,
        is_processed = FALSE;
    """

    print(f"Fetching options snapshot for [{underlying}]...")

    while True:
        # Use relative endpoint on initial request; next_url on subsequent pages
        if next_url:
            data = fetch_polygon_json(next_url)
        else:
            data = fetch_polygon_json(endpoint, params=params)

        results = data.get("results", [])
        if not results:
            break

        records = []
        today_str = date.today().isoformat()

        for contract in results:
            details = contract.get("details", {})
            greeks = contract.get("greeks", {})
            day_bar = contract.get("day", {})

            option_symbol = details.get("ticker")
            if not option_symbol:
                continue

            # Extract bar date or fallback to today
            bar_date = today_str
            if day_bar and day_bar.get("last_updated"):
                # Polygon timestamps are Unix nanoseconds
                bar_date = date.fromtimestamp(day_bar["last_updated"] / 1e9).isoformat()

            raw_str = json.dumps(contract, sort_keys=True)
            payload_hash = hashlib.md5(raw_str.encode("utf-8")).hexdigest()

            records.append((
                underlying,
                option_symbol,
                details.get("contract_type", "").lower(),  # 'call' or 'put'
                details.get("expiration_date"),
                clean_num(details.get("strike_price")),
                bar_date,
                clean_num(day_bar.get("open")),
                clean_num(day_bar.get("high")),
                clean_num(day_bar.get("low")),
                clean_num(day_bar.get("close")),
                day_bar.get("volume"),
                contract.get("open_interest"),
                clean_num(contract.get("implied_volatility")),
                clean_num(greeks.get("delta")),
                clean_num(greeks.get("gamma")),
                clean_num(greeks.get("theta")),
                clean_num(greeks.get("vega")),
                payload_hash,
                False
            ))

        execute_values(cur, query, records)
        batch_len = len(records)
        total_staged += batch_len
        print(f"  Staged: {batch_len} contracts (Total so far: {total_staged})")

        # Handle cursor pagination
        next_url = data.get("next_url")
        if not next_url:
            break

    print(f"[{underlying}] Snapshot completed. Total contracts ingested: {total_staged}.")
    return total_staged


def run_scheduled_job():
    """Daily schedule: pulls complete option snapshots for tracked underlyings."""
    print(f"Starting Polygon Options Snapshot for {len(TARGET_UNDERLYINGS)} symbols...")
    with get_db_cursor(commit=True) as cur:
        for ticker in TARGET_UNDERLYINGS:
            sync_options_chain_snapshot(cur, ticker)
    print("Polygon options snapshot ingestion complete.")


if __name__ == "__main__":
    run_scheduled_job()