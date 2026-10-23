import sys
from pathlib import Path
from psycopg2.extras import execute_values

# Allow imports from src/
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from db_manager import get_db_cursor
from FRED.fred_client import fetch_fred_json

MAX_DEPTH = 3  # Level 1 (Pillars), Level 2 (Sub-branches), Level 3 (Sub-indices)


def run_scheduled_job():
    print(f"Syncing FRED categories up to Level {MAX_DEPTH}...")

    upsert_query = """
    INSERT INTO fred.categories (id, name, parent_id)
    VALUES %s
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        parent_id = EXCLUDED.parent_id;
    """

    with get_db_cursor(commit=True) as cur:
        # Step 1: Ensure Root category (0) is present
        root_payload = fetch_fred_json("category", {"category_id": 0})
        root_data = root_payload.get("categories", [{}])[0]
        cur.execute(
            """
            INSERT INTO fred.categories (id, name, parent_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
            """,
            (0, root_data.get("name", "Root"), None),
        )

        # Queue contains tuples of (category_id, current_depth)
        queue = [(0, 0)]
        visited = set()
        total_synced = 1

        while queue:
            current_id, depth = queue.pop(0)

            # Stop expanding deeper once target depth is reached
            if depth >= MAX_DEPTH:
                continue

            if current_id in visited:
                continue
            visited.add(current_id)

            payload = fetch_fred_json("category/children", {"category_id": current_id})
            children = payload.get("categories", [])

            if not children:
                continue

            records = [(c["id"], c["name"], c.get("parent_id")) for c in children]
            execute_values(cur, upsert_query, records)
            total_synced += len(records)

            next_depth = depth + 1
            print(f"  Level {next_depth}: Synced {len(records)} child categories under Parent ID {current_id}.")

            # Enqueue child categories for the next depth level
            for c in children:
                queue.append((c["id"], next_depth))

    print(f"[fred.categories] Sync complete. Ingested {total_synced} categories (Levels 0 through {MAX_DEPTH}).")


if __name__ == "__main__":
    run_scheduled_job()









# import sys
# from pathlib import Path
# from psycopg2.extras import execute_values

# SRC_DIR = Path(__file__).resolve().parent.parent
# if str(SRC_DIR) not in sys.path:
#     sys.path.append(str(SRC_DIR))

# from db_manager import get_db_cursor
# from FRED.fred_client import fetch_fred_json


# def run_scheduled_job():
#     print("Crawling FRED category tree...")
#     query = """
#     INSERT INTO fred.categories (id, name, parent_id)
#     VALUES %s
#     ON CONFLICT (id) DO UPDATE SET
#         name = EXCLUDED.name,
#         parent_id = EXCLUDED.parent_id;
#     """

#     # Queue of category IDs to explore: start with root (0)
#     queue = [0]
#     visited = set()
#     total_categories = 0

#     with get_db_cursor(commit=True) as cur:
#         # First ensure root 0 exists in DB
#         root_payload = fetch_fred_json("category", {"category_id": 0})
#         root_data = root_payload.get("categories", [{}])[0]
#         cur.execute(
#             """
#             INSERT INTO fred.categories (id, name, parent_id)
#             VALUES (%s, %s, %s)
#             ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
#             """,
#             (0, root_data.get("name", "Root"), None),
#         )

#         while queue:
#             current_cat_id = queue.pop(0)
#             if current_cat_id in visited:
#                 continue
#             visited.add(current_cat_id)

#             payload = fetch_fred_json("category/children", {"category_id": current_cat_id})
#             children = payload.get("categories", [])

#             if children:
#                 records = [(c["id"], c["name"], c.get("parent_id")) for c in children]
#                 execute_values(cur, query, records)
#                 total_categories += len(records)

#                 # Queue child categories to fetch their sub-categories
#                 for c in children:
#                     queue.append(c["id"])

#     print(f"[fred.categories] Synced {total_categories} sub-categories.")


# if __name__ == "__main__":
#     run_scheduled_job()