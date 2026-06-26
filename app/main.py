import asyncio
import cv2
import base64
import time
import torch
import logging
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager
from ultralytics import YOLO
from app.routers import streams, history, alerts, users
from app.services.clustering import predict_density
from app.db.asyncpg_client import init_db_pool, close_db_pool, get_db_pool
from fastapi.middleware.cors import CORSMiddleware

async def save_to_db(payload, counts):
    try:
        pool = get_db_pool()
        if not pool: return
        query_history = """
        INSERT INTO traffic_history (stream_id, person_count, motorcycle_count, car_count, bus_count, truck_count, total_vehicle_count, person_vehicle_ratio, density_status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
        """
        total_v = counts["motorcycle"] + counts["car"] + counts["bus"] + counts["truck"]
        hist_id = await pool.fetchval(query_history,
            payload["stream_id"], counts["person"], counts["motorcycle"], counts["car"], counts["bus"], counts["truck"],
            total_v, payload["person_vehicle_ratio"], payload["density_status"]
        )
        if payload["density_status"] in ["High Density", "Anomaly"]:
            query_alert = """
            INSERT INTO alerts (traffic_history_id, stream_id, alert_type, alert_message)
            VALUES ($1, $2, $3, $4)
            """
            await pool.execute(query_alert, hist_id, payload["stream_id"], payload["density_status"], payload["alert"]["message"])
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    yield
    await close_db_pool()

app = FastAPI(title="Urban Density Monitor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:5050",
        "http://127.0.0.1:5050",
        "http://localhost:5500",
        "https://urbandensitymonitor.web.id",
        "https://www.urbandensitymonitor.web.id"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(streams.router)
app.include_router(history.router)
app.include_router(alerts.router)
app.include_router(users.router)

device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = YOLO("yolov8s.pt").to(device)

def process_frame_sync(frame):
    results = model(
        frame,
        classes=[0, 2, 3, 5, 7],
        verbose=False,
        conf=0.45,
        iou=0.45,
        device=device
    )
    counts = {"person": 0, "motorcycle": 0, "car": 0, "bus": 0, "truck": 0}

    for box in results[0].boxes:
        cid = int(box.cls[0])
        if cid == 0: counts["person"] += 1
        elif cid == 2: counts["car"] += 1
        elif cid == 3: counts["motorcycle"] += 1
        elif cid == 5: counts["bus"] += 1
        elif cid == 7: counts["truck"] += 1

    vehicle_total = counts["motorcycle"] + counts["car"] + counts["bus"] + counts["truck"]
    status_jalan = predict_density(counts["person"], vehicle_total)
    rasio = counts["person"] / vehicle_total if vehicle_total > 0 else 0.0
    annotated_frame = results[0].plot()
    _, buffer = cv2.imencode('.jpg', annotated_frame)
    frame_b64 = base64.b64encode(buffer).decode('utf-8')

    return counts, rasio, status_jalan, frame_b64

@app.get("/")
def read_root():
    return {"message": "✅ Backend Urban Density Monitor Aktif!"}

@app.websocket("/ws/live/{stream_id}")
async def websocket_endpoint(websocket: WebSocket, stream_id: str):
    await websocket.accept()
    logger.info(f"🔗 Client terhubung ke stream: {stream_id}")
    pool = get_db_pool()
    if not pool:
        logger.error("❌ Database belum nyambung!")
        await websocket.close()
        return
    try:
        query = "SELECT stream_url FROM streams WHERE id = $1"
        stream_url = await pool.fetchval(query, stream_id)
        if not stream_url:
            logger.warning(f"❌ CCTV dengan ID {stream_id} tidak ditemukan!")
            await websocket.close()
            return
        logger.info(f"🎥 Membuka CCTV: {stream_url}")

    except Exception as e:
        logger.error(f"❌ Error Database: {e}")
        await websocket.close()
        return

    q = asyncio.Queue(maxsize=5)
    loop = asyncio.get_running_loop()
    state = {"running": True}

    def put_to_queue(item):
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            pass

    def video_thread():
        cap = cv2.VideoCapture(stream_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        frame_count = 0
        skip_rate = 1

        while state["running"]:
            start_waktu = time.time()
            if not cap.isOpened():
                logger.warning("🔄 Reconnecting ke CCTV...")
                cap = cv2.VideoCapture(stream_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                time.sleep(1)
                continue
            
            ret, frame = cap.read()
            if not ret:
                logger.warning("⚠️ Sinyal CCTV putus (Frame kosong)! Coba sambung ulang...")
                cap.release()
                time.sleep(1)
                continue

            frame_count += 1
            if frame_count % skip_rate != 0:
                continue

            counts, rasio, status_jalan, frame_b64 = process_frame_sync(frame)

            payload = {
                "type": "frame_update",
                "stream_id": stream_id,
                "counts": counts,
                "person_vehicle_ratio": rasio,
                "density_status": status_jalan,
                "frame_base64": frame_b64,
                "frame": f"data:image/jpeg;base64,{frame_b64}"
            }

            if status_jalan in ["High Density", "Anomaly"]:
                payload["alert"] = {
                    "triggered": True,
                    "type": status_jalan,
                    "message": f"🚨 {status_jalan.upper()} DETECTED!"
                }

            end_waktu = time.time()
            waktu_proses_detik = end_waktu - start_waktu
            latency_ms = waktu_proses_detik * 1000
            fps = 1.0 / waktu_proses_detik if waktu_proses_detik > 0 else 0.0

            loop.call_soon_threadsafe(put_to_queue, (payload, counts, latency_ms, fps))
            time.sleep(0.001)

        cap.release()

    t = threading.Thread(target=video_thread, daemon=True)
    t.start()

    try:
        while True:
            payload, counts, latency_ms, fps = await q.get()
            asyncio.create_task(save_to_db(payload, counts))
            await websocket.send_json(payload)
            logger.info(f"📊 YOLO 8s Latency: {latency_ms:.1f} ms | Speed: {fps:.1f} FPS")

    except WebSocketDisconnect:
        logger.info(f"❌ Client terputus dari stream: {stream_id}")
    except Exception as e:
        logger.error(f"⚠️ Error: {e}")
    finally:
        state["running"] = False
        logger.info("🛑 Stream CCTV ditutup.")
