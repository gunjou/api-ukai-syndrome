from decimal import Decimal
import os
import uuid
from datetime import date, datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def is_valid_date(date_str):
    """Cek apakah string sesuai format YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
    
def serialize_row(row):
    if not hasattr(row, "items"):
        return row  # atau raise error/logging
    return {
        key: value.strftime("%Y-%m-%d") if isinstance(value, (datetime, date)) else value
        for key, value in row.items()
    }

def serialize_datetime_uuid(row):
    def convert(v):
        if isinstance(v, uuid.UUID):
            return str(v)
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, Decimal):
            # kalau mau float:
            return float(v)
            # atau kalau mau int: return int(v)
        return v

    return {k: convert(v) for k, v in dict(row).items()}

def serialize_value(obj):
    if isinstance(obj, list):
        return [serialize_value(item) for item in obj]
    if isinstance(obj, dict):
        return {k: serialize_value(v) for k, v in obj.items()}
    # SQLAlchemy RowMapping
    from sqlalchemy.engine import RowMapping
    if isinstance(obj, RowMapping):
        return {k: serialize_value(v) for k, v in dict(obj).items()}
    # Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    # UUID
    if isinstance(obj, uuid.UUID):
        return str(obj)
    # Datetime
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def serialize_row_datetime(row):
    return {
        key: value.isoformat() if isinstance(value, (datetime, date)) else value
        for key, value in row.items()
    }

def get_project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

def get_sample_file(filename):
    return os.path.join(get_project_root(), "template_files", filename)

from datetime import datetime

def generate_judul(payload):
    # Format tanggal ke dd Mon yy (misal 26 Agu 25)
    tanggal_obj = datetime.strptime(payload["tanggal"], "%Y-%m-%d")
    tanggal_str = tanggal_obj.strftime("%d %b %y")  # ex: "26 Aug 25"
    tanggal_str = tanggal_str.replace("Aug", "Agu")  # lokalize kalau perlu
    
    nickname = payload["nickname_mentor"]
    modul = payload["nama_modul"]

    # default akhir judul kosong
    suffix = ""

    if payload["tipe_materi"] == "document":
        suffix = ""  # tidak ada tambahan
    elif payload["tipe_materi"] == "video":
        tipe_video = payload.get("tipe_video")
        if tipe_video == "full":
            suffix = ""  # sama seperti document
        elif tipe_video and tipe_video.startswith("part"):
            suffix = f"_{tipe_video}"  # misal: part_1, part_2
        elif tipe_video == "terjeda":
            time_str = payload.get("time")
            suffix = f"_part_{time_str}" if time_str else ""
    
    judul = f"{tanggal_str}_{nickname}_{modul}{suffix}"
    return judul


def generate_excel_hasiltryout(id_tryout: int, data: list):
    df = pd.DataFrame(data)

    temp_path = f"/tmp/export_tryout_{id_tryout}_{datetime.now().timestamp()}.xlsx"
    df.to_excel(temp_path, index=False)

    return temp_path


def generate_pdf_hasiltryout(id_tryout: int, data: list):
    temp_path = f"/tmp/export_tryout_{id_tryout}.pdf"
    c = canvas.Canvas(temp_path, pagesize=letter)

    y = 750
    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, y, f"Laporan Hasil Tryout ID {id_tryout}")
    y -= 30

    c.setFont("Helvetica", 10)

    for row in data:
        text = f"{row['nama_user']} | Nilai: {row['nilai']} | Benar: {row['benar']} | Salah: {row['salah']} | Kosong: {row['kosong']}"
        c.drawString(30, y, text)
        y -= 20

        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = 750

    c.save()
    return temp_path
