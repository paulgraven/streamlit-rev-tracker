import os
from sqlalchemy import create_engine

# Prefer POSTGRES_URL, but fallback to Railway's default DATABASE_URL if available
DATABASE_URL = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("Database URL environment variable is not set.")

# Create the database engine
engine = create_engine(DATABASE_URL, echo=False)

def get_connection():
    return engine.connect()