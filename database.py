# database.py
import os
from sqlalchemy import create_engine

POSTGRES_URL = os.getenv("POSTGRES_URL")  # set this in Railway service Variables
if not POSTGRES_URL:
    raise RuntimeError("POSTGRES_URL environment variable is not set.")

engine = create_engine(POSTGRES_URL, pool_pre_ping=True)

def get_connection():
    return engine.connect()