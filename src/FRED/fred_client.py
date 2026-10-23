import time
import threading
from pathlib import Path
import requests
from dotenv import dotenv_values

# Resolve root .env (src/FRED/ -> src/ -> root)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"
config = dotenv_values(ENV_PATH)
FRED_API_KEY = config.get("FRED_API_KEY")

if not FRED_API_KEY:
    raise ValueError(f"FRED_API_KEY missing from {ENV_PATH}")

BASE_URL = "https://api.stlouisfed.org/fred"

# Rate compliance settings
MIN_INTERVAL_SECONDS = 1.2  # ~50 requests/min max (FRED limit is 120)
_request_lock = threading.Lock()


def fetch_fred_json(endpoint: str, params: dict = None, max_retries: int = 5) -> dict:
    """Rate-controlled, self-healing HTTP client for FRED.
    
    Catches 429 errors, pauses for FRED's rolling 60s cooldown,
    and retries transparently.
    """
    if params is None:
        params = {}
    params.update({"api_key": FRED_API_KEY, "file_type": "json"})

    with _request_lock:
        for attempt in range(1, max_retries + 1):
            response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
            
            # Enforce baseline polite delay between every call
            time.sleep(MIN_INTERVAL_SECONDS)

            # Handle 429 Rate Limit Cooldown
            if response.status_code == 429:
                wait_time = 75  # Clear FRED's rolling 1-minute window
                print(f"\n[RATE LIMIT] HTTP 429 encountered on '{endpoint}'.")
                print(f"             Pausing for {wait_time}s to reset FRED quota (attempt {attempt}/{max_retries})...")
                time.sleep(wait_time)
                continue

            # Other HTTP errors (400, 404, 500, etc.)
            if not response.ok:
                try:
                    err_msg = response.json().get("error_message", response.text)
                except Exception:
                    err_msg = response.text
                safe_msg = str(err_msg).replace(FRED_API_KEY, "***MASKED***")
                print(f"[FRED API Error {response.status_code}] on {endpoint}: {safe_msg}")
                response.raise_for_status()

            return response.json()

        raise RuntimeError(f"Endpoint '{endpoint}' failed after {max_retries} attempts due to repeated rate limits.")