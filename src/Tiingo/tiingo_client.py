import os
import sys
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

SRC_DIR = Path(__file__).resolve().parent.parent
load_dotenv(SRC_DIR.parent / ".env")

TIINGO_API_KEY = os.getenv("TIINGO_API_KEY")
BASE_URL = "https://api.tiingo.com/tiingo"

if not TIINGO_API_KEY:
    raise ValueError("Missing TIINGO_API_KEY in .env file.")

session = requests.Session()
session.headers.update({
    "Content-Type": "application/json",
    "Authorization": f"Token {TIINGO_API_KEY}"
})


def fetch_tiingo_json(endpoint: str, params: dict | None = None) -> list | dict:
    """Thread-safe, authenticated client for Tiingo REST API."""
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    time.sleep(0.5)  # Respect free/starter tier rate limits

    response = session.get(url, params=params, timeout=15)

    if response.status_code == 429:
        print("[Tiingo Client] Rate limit encountered. Waiting 60 seconds...")
        time.sleep(60)
        response = session.get(url, params=params, timeout=15)

    response.raise_for_status()
    return response.json()