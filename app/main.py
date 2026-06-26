import asyncio
import cv2
import base64
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
        print(f"❌ DATABASE ERROR: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    yield
    await close_db_pool()

app = FastAPI(title="Urban Density Monitor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(streams.router)
app.include_router(history.router)
app.include_router(alerts.router)
app.include_router(users.router)

model = YOLO("yolov8l.pt").to("cuda")

@app.get("/")
def read_root():
    return {"message": "✅ Backend Urban Density Monitor Aktif!"}

@app.websocket("/ws/live/{stream_id}")
async def websocket_endpoint(websocket: WebSocket, stream_id: str):
    await websocket.accept()
    print(f"🔗 Client terhubung ke stream: {stream_id}")
    pool = get_db_pool()
    if not pool:
        print("❌ Database belum nyambung!")
        await websocket.close()
        return
    try:
        query = "SELECT stream_url FROM streams WHERE id = $1"
        stream_url = await pool.fetchval(query, stream_id)
        if not stream_url:
            print(f"❌ CCTV dengan ID {stream_id} tidak ditemukan!")
            await websocket.close()
            return
        print(f"🎥 Membuka CCTV: {stream_url}")

    except Exception as e:
        print(f"❌ Error Database: {e}")
        await websocket.close()
        return

    cap = cv2.VideoCapture(stream_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    try:
        frame_count = 0
        skip_rate = 1

        while True:

            start_waktu = time.time()
            if not cap.isOpened():
                print("🔄 Reconnecting ke CCTV...")
                cap = cv2.VideoCapture(stream_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                await asyncio.sleep(1)
                continue
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Sinyal CCTV putus (Frame kosong)! Coba sambung ulang...")
                cap.release()
                await asyncio.sleep(1)
                continue

            frame_count += 1
            if frame_count % skip_rate != 0:
                continue

            results = model(
                frame,
                classes=[0, 2, 3, 5, 7],
                verbose=False,
                conf=0.45,
                iou=0.45,
                device='cuda'
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

            asyncio.create_task(save_to_db(payload, counts))
            await websocket.send_json(payload)

            end_waktu = time.time()
            waktu_proses_detik = end_waktu - start_waktu
            latency_ms = waktu_proses_detik * 1000
            fps = 1.0 / waktu_proses_detik if waktu_proses_detik > 0 else 0.0

            print(f"📊 YOLO 8n Latency: {latency_ms:.1f} ms | Speed: {fps:.1f} FPS")
            await asyncio.sleep(0.001)

    except WebSocketDisconnect:
        print(f"❌ Client terputus dari stream: {stream_id}")
    except Exception as e:
        print(f"⚠️ Error: {e}")
    finally:
        cap.release()
        print("🛑 Stream CCTV ditutup.")
