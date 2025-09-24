from datetime import date, datetime
import os
import uuid


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
        return v

    return {k: convert(v) for k, v in dict(row).items()}

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
