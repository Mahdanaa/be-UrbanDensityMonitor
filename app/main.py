import asyncio
import cv2
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from ultralytics import YOLO
from app.routers import streams, history, alerts, users  # <-- Tambahkan 'users' di sini
from app.services.clustering import DensityAnalyzer
from app.db.asyncpg_client import init_db_pool, close_db_pool, get_db_pool
from fastapi.middleware.cors import CORSMiddleware
# --- Fungsi Kasir (Simpan ke Supabase) ---
async def save_to_db(payload, counts):
    try:
        pool = get_db_pool()
        if not pool:
            return  # Kalau database belum nyambung, lewati aja

        # 1. Simpan ke traffic_history
        query_history = """
        INSERT INTO traffic_history (stream_id, person_count, motorcycle_count, car_count, bus_count, truck_count, total_vehicle_count, person_vehicle_ratio, density_status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
        """
        total_v = counts["motorcycle"] + counts["car"] + counts["bus"] + counts["truck"]
        hist_id = await pool.fetchval(query_history,
            payload["stream_id"], counts["person"], counts["motorcycle"], counts["car"], counts["bus"], counts["truck"],
            total_v, payload["person_vehicle_ratio"], payload["density_status"]
        )

        # 2. Kalau Bahaya, Simpan ke Alerts
        if payload["density_status"] in ["High Density", "Anomaly"]:
            query_alert = """
            INSERT INTO alerts (traffic_history_id, stream_id, alert_type, alert_message)
            VALUES ($1, $2, $3, $4)
            """
            await pool.execute(query_alert, hist_id, payload["stream_id"], payload["density_status"], payload["alert"]["message"])

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")

# --- Manajemen Mesin Nyala/Mati ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    yield
    await close_db_pool()

app = FastAPI(title="Urban Density Monitor API", lifespan=lifespan)

# --- MULAI DARI SINI: Pasang Surat Izin CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Bolehkan akses dari semua browser/HTML
    allow_credentials=True,
    allow_methods=["*"],  # Bolehkan metode GET, POST, PUT, DELETE
    allow_headers=["*"],  # Bolehkan bawa tiket JWT di Header
)
# --- SAMPAI SINI ---

# Daftarkan Router (Biarkan kode bawahnya tetap sama)
app.include_router(streams.router)
app.include_router(history.router)
app.include_router(alerts.router)
app.include_router(users.router)

analyzer = DensityAnalyzer()
model = YOLO("yolov8n.pt")

@app.get("/")
def read_root():
    return {"message": "✅ Backend Urban Density Monitor Aktif!"}

# --- Jendela Layanan Live Streaming (WebSocket) ---
# --- Jendela Layanan Live Streaming (WebSocket) ---
@app.websocket("/ws/live/{stream_id}")
async def websocket_endpoint(websocket: WebSocket, stream_id: str):
    await websocket.accept()
    print(f"🔗 Client terhubung ke stream: {stream_id}")

    # --- KOKI BACA PESANAN DARI DATABASE ---
    pool = get_db_pool()
    if not pool:
        print("❌ Database belum nyambung!")
        await websocket.close()
        return

    try:
        # Cari URL asli berdasarkan ID yang diklik di HTML
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
    # --- SELESAI BACA PESANAN ---

    # Koki mulai memasak URL yang sudah didapat
    cap = cv2.VideoCapture(stream_url)

    try:
        while True:
            if not cap.isOpened():
                print("🔄 Reconnecting ke CCTV...")
# ... (Biarkan sisa kode ke bawahnya persis sama seperti sebelumnya) ...                cap = cv2.VideoCapture(stream_url)
                await asyncio.sleep(2)
                continue

            ret, frame = cap.read()
            if not ret:
                print("⚠️ Sinyal CCTV putus (Frame kosong)! Coba sambung ulang...")
                cap.release()
                await asyncio.sleep(2) # Tunggu 2 detik sebelum nyambung lagi
                continue # Langsung lompat ke putaran awal, jangan ke bawah

            # A. Koki YOLO Menganalisis Frame
            results = model(frame, classes=[0, 2, 3, 5, 7], verbose=False)

            counts = {"person": 0, "motorcycle": 0, "car": 0, "bus": 0, "truck": 0}

            # Hitung per kelas
            for box in results[0].boxes:
                cid = int(box.cls[0])
                if cid == 0: counts["person"] += 1
                elif cid == 2: counts["car"] += 1
                elif cid == 3: counts["motorcycle"] += 1
                elif cid == 5: counts["bus"] += 1
                elif cid == 7: counts["truck"] += 1

            vehicle_total = counts["motorcycle"] + counts["car"] + counts["bus"] + counts["truck"]

            # B. Ahli Gizi (Clustering) Tentukan Status
            analysis = analyzer.analyze(counts["person"], vehicle_total)

            # C. Plating! (Gambar kotak Bounding Box)
            annotated_frame = results[0].plot()

            # D. Ubah Gambar jadi Base64 biar bisa dikirim lewat teks
            _, buffer = cv2.imencode('.jpg', annotated_frame)
            frame_b64 = base64.b64encode(buffer).decode('utf-8')

            # E. Siapkan Struk Laporan
            payload = {
                "type": "frame_update",
                "stream_id": stream_id,
                "counts": counts,
                "person_vehicle_ratio": analysis["ratio"],
                "density_status": analysis["status"],
                # Biarkan nama lama untuk jaga-jaga
                "frame_base64": frame_b64,
                # 👇 TAMBAHAN BARU: Kasih nama 'frame' plus awalan Base64 biar FE tinggal telan!
                "frame": f"data:image/jpeg;base64,{frame_b64}"
            }

            # Jika bahaya, tambahkan alarm merah/oranye!
            if analysis["status"] in ["High Density", "Anomaly"]:
                payload["alert"] = {
                    "triggered": True,
                    "type": analysis["status"],
                    "message": f"🚨 {analysis['status'].upper()} DETECTED!"
                }

            # --- F. Kasir Mencatat ke Database! ---
            await save_to_db(payload, counts)

            # G. Pelayan Ngirim Makanan ke Meja (Kirim ke Next.js)
            await websocket.send_json(payload)

            # H. Polisi Tidur (Biar CPU/GPU kamu gak meledak)
            await asyncio.sleep(0.03)

    except WebSocketDisconnect:
        print(f"❌ Client terputus dari stream: {stream_id}")
    except Exception as e:
        print(f"⚠️ Error: {e}")
    finally:
        cap.release()
        print("🛑 Stream CCTV ditutup.")
