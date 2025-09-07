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