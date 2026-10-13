
import asyncio
from app.database import client, db


async def main():
    if client is None or db is None:
        print("ERROR: MONGODB_URI is missing from .env")
        return

    try:
        await client.admin.command("ping")
        print("SUCCESS: Connected to MongoDB Atlas!")
        print(f"Database name: {db.name}")
        print("Ready to implement authentication.")
    except Exception as error:
        print("MongoDB connection failed.")
        print(f"Error type: {type(error).__name__}")
        print("Check your URI, password, IP access list, and network.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
