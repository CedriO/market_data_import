from pathlib import Path
from contextlib import contextmanager
import psycopg2
from dotenv import dotenv_values

# Resolve root .env (src/ -> market_data_import/)
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
config = dotenv_values(ENV_PATH)

PG_HOST = config.get("PG_HOST", "localhost")
PG_PORT = config.get("PG_PORT", "5432")
PG_DATABASE = config.get("PG_DATABASE", "postgres")
PG_USER = config.get("PG_USER", "postgres")
PG_PASSWORD = config.get("PG_PASSWORD")


def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD,
    )


@contextmanager
def get_db_cursor(commit=True):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()