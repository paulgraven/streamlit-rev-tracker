# database.py
import os
import psycopg2

def get_connection():
    db_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("Database URL environment variable is not set.")
    # psycopg2 connects directly using the URL string
    return psycopg2.connect(db_url)