from datetime import date, datetime


def is_valid_date(date_str):
    """Cek apakah string sesuai format YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
    
def serialize_row(row):
    return {
        key: value.strftime("%Y-%m-%d") if isinstance(value, (datetime, date)) else value
        for key, value in row.items()
    }