import cv2
from ultralytics import YOLO

def test_yolo():
    print("🔥 Memanaskan mesin YOLOv8...")

    # Load model YOLOv8 (Otomatis download yolov8n.pt kalau belum ada)
    model = YOLO("yolov8n.pt")

    # URL CCTV Semarang (Contoh aja buat ngetes)
    stream_url = "https://livepantau.semarangkota.go.id/a875df34-d235-4760-8c7f-2705fb155807/index.m3u8"

    print(f"📡 Mencoba konek ke: {stream_url}")
    cap = cv2.VideoCapture(stream_url)

    if not cap.isOpened():
        print("❌ Gagal buka stream CCTV! (Mungkin token expired)")
        return

    print("✅ Berhasil buka CCTV! Mulai deteksi...")

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Stream terputus!")
            break

        frame_count += 1

        # Biar gak berat, kita proses 1 frame aja buat bukti!
        if frame_count == 1:
            print("📸 Frame berhasil ditangkap! Menganalisis...")

            # Deteksi: 0=Person, 2=Car, 3=Motor, 5=Bus, 7=Truck
            results = model(frame, classes=[0, 2, 3, 5, 7], verbose=False)

            # Ekstrak hasil hitungan
            boxes = results[0].boxes
            print(f"🎯 KETEMU {len(boxes)} OBJEK DI FRAME INI!")

            for box in boxes:
                class_id = int(box.cls[0])
                class_name = model.names[class_id]
                conf = float(box.conf[0])
                print(f"  -> {class_name} (Yakin: {conf*100:.1f}%)")

            break # Selesai, kita cuma butuh 1 bukti frame!

    cap.release()
    print("🏁 Tes Selesai!")

if __name__ == "__main__":
    test_yolo()
