from fastapi import APIRouter, Query, HTTPException, Depends # <-- Tambah Depends
from typing import Optional
from datetime import datetime

from app.db.asyncpg_client import get_db_pool
from app.auth.jwt_handler import verify_jwt # <-- Panggil Satpam

router = APIRouter(
    prefix="/api/alerts",
    tags=["Alerts & Notifications"]
)

@router.get("/")
async def get_alerts(
    stream_id: Optional[str] = Query(None, description="Filter alert CCTV tertentu"),
    is_read: Optional[bool] = Query(None, description="Filter yang belum/sudah dibaca"),
    limit: int = Query(20, description="Maksimal data alert"),
    user_info: dict = Depends(verify_jwt) # 🔒 PINTU DIGEMBOK!
):
    pool = get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database belum siap!")

    query = "SELECT id, traffic_history_id, stream_id, alert_type, alert_message, is_read, created_at FROM alerts WHERE 1=1"
    params = []
    counter = 1

    if stream_id:
        query += f" AND stream_id = ${counter}"
        params.append(stream_id)
        counter += 1

    if is_read is not None:
        query += f" AND is_read = ${counter}"
        params.append(is_read)
        counter += 1

    query += f" ORDER BY created_at DESC LIMIT ${counter}"
    params.append(limit)

    rows = await pool.fetch(query, *params)
    alert_list = []
    for row in rows:
        item = dict(row)
        item["id"] = str(item["id"])
        item["traffic_history_id"] = str(item["traffic_history_id"])
        item["stream_id"] = str(item["stream_id"])
        if isinstance(item["created_at"], datetime):
            item["created_at"] = item["created_at"].isoformat()
        alert_list.append(item)

    return {"data": alert_list}

@router.patch("/{alert_id}/read")
async def mark_alert_read(alert_id: str, user_info: dict = Depends(verify_jwt)): # 🔒 PINTU DIGEMBOK!
    pool = get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database belum siap!")
    query = "UPDATE alerts SET is_read = true WHERE id = $1"
    await pool.execute(query, alert_id)
    return {"message": f"✅ Alert {alert_id} berhasil ditandai sudah dibaca"}
