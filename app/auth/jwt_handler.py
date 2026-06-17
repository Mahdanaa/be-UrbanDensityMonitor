import os
import jwt
from jwt import PyJWKClient # <-- Alat baru buat download kunci publik
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

# Baca file .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SECRET_KEY = os.getenv("SUPABASE_JWT_SECRET")

# Siapkan alat untuk otomatis download Kunci Publik ES256 dari Supabase
jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
jwks_client = PyJWKClient(jwks_url)

security = HTTPBearer()

def verify_jwt(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        # 1. Cek dulu, ini tiket jenis baru (ES256) atau lama (HS256)?
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")

        # 2. Proses sesuai jenis tiketnya
        if alg == "ES256":
            # Pakai kunci publik canggih dari internet
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                options={"verify_aud": False}
            )
        else:
            # Pakai cara lama pakai file .env
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )

        return payload # Lolos!

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="❌ Tiket kedaluwarsa! Silakan login ulang.")
    except Exception as e:
        print(f"🚨 ALASAN SATPAM NOLAK TIKET: {str(e)}")
        raise HTTPException(status_code=401, detail="❌ Tiket palsu atau tidak valid!")
