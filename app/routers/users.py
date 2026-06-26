from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db.asyncpg_client import get_db_pool
from app.auth.jwt_handler import verify_jwt
router = APIRouter(
    prefix="/api/users",
    tags=["User Management (Admin)"]
)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

async def kuasai_akses_admin(user_info: dict, pool):
    user_id = user_info.get("sub")
    role = await pool.fetchval("SELECT role FROM users WHERE id = $1", user_id)
    if role != "admin":
        raise HTTPException(status_code=403, detail="⛔ Akses ditolak! Fitur ini khusus untuk Admin.")
@router.get("/")
async def get_all_users(user_info: dict = Depends(verify_jwt)):
    pool = get_db_pool()
    if not pool: raise HTTPException(status_code=500, detail="Database belum siap!")
    await kuasai_akses_admin(user_info, pool)

    query = "SELECT id, email, full_name, role, is_active, created_at FROM users ORDER BY created_at DESC"
    rows = await pool.fetch(query)
    user_list = []
    for row in rows:
        item = dict(row)
        item["id"] = str(item["id"])
        if isinstance(item["created_at"], datetime):
            item["created_at"] = item["created_at"].isoformat()
        user_list.append(item)

    return {"data": user_list, "total": len(user_list)}

@router.put("/{user_id}")
async def update_user(user_id: str, user_data: UserUpdate, user_info: dict = Depends(verify_jwt)):
    pool = get_db_pool()
    await kuasai_akses_admin(user_info, pool)

    query = """
    UPDATE users
    SET full_name = COALESCE($1, full_name),
        role = COALESCE($2, role),
        is_active = COALESCE($3, is_active)
    WHERE id = $4 RETURNING id
    """
    updated_id = await pool.fetchval(query, user_data.full_name, user_data.role, user_data.is_active, user_id)
    if not updated_id:
        raise HTTPException(status_code=404, detail="User tidak ditemukan!")
    return {"message": f"✅ Data user {user_id} berhasil diperbarui!"}

@router.delete("/{user_id}")
async def delete_user(user_id: str, user_info: dict = Depends(verify_jwt)):
    pool = get_db_pool()
    await kuasai_akses_admin(user_info, pool)

    query = "DELETE FROM users WHERE id = $1"
    result = await pool.execute(query, user_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="User tidak ditemukan!")
    return {"message": f"🗑️ User {user_id} berhasil dihapus!"}
