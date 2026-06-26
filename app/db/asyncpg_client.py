import asyncpg
import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

pool = None

async def init_db_pool():
    global pool
    logger.info("🗄️ Menghubungkan ke Supabase (asyncpg)...")
    try:
        pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=10,
            statement_cache_size=0
        )
        logger.info("✅ Database Supabase Terhubung!")
    except Exception as e:
        logger.error(f"❌ Gagal konek ke DB: {e}")

async def close_db_pool():
    global pool
    if pool:
        await pool.close()
        logger.info("🛑 Koneksi Database ditutup.")

def get_db_pool():
    return pool
