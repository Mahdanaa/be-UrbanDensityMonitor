import numpy as np
from sklearn.cluster import KMeans
import os
import pickle

class DensityAnalyzer:
    def __init__(self):
        self.model_path = "app/models/density_cluster_model.pkl"
        self.model = self._load_or_train_model()

    def _load_or_train_model(self):
        # Kalau model ML sudah ada, tinggal load
        if os.path.exists(self.model_path):
            with open(self.model_path, 'rb') as f:
                return pickle.load(f)

        print("⚙️ Membuat model K-Means awal (Dummy Training)...")
        # Data simulasi: [person_count, vehicle_count, ratio]
        # Kita ajarin AI-nya kondisi jalanan:
        X_dummy = np.array([
            [2, 5, 0.4],    # Sepi
            [5, 15, 0.33],  # Sepi
            [15, 20, 0.75], # Sedang
            [25, 30, 0.83], # Sedang
            [50, 10, 5.0],  # Padat / Anomali (Banyak orang, dikit mobil)
            [80, 5, 16.0]   # Padat Banget (Demo)
        ])

        # Bikin 3 kelompok (Low, Medium, High)
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        kmeans.fit(X_dummy)

        # Simpan otak ML-nya ke file .pkl
        os.makedirs("app/models", exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump(kmeans, f)

        return kmeans

    def analyze(self, person_count, vehicle_count):
        # 1. Ekstraksi Fitur (ATM dari Jurnal)
        ratio = person_count / max(vehicle_count, 1)

        # 2. Prediksi pakai ML
        features = np.array([[person_count, vehicle_count, ratio]])
        cluster_id = self.model.predict(features)[0]

        # 3. Logika Anomali (DBSCAN / Rule-based hybrid)
        # Jika rasionya mendadak ekstrem (terlalu banyak orang di jalan raya)
        if ratio > 3.0 and person_count > 10:
            status = "Anomaly"
        elif cluster_id == 0:
            status = "Low Density"
        elif cluster_id == 1:
            status = "Medium Density"
        else:
            status = "High Density"

        return {
            "person_count": person_count,
            "vehicle_count": vehicle_count,
            "ratio": round(ratio, 2),
            "status": status
        }

# Tes langsung kalau file ini dijalankan
if __name__ == "__main__":
    analyzer = DensityAnalyzer()

    # Uji coba skenario jalanan
    print(analyzer.analyze(person_count=3, vehicle_count=12))  # Harusnya Low
    print(analyzer.analyze(person_count=45, vehicle_count=8))  # Harusnya Anomali!
