import os
from sqlalchemy import create_engine

# Prefer POSTGRES_URL; fall back to DATABASE_URL if Railway provides it
DATABASE_URL = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Database URL environment variable is not set.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def get_connection():
    return engine.connect()