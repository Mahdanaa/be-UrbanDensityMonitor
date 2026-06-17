import asyncpg
import os
from dotenv import load_dotenv

# Baca isi file .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Wadah penampung koneksi
pool = None

async def init_db_pool():
    global pool
    print("🗄️ Menghubungkan ke Supabase (asyncpg)...")
    try:
        pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=10,
            statement_cache_size=0  # 👈 INI OBAT ANTI-ERROR PGBOUNCER!
        )
        print("✅ Database Supabase Terhubung!")
    except Exception as e:
        print(f"❌ Gagal konek ke DB: {e}")

async def close_db_pool():
    global pool
    if pool:
        await pool.close()
        print("🛑 Koneksi Database ditutup.")

def get_db_pool():
    return pool
