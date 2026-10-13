import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from pymongo import AsyncMongoClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("MONGODB_DB_NAME", "nexhire")

client = (
    AsyncMongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    if MONGODB_URI
    else None
)

db = client[DATABASE_NAME] if client is not None else None


def get_users_collection():
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not configured. Check backend/.env.",
        )
    return db["users"]


async def ensure_database_indexes():
    if db is None:
        raise RuntimeError("MONGODB_URI is missing from backend/.env")

    await db.command("ping")
    await db["users"].create_index("email", unique=True)
    print(f"Connected to MongoDB database: {DATABASE_NAME}")


async def close_database():
    if client is not None:
        await client.close()