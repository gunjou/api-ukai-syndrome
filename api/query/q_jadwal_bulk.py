import os
import uuid
import tempfile

from io import BytesIO
from datetime import datetime, date, time
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_value
from ..utils.config import get_connection, get_wib



# ============================================================================ #
#                                #ANCHOR - HELPER                              #
# ============================================================================ #

def normalize_text(value):
    """
    Normalisasi text untuk kebutuhan matching.

    Contoh:
        "  Python   Backend "
        "PYTHON BACKEND"
        "python backend"

    menjadi:
        "python backend"
    """

    if value is None:
        return None

    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    # Normalisasi multiple whitespace menjadi satu spasi
    value = " ".join(value.split())

    return value if value else None


def normalize_type_pertemuan(value):
    value = normalize_text(value)

    if value is None:
        return None

    return value.upper()


def parse_bulk_date(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def parse_bulk_time(value):
    if value is None:
        return None

    if isinstance(value, time):
        return value

    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)

    if pd.isna(value):
        return None

    # Excel terkadang memberikan fractional day
    if isinstance(value, (float, int)):
        total_seconds = int(round(float(value) * 24 * 60 * 60))

        hours = (total_seconds // 3600) % 24
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return time(hours, minutes, seconds)

    value = str(value).strip()

    formats = [
        "%H:%M",
        "%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue

    return None


def read_bulk_jadwal_file(file):
    """
    Membaca file CSV atau XLSX dari Flask FileStorage.

    FileStorage dari Werkzeug menggunakan SpooledTemporaryFile.
    Untuk kompatibilitas dengan pandas/openpyxl, file dibaca
    menjadi bytes kemudian dibungkus kembali dengan BytesIO.
    """

    filename = file.filename.lower()

    # Pastikan pointer berada di awal
    file.stream.seek(0)

    # Baca seluruh file menjadi bytes
    file_bytes = file.stream.read()

    if not file_bytes:
        raise ValueError("File kosong")

    # Buat stream standar Python
    file_stream = BytesIO(file_bytes)

    if filename.endswith(".xlsx"):

        df = pd.read_excel(
            file_stream,
            engine="openpyxl",
            dtype=object
        )

    elif filename.endswith(".csv"):

        df = pd.read_csv(
            file_stream,
            dtype=object
        )

    else:
        raise ValueError(
            "Format file harus CSV atau XLSX"
        )

    # Normalisasi nama kolom
    df.columns = [
        normalize_text(column)
        for column in df.columns
    ]

    return df


BULK_JADWAL_REQUIRED_COLUMNS = [
    "nama_kelas",
    "mentor",
    "tanggal",
    "waktu_mulai",
    "waktu_selesai",
    "topik",
    "catatan",
    "type_pertemuan",
]


def validate_bulk_headers(df):
    actual_columns = set(df.columns)

    missing_columns = [
        column
        for column in BULK_JADWAL_REQUIRED_COLUMNS
        if column not in actual_columns
    ]

    return missing_columns


def get_bulk_paketkelas_mapping():
    engine = get_connection()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                id_paketkelas,
                nama_kelas
            FROM paketkelas
            WHERE status = 1
        """)).mappings().fetchall()

    mapping = {}

    for row in result:
        key = normalize_text(row["nama_kelas"])

        if key:
            mapping.setdefault(key, []).append(
                row["id_paketkelas"]
            )

    return mapping


def get_bulk_mentor_mapping():
    engine = get_connection()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                id_user,
                nama,
                nickname
            FROM users
            WHERE role = 'mentor'
              AND status = 1
        """)).mappings().fetchall()

    mapping = {}

    for row in result:
        nama_key = normalize_text(row["nama"])
        nickname_key = normalize_text(row["nickname"])

        if nama_key:
            mapping.setdefault(nama_key, set()).add(
                row["id_user"]
            )

        if nickname_key:
            mapping.setdefault(nickname_key, set()).add(
                row["id_user"]
            )

    return mapping


def get_bulk_mentor_kelas_mapping():
    engine = get_connection()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                id_user,
                id_paketkelas
            FROM mentorkelas
            WHERE status = 1
        """)).fetchall()

    return {
        (row[0], row[1])
        for row in result
    }


def get_existing_jadwal_for_bulk():
    engine = get_connection()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                id_jadwal,
                id_paketkelas,
                id_mentor,
                tanggal,
                waktu_mulai,
                waktu_selesai
            FROM jadwal_kelas
            WHERE status = 1
        """)).mappings().fetchall()

    return result


def is_time_overlap(start_a, end_a, start_b, end_b):
    return (start_a < end_b and end_a > start_b)



# ============================================================================ #
#                            #ANCHOR - QUERY FUNCTION                          #
# ============================================================================ #

def get_bulk_jadwal_template():
    """
    Membuat template XLSX untuk bulk import jadwal.
    """

    columns = [
        "nama_kelas",
        "mentor",
        "tanggal",
        "waktu_mulai",
        "waktu_selesai",
        "topik",
        "catatan",
        "type_pertemuan"
    ]

    example_data = [
        {
            "nama_kelas": "Degirol",
            "mentor": "apt. Suatowijaya, S.Farm.",
            "tanggal": "2026-09-01",
            "waktu_mulai": "09:00",
            "waktu_selesai": "11:00",
            "topik": "Bahan Alam",
            "catatan": "Pertemuan pertama",
            "type_pertemuan": "ONLINE"
        },
        {
            "nama_kelas": "Degirol",
            "mentor": "Kak Suato",
            "tanggal": "2026-09-02",
            "waktu_mulai": "09:00",
            "waktu_selesai": "11:00",
            "topik": "Bahan Alam",
            "catatan": "Pertemuan kedua",
            "type_pertemuan": "OFFLINE"
        }
    ]

    df = pd.DataFrame(
        example_data,
        columns=columns
    )

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".xlsx",
        delete=False
    )

    temp_file.close()

    try:
        with pd.ExcelWriter(
            temp_file.name,
            engine="openpyxl"
        ) as writer:

            df.to_excel(
                writer,
                index=False,
                sheet_name="Jadwal"
            )

            workbook = writer.book
            worksheet = writer.sheets["Jadwal"]

            # ------------------------------------------------------------ #
            # Header
            # ------------------------------------------------------------ #

            for cell in worksheet[1]:
                cell.font = cell.font.copy(
                    bold=True
                )

            # ------------------------------------------------------------ #
            # Width
            # ------------------------------------------------------------ #

            widths = {
                "A": 30,
                "B": 25,
                "C": 15,
                "D": 15,
                "E": 15,
                "F": 30,
                "G": 40,
                "H": 20
            }

            for column, width in widths.items():
                worksheet.column_dimensions[
                    column
                ].width = width

            # ------------------------------------------------------------ #
            # Freeze header
            # ------------------------------------------------------------ #

            worksheet.freeze_panes = "A2"

            # ------------------------------------------------------------ #
            # Auto filter
            # ------------------------------------------------------------ #

            worksheet.auto_filter.ref = (
                worksheet.dimensions
            )

        return temp_file.name

    except Exception:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)

        raise



def validate_bulk_jadwal(file, filename, id_user):
    engine = get_connection()

    import_id = uuid.uuid4()

    now = get_wib()

    try:
        # ================================================================ #
        # READ FILE
        # ================================================================ #

        df = read_bulk_jadwal_file(file)

        if df.empty:
            return {
                "status": "INVALID",
                "import_id": str(import_id),
                "total_rows": 0,
                "valid_rows": 0,
                "invalid_rows": 0,
                "errors": [
                    {
                        "row": 1,
                        "errors": [
                            {
                                "field": "file",
                                "message": "File tidak memiliki data"
                            }
                        ]
                    }
                ]
            }

        # ================================================================ #
        # VALIDATE HEADER
        # ================================================================ #

        missing_columns = validate_bulk_headers(df)

        if missing_columns:
            return {
                "status": "INVALID",
                "import_id": str(import_id),
                "total_rows": len(df),
                "valid_rows": 0,
                "invalid_rows": len(df),
                "errors": [
                    {
                        "row": 1,
                        "errors": [
                            {
                                "field": "header",
                                "message": (
                                    "Kolom wajib tidak ditemukan: "
                                    + ", ".join(missing_columns)
                                )
                            }
                        ]
                    }
                ]
            }

        # ================================================================ #
        # MASTER DATA
        # ================================================================ #

        paketkelas_mapping = get_bulk_paketkelas_mapping()
        mentor_mapping = get_bulk_mentor_mapping()
        mentor_kelas_mapping = get_bulk_mentor_kelas_mapping()

        existing_jadwal = get_existing_jadwal_for_bulk()

        # ================================================================ #
        # VALIDATION RESULT
        # ================================================================ #

        detail_rows = []

        all_errors = []

        total_rows = len(df)
        valid_rows = 0
        invalid_rows = 0

        # Untuk duplicate di dalam file
        file_schedule_keys = {}

        # ================================================================ #
        # LOOP ROW
        # ================================================================ #

        for index, row in df.iterrows():

            row_number = index + 2

            row_errors = []

            # ------------------------------------------------------------ #
            # RAW VALUE
            # ------------------------------------------------------------ #

            nama_kelas_raw = row.get("nama_kelas")
            mentor_raw = row.get("mentor")
            tanggal_raw = row.get("tanggal")
            waktu_mulai_raw = row.get("waktu_mulai")
            waktu_selesai_raw = row.get("waktu_selesai")
            topik_raw = row.get("topik")
            catatan_raw = row.get("catatan")
            type_pertemuan_raw = row.get("type_pertemuan")

            # ------------------------------------------------------------ #
            # NORMALIZE
            # ------------------------------------------------------------ #

            nama_kelas_key = normalize_text(nama_kelas_raw)
            mentor_key = normalize_text(mentor_raw)
            type_pertemuan = normalize_type_pertemuan(
                type_pertemuan_raw
            )

            # ------------------------------------------------------------ #
            # RESOLVE KELAS
            # ------------------------------------------------------------ #

            id_paketkelas = None

            if not nama_kelas_key:
                row_errors.append({
                    "field": "nama_kelas",
                    "message": "Nama kelas wajib diisi"
                })

            else:
                paketkelas_ids = paketkelas_mapping.get(
                    nama_kelas_key,
                    []
                )

                if not paketkelas_ids:
                    row_errors.append({
                        "field": "nama_kelas",
                        "value": nama_kelas_raw,
                        "message": "Paket kelas tidak ditemukan"
                    })

                elif len(paketkelas_ids) > 1:
                    row_errors.append({
                        "field": "nama_kelas",
                        "value": nama_kelas_raw,
                        "message": (
                            "Nama kelas tidak unik di database"
                        )
                    })

                else:
                    id_paketkelas = paketkelas_ids[0]

            # ------------------------------------------------------------ #
            # RESOLVE MENTOR
            # ------------------------------------------------------------ #

            id_mentor = None

            if not mentor_key:
                row_errors.append({
                    "field": "mentor",
                    "message": "Mentor wajib diisi"
                })

            else:
                mentor_ids = mentor_mapping.get(
                    mentor_key,
                    set()
                )

                if not mentor_ids:
                    row_errors.append({
                        "field": "mentor",
                        "value": mentor_raw,
                        "message": "Mentor tidak ditemukan"
                    })

                elif len(mentor_ids) > 1:
                    row_errors.append({
                        "field": "mentor",
                        "value": mentor_raw,
                        "message": (
                            "Mentor tidak unik. "
                            "Gunakan nama lengkap mentor."
                        )
                    })

                else:
                    id_mentor = next(iter(mentor_ids))

            # ------------------------------------------------------------ #
            # RELASI MENTOR - KELAS
            # ------------------------------------------------------------ #

            if (
                id_mentor is not None
                and id_paketkelas is not None
            ):
                if (
                    id_mentor,
                    id_paketkelas
                ) not in mentor_kelas_mapping:

                    row_errors.append({
                        "field": "mentor",
                        "value": mentor_raw,
                        "message": (
                            f'Mentor "{mentor_raw}" '
                            f'tidak terdaftar pada kelas '
                            f'"{nama_kelas_raw}"'
                        )
                    })

            # ------------------------------------------------------------ #
            # DATE
            # ------------------------------------------------------------ #

            tanggal = parse_bulk_date(tanggal_raw)

            if tanggal is None:
                row_errors.append({
                    "field": "tanggal",
                    "value": str(tanggal_raw),
                    "message": (
                        "Tanggal tidak valid. "
                        "Gunakan format YYYY-MM-DD"
                    )
                })

            # ------------------------------------------------------------ #
            # TIME
            # ------------------------------------------------------------ #

            waktu_mulai = parse_bulk_time(
                waktu_mulai_raw
            )

            waktu_selesai = parse_bulk_time(
                waktu_selesai_raw
            )

            if waktu_mulai is None:
                row_errors.append({
                    "field": "waktu_mulai",
                    "value": str(waktu_mulai_raw),
                    "message": "Format waktu_mulai tidak valid"
                })

            if waktu_selesai is None:
                row_errors.append({
                    "field": "waktu_selesai",
                    "value": str(waktu_selesai_raw),
                    "message": "Format waktu_selesai tidak valid"
                })

            if (
                waktu_mulai is not None
                and waktu_selesai is not None
                and waktu_mulai >= waktu_selesai
            ):
                row_errors.append({
                    "field": "waktu_selesai",
                    "message": (
                        "waktu_selesai harus lebih besar "
                        "dari waktu_mulai"
                    )
                })

            # ------------------------------------------------------------ #
            # TYPE PERTEMUAN
            # ------------------------------------------------------------ #

            if type_pertemuan not in [
                "ONLINE",
                "OFFLINE"
            ]:
                row_errors.append({
                    "field": "type_pertemuan",
                    "value": str(type_pertemuan_raw),
                    "message": (
                        "type_pertemuan harus ONLINE atau OFFLINE"
                    )
                })

            # ------------------------------------------------------------ #
            # DUPLICATE / CONFLICT
            # ------------------------------------------------------------ #

            if (
                id_paketkelas is not None
                and id_mentor is not None
                and tanggal is not None
                and waktu_mulai is not None
                and waktu_selesai is not None
                and waktu_mulai < waktu_selesai
            ):

                schedule_key = (
                    id_paketkelas,
                    id_mentor,
                    tanggal,
                    waktu_mulai,
                    waktu_selesai
                )

                # -------------------------------------------------------- #
                # Duplicate dalam file
                # -------------------------------------------------------- #

                if schedule_key in file_schedule_keys:

                    duplicate_row = file_schedule_keys[
                        schedule_key
                    ]

                    row_errors.append({
                        "field": "jadwal",
                        "message": (
                            "Jadwal duplicate dengan "
                            f"row {duplicate_row} "
                            "di dalam file"
                        )
                    })

                else:
                    file_schedule_keys[
                        schedule_key
                    ] = row_number

                # -------------------------------------------------------- #
                # Duplicate / conflict dengan DB
                # -------------------------------------------------------- #

                for existing in existing_jadwal:

                    if (
                        existing["id_paketkelas"]
                        == id_paketkelas
                        and existing["id_mentor"]
                        == id_mentor
                        and existing["tanggal"]
                        == tanggal
                    ):

                        # Exact duplicate
                        if (
                            existing["waktu_mulai"]
                            == waktu_mulai
                            and existing["waktu_selesai"]
                            == waktu_selesai
                        ):
                            row_errors.append({
                                "field": "jadwal",
                                "message": (
                                    "Jadwal sudah terdaftar "
                                    "di database"
                                )
                            })

                            break

                        # Mentor conflict
                        if is_time_overlap(
                            waktu_mulai,
                            waktu_selesai,
                            existing["waktu_mulai"],
                            existing["waktu_selesai"]
                        ):
                            row_errors.append({
                                "field": "jadwal",
                                "message": (
                                    "Jadwal bentrok dengan "
                                    "jadwal mentor yang sudah ada"
                                )
                            })

                            break

            # ------------------------------------------------------------ #
            # RESULT ROW
            # ------------------------------------------------------------ #

            if row_errors:
                status = "INVALID"
                invalid_rows += 1

                all_errors.append({
                    "row": row_number,
                    "errors": row_errors
                })

            else:
                status = "VALID"
                valid_rows += 1

            detail_rows.append({
                "row_number": row_number,

                "nama_kelas_raw": (
                    None
                    if pd.isna(nama_kelas_raw)
                    else str(nama_kelas_raw)
                ),

                "mentor_raw": (
                    None
                    if pd.isna(mentor_raw)
                    else str(mentor_raw)
                ),

                "tanggal_raw": (
                    None
                    if pd.isna(tanggal_raw)
                    else str(tanggal_raw)
                ),

                "waktu_mulai_raw": (
                    None
                    if pd.isna(waktu_mulai_raw)
                    else str(waktu_mulai_raw)
                ),

                "waktu_selesai_raw": (
                    None
                    if pd.isna(waktu_selesai_raw)
                    else str(waktu_selesai_raw)
                ),

                "topik_raw": (
                    None
                    if pd.isna(topik_raw)
                    else str(topik_raw)
                ),

                "catatan_raw": (
                    None
                    if pd.isna(catatan_raw)
                    else str(catatan_raw)
                ),

                "type_pertemuan_raw": (
                    None
                    if pd.isna(type_pertemuan_raw)
                    else str(type_pertemuan_raw)
                ),

                "id_paketkelas": id_paketkelas,
                "id_mentor": id_mentor,

                "tanggal": tanggal,
                "waktu_mulai": waktu_mulai,
                "waktu_selesai": waktu_selesai,

                "type_pertemuan": type_pertemuan,

                "status": status,
                "error_message": row_errors
            })

        # ================================================================ #
        # IMPORT STATUS
        # ================================================================ #

        import_status = (
            "VALID"
            if invalid_rows == 0
            else "INVALID"
        )

        # ================================================================ #
        # SAVE STAGING
        # ================================================================ #

        with engine.begin() as conn:

            conn.execute(text("""
                INSERT INTO jadwal_import (
                    id_import,
                    file_name,
                    status,
                    total_rows,
                    valid_rows,
                    invalid_rows,
                    created_by,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id_import,
                    :file_name,
                    :status,
                    :total_rows,
                    :valid_rows,
                    :invalid_rows,
                    :created_by,
                    :created_at,
                    :updated_at
                )
            """), {
                "id_import": import_id,
                "file_name": filename,
                "status": import_status,
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "created_by": id_user,
                "created_at": now,
                "updated_at": now
            })

            for detail in detail_rows:

                conn.execute(text("""
                    INSERT INTO jadwal_import_detail (
                        id_import,
                        row_number,

                        nama_kelas_raw,
                        mentor_raw,
                        tanggal_raw,
                        waktu_mulai_raw,
                        waktu_selesai_raw,
                        topik_raw,
                        catatan_raw,
                        type_pertemuan_raw,

                        id_paketkelas,
                        id_mentor,

                        tanggal,
                        waktu_mulai,
                        waktu_selesai,
                        type_pertemuan,

                        status,
                        error_message,
                        created_at
                    )
                    VALUES (
                        :id_import,
                        :row_number,

                        :nama_kelas_raw,
                        :mentor_raw,
                        :tanggal_raw,
                        :waktu_mulai_raw,
                        :waktu_selesai_raw,
                        :topik_raw,
                        :catatan_raw,
                        :type_pertemuan_raw,

                        :id_paketkelas,
                        :id_mentor,

                        :tanggal,
                        :waktu_mulai,
                        :waktu_selesai,
                        :type_pertemuan,

                        :status,
                        CAST(:error_message AS JSONB),
                        :created_at
                    )
                """), {
                    "id_import": import_id,
                    **detail,
                    "error_message": (
                        __import__("json").dumps(
                            detail["error_message"]
                        )
                    ),
                    "created_at": now
                })

        # ================================================================ #
        # PREVIEW
        # ================================================================ #

        preview = []

        for detail in detail_rows[:20]:
            preview.append({
                "row": detail["row_number"],
                "nama_kelas": detail["nama_kelas_raw"],
                "mentor": detail["mentor_raw"],
                "id_paketkelas": detail["id_paketkelas"],
                "id_mentor": detail["id_mentor"],
                "tanggal": (
                    detail["tanggal"].isoformat()
                    if detail["tanggal"]
                    else None
                ),
                "waktu_mulai": (
                    detail["waktu_mulai"].strftime("%H:%M:%S")
                    if detail["waktu_mulai"]
                    else None
                ),
                "waktu_selesai": (
                    detail["waktu_selesai"].strftime("%H:%M:%S")
                    if detail["waktu_selesai"]
                    else None
                ),
                "type_pertemuan": detail["type_pertemuan"],
                "status": detail["status"],
                "errors": detail["error_message"]
            })

        return {
            "status": import_status,
            "import_id": str(import_id),
            "total_rows": total_rows,
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "errors": all_errors,
            "preview": preview
        }

    except SQLAlchemyError as e:
        print(f"[validate_bulk_jadwal] Error: {e}")
        raise

    except Exception as e:
        print(f"[validate_bulk_jadwal] Error: {e}")
        raise



def get_bulk_jadwal_import(import_id):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            import_result = conn.execute(text("""
                SELECT
                    id_import,
                    file_name,
                    status,
                    total_rows,
                    valid_rows,
                    invalid_rows,
                    created_by,
                    created_at,
                    updated_at
                FROM jadwal_import
                WHERE id_import = :id_import
            """), {
                "id_import": import_id
            }).mappings().fetchone()

            if not import_result:
                return None

            details = conn.execute(text("""
                SELECT
                    id_detail,
                    row_number,

                    nama_kelas_raw,
                    mentor_raw,
                    tanggal_raw,
                    waktu_mulai_raw,
                    waktu_selesai_raw,
                    topik_raw,
                    catatan_raw,
                    type_pertemuan_raw,

                    id_paketkelas,
                    id_mentor,

                    tanggal,
                    waktu_mulai,
                    waktu_selesai,
                    type_pertemuan,

                    status,
                    error_message
                FROM jadwal_import_detail
                WHERE id_import = :id_import
                ORDER BY row_number ASC
            """), {
                "id_import": import_id
            }).mappings().fetchall()

            return {
                "import": serialize_value(
                    import_result
                ),
                "details": [
                    serialize_value(row)
                    for row in details
                ]
            }

    except SQLAlchemyError as e:
        print(f"[get_bulk_jadwal_import] Error: {e}")
        return None



def commit_bulk_jadwal(import_id, id_user):
    engine = get_connection()

    try:
        with engine.begin() as conn:

            # ============================================================ #
            # LOCK IMPORT
            # ============================================================ #

            import_result = conn.execute(text("""
                SELECT
                    id_import,
                    status,
                    total_rows,
                    valid_rows,
                    invalid_rows
                FROM jadwal_import
                WHERE id_import = :id_import
                FOR UPDATE
            """), {
                "id_import": import_id
            }).mappings().fetchone()

            if not import_result:
                return {
                    "status": "NOT_FOUND"
                }

            # ============================================================ #
            # STATUS CHECK
            # ============================================================ #

            if import_result["status"] == "COMMITTED":
                return {
                    "status": "ALREADY_COMMITTED"
                }

            if import_result["status"] == "INVALID":
                return {
                    "status": "INVALID"
                }

            if import_result["status"] != "VALID":
                return {
                    "status": "INVALID"
                }

            # ============================================================ #
            # GET DETAIL
            # ============================================================ #

            details = conn.execute(text("""
                SELECT
                    id_detail,
                    row_number,
                    id_paketkelas,
                    id_mentor,
                    topik_raw,
                    catatan_raw,
                    tanggal,
                    waktu_mulai,
                    waktu_selesai,
                    type_pertemuan,
                    status
                FROM jadwal_import_detail
                WHERE id_import = :id_import
                ORDER BY row_number ASC
                FOR UPDATE
            """), {
                "id_import": import_id
            }).mappings().fetchall()

            if not details:
                return {
                    "status": "INVALID"
                }

            # ============================================================ #
            # DOUBLE CHECK
            # ============================================================ #

            for detail in details:

                if detail["status"] != "VALID":
                    raise ValueError(
                        f"Row {detail['row_number']} tidak valid"
                    )

                if not detail["id_paketkelas"]:
                    raise ValueError(
                        f"Row {detail['row_number']} "
                        "tidak memiliki id_paketkelas"
                    )

                if not detail["id_mentor"]:
                    raise ValueError(
                        f"Row {detail['row_number']} "
                        "tidak memiliki id_mentor"
                    )

                if not detail["tanggal"]:
                    raise ValueError(
                        f"Row {detail['row_number']} "
                        "tidak memiliki tanggal"
                    )

                if not detail["waktu_mulai"]:
                    raise ValueError(
                        f"Row {detail['row_number']} "
                        "tidak memiliki waktu_mulai"
                    )

                if not detail["waktu_selesai"]:
                    raise ValueError(
                        f"Row {detail['row_number']} "
                        "tidak memiliki waktu_selesai"
                    )

            # ============================================================ #
            # INSERT ALL
            # ============================================================ #

            now = get_wib()

            inserted_rows = 0

            for detail in details:

                result = conn.execute(text("""
                    INSERT INTO jadwal_kelas (
                        id_paketkelas,
                        id_mentor,
                        topik,
                        catatan,
                        tanggal,
                        waktu_mulai,
                        waktu_selesai,
                        type_pertemuan,
                        status,
                        created_by,
                        created_at,
                        updated_by,
                        updated_at
                    )
                    VALUES (
                        :id_paketkelas,
                        :id_mentor,
                        :topik,
                        :catatan,
                        :tanggal,
                        :waktu_mulai,
                        :waktu_selesai,
                        :type_pertemuan,
                        1,
                        :created_by,
                        :created_at,
                        :updated_by,
                        :updated_at
                    )
                    RETURNING id_jadwal
                """), {
                    "id_paketkelas": detail["id_paketkelas"],
                    "id_mentor": detail["id_mentor"],
                    "topik": detail["topik_raw"],
                    "catatan": detail["catatan_raw"],
                    "tanggal": detail["tanggal"],
                    "waktu_mulai": detail["waktu_mulai"],
                    "waktu_selesai": detail["waktu_selesai"],
                    "type_pertemuan": detail["type_pertemuan"],
                    "created_by": id_user,
                    "created_at": now,
                    "updated_by": id_user,
                    "updated_at": now
                }).scalar()

                if not result:
                    raise SQLAlchemyError(
                        f"Gagal insert row "
                        f"{detail['row_number']}"
                    )

                inserted_rows += 1

            # ============================================================ #
            # UPDATE IMPORT STATUS
            # ============================================================ #

            conn.execute(text("""
                UPDATE jadwal_import
                SET
                    status = 'COMMITTED',
                    updated_at = :updated_at
                WHERE id_import = :id_import
            """), {
                "id_import": import_id,
                "updated_at": now
            })

            return {
                "status": "COMMITTED",
                "total_rows": import_result["total_rows"],
                "inserted_rows": inserted_rows
            }

    except SQLAlchemyError as e:
        print(f"[commit_bulk_jadwal] Error: {e}")
        raise

    except Exception as e:
        print(f"[commit_bulk_jadwal] Error: {e}")
        raise

