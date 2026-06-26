from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from app.db.asyncpg_client import get_db_pool

from app.auth.jwt_handler import verify_jwt

router = APIRouter(
    prefix="/api/streams",
    tags=["Streams CCTV"]
)

class StreamCreate(BaseModel):
    location_name: str
    stream_url: str
    stream_type: str

class StreamResponse(BaseModel):
    id: str
    location_name: str
    stream_url: str
    stream_type: str
    status: str

@router.get("/", response_model=dict)
async def get_streams(user_info: dict = Depends(verify_jwt)):
    pool = get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database belum siap!")

    query = "SELECT id, location_name, stream_url, stream_type, status FROM streams ORDER BY location_name ASC"

    try:
        rows = await pool.fetch(query)
        streams_data = [dict(row) for row in rows]
        for s in streams_data:
            s['id'] = str(s['id'])

        return {"data": streams_data, "total": len(streams_data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def add_stream(stream: StreamCreate, user_info: dict = Depends(verify_jwt)):
    pool = get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database belum siap!")
    query = """
    INSERT INTO streams (location_name, stream_url, stream_type)
    VALUES ($1, $2, $3) RETURNING id
    """
    try:
        new_id = await pool.fetchval(query, stream.location_name, stream.stream_url, stream.stream_type)
        return {"message": f"✅ CCTV {stream.location_name} berhasil ditambahkan!", "id": str(new_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{stream_id}")
async def delete_stream(stream_id: str, user_info: dict = Depends(verify_jwt)):
    pool = get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database belum siap!")
    query = "DELETE FROM streams WHERE id = $1"
    try:
        await pool.execute(query, stream_id)
        return {"message": f"🗑️ CCTV {stream_id} berhasil dihapus!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
