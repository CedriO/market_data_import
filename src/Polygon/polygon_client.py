import os
import sys
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

SRC_DIR = Path(__file__).resolve().parent.parent
load_dotenv(SRC_DIR.parent / ".env")

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
BASE_URL = "https://api.polygon.io"

if not POLYGON_API_KEY:
    raise ValueError("Missing POLYGON_API_KEY in .env file.")

# Set to 12.0 for Free Tier (5 calls/min). Lower to 0.1 for Paid Unlimited tiers.
REQUEST_INTERVAL_SECONDS = 12.0

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {POLYGON_API_KEY}",
    "Accept": "application/json"
})

last_request_time = 0.0


def fetch_polygon_json(endpoint_or_url: str, params: dict | None = None) -> dict:
    """Thread-safe, rate-controlled client for Polygon REST API with cursor support."""
    global last_request_time

    # Determine whether endpoint_or_url is a relative path or a full next_url link
    if endpoint_or_url.startswith("http"):
        url = endpoint_or_url
    else:
        url = f"{BASE_URL}/{endpoint_or_url.lstrip('/')}"

    while True:
        elapsed = time.time() - last_request_time
        if elapsed < REQUEST_INTERVAL_SECONDS:
            time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)

        try:
            last_request_time = time.time()
            response = session.get(url, params=params, timeout=20)

            if response.status_code == 429:
                print("[Polygon Client] Rate limit exceeded (429). Cooling down for 60 seconds...")
                time.sleep(60)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            if response.status_code == 429:
                time.sleep(60)
                continue
            raise e