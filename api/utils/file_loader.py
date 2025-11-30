import csv
import pandas as pd
from io import StringIO
from openpyxl import load_workbook

def load_question_file(file):
    """
    Helper universal untuk membaca file CSV/XLSX:
    - Auto detect encoding
    - Auto detect delimiter
    - Support UTF-8, Latin1, Windows-1252
    - Support CSV & XLSX
    - Bersihkan NBSP & whitespace
    - Return DataFrame siap pakai
    """

    filename = file.filename.lower()

    # ========= HANDLE XLSX ==========
    if filename.endswith(".xlsx"):
        df = pd.read_excel(file)
        df = _clean_dataframe(df)
        return df

    # ========= HANDLE CSV ==========
    if not filename.endswith(".csv"):
        raise ValueError("File harus berformat CSV atau XLSX")

    # Baca raw bytes
    raw = file.read()

    # Deteksi encoding
    encodings_to_try = ["utf-8", "latin1", "windows-1252"]
    decoded_text = None

    for enc in encodings_to_try:
        try:
            decoded_text = raw.decode(enc)
            break
        except:
            continue

    if decoded_text is None:
        raise UnicodeDecodeError("Gagal decode file CSV dalam semua encoding umum")

    # Auto detect delimiter
    try:
        dialect = csv.Sniffer().sniff(decoded_text[:4096])
        delimiter = dialect.delimiter
    except:
        # fallback default region Indonesia
        delimiter = ";"

    # Baca CSV dengan pandas
    df = pd.read_csv(StringIO(decoded_text), sep=delimiter)

    # Clean
    df = _clean_dataframe(df)

    return df

# ===========================

def _clean_dataframe(df):
    # Bersihkan header kolom: strip, lower, hapus NBSP, hapus BOM
    cleaned_columns = []
    for c in df.columns:
        c = c.replace("\ufeff", "")     # BOM UTF-8
        c = c.replace("\xa0", " ")      # NBSP jadi spasi biasa
        c = c.strip().lower()
        cleaned_columns.append(c)
    df.columns = cleaned_columns

    # Bersihkan isi tabel
    def clean_val(v):
        if isinstance(v, str):
            v = v.replace("\ufeff", "")
            v = v.replace("\xa0", " ")
            return v.strip()
        return v

    return df.applymap(clean_val)

