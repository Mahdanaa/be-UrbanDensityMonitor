import numpy as np
from sklearn.cluster import KMeans
import pickle
import os

print("👨‍🏫 Membuka Kelas Pelatihan untuk Manajer AI di Laptop Lokal...")

data_normal = np.array([
    [2, 5], [5, 10], [8, 12], [4, 8],
    [15, 30], [20, 35], [25, 40], [18, 28],
    [40, 80], [50, 100], [60, 120], [80, 150]
])

ratios = data_normal[:, 0] / data_normal[:, 1]
ratios = ratios.reshape(-1, 1)

X_train = np.column_stack((data_normal, ratios))

print("🧠 Sedang menyusun rumus pola kemacetan (K-Means)...")
kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
kmeans.fit(X_train)

os.makedirs("app/models", exist_ok=True)
with open("app/models/density_cluster_model.pkl", "wb") as f:
    pickle.dump(kmeans, f)

print("✅ BUKU PANDUAN BARU (.pkl) VERSI LOKAL SUDAH BERHASIL DICETAK!")
