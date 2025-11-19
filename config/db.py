import os

import asyncpg
from dotenv import load_dotenv
from utils.logger import get_logger

load_dotenv()
logger = get_logger("db")

pool = None


async def init_db():
    global pool
    try:
        pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
        logger.info("✅ PostgreSQL pool initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize DB pool: {e}")


async def get_pool():
    return pool
