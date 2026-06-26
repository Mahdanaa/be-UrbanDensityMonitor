from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
from datetime import datetime

from app.db.asyncpg_client import get_db_pool
from app.auth.jwt_handler import verify_jwt

router = APIRouter(
    prefix="/api/history",
    tags=["Traffic History"]
)

@router.get("/")
async def get_history(
    stream_id: Optional[str] = Query(None, description="Filter berdasarkan ID CCTV"),
    limit: int = Query(50, description="Jumlah maksimal data"),
    offset: int = Query(0, description="Mulai dari urutan ke berapa"),
    user_info: dict = Depends(verify_jwt)
):
    pool = get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database belum siap!")

    if stream_id:
        query = """
        SELECT id, stream_id, person_count, motorcycle_count, car_count, bus_count, truck_count,
               total_vehicle_count, person_vehicle_ratio, density_status, recorded_at
        FROM traffic_history
        WHERE stream_id = $1
        ORDER BY recorded_at DESC
        LIMIT $2 OFFSET $3
        """
        rows = await pool.fetch(query, stream_id, limit, offset)
    else:
        query = """
        SELECT id, stream_id, person_count, motorcycle_count, car_count, bus_count, truck_count,
               total_vehicle_count, person_vehicle_ratio, density_status, recorded_at
        FROM traffic_history
        ORDER BY recorded_at DESC
        LIMIT $1 OFFSET $2
        """
        rows = await pool.fetch(query, limit, offset)

    history_list = []
    for row in rows:
        item = dict(row)
        item["id"] = str(item["id"])
        item["stream_id"] = str(item["stream_id"])
        if isinstance(item["recorded_at"], datetime):
            item["recorded_at"] = item["recorded_at"].isoformat()
        history_list.append(item)

    return {"data": history_list, "limit": limit, "offset": offset, "total_returned": len(history_list)}
