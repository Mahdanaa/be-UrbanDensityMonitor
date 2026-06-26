#!/bin/bash
set -e
# Script untuk deploy otomatis

echo "=========================================="
echo "Memulai proses deploy otomatis..."
echo "=========================================="

# 1. Pindah ke root directory (karena script ini ada di folder docker)
cd ..

# 2. Ambil kode terbaru dari git repository
echo "--> Mengambil kode terbaru dari repository..."
git pull origin main

# 3. Jalankan docker-compose up dengan flag --build dan -d (detach mode)
echo "--> Rebuild dan restart container..."
cd docker
docker compose up -d --build

echo "=========================================="
echo "Deploy selesai dengan sukses!"
echo "=========================================="
