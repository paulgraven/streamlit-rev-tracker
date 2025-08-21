from sqlalchemy import create_engine
import os

# You can store this securely in an environment variable or .env file
POSTGRES_URL = "postgresql://postgres:jsqAddWjYjEFQKbjSzgFMuSTmdjQnPtq@caboose.proxy.rlwy.net:52378/railway"

# Create SQLAlchemy engine
engine = create_engine(POSTGRES_URL)

def get_connection():
    return engine.connect()