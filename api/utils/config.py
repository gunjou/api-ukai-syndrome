import os
import pytz
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine


load_dotenv()

# === Konfigurasi CDN === #
CDN_UPLOAD_URL = os.getenv("CDN_UPLOAD_URL")
CDN_API_KEY = os.getenv("CDN_API_KEY")


# === Konfigurasi Database === #
host = os.getenv("DB_HOST", "localhost")
port = os.getenv("DB_PORT", "5432")
dbname = os.getenv("DB_NAME")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASS")

DATABASE_URL = f'postgresql+psycopg2://{username}:{password}@{host}:{port}/{dbname}'

# ⛽️ Engine dibuat sekali dan dipakai ulang (pool aman)
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True  # opsional tapi direkomendasikan
)

def get_connection():
    return engine

# === Mencari Timestamp WITA === #
def get_wita():
    # wita = pytz.timezone('Asia/Makassar')
    wib = pytz.timezone('Asia/Jakarta')
    now_wita = datetime.now(wib)
    return now_wita.replace(tzinfo=None)