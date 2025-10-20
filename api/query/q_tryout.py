from datetime import datetime, timedelta
import uuid
import json
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_datetime_uuid, serialize_row
from ..utils.config import get_connection, get_wita


"""#=== query helper ===#"""
def is_valid_batch(id_batch: int):
    engine = get_connection()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM batch WHERE id_batch = :id"), {"id": id_batch}).mappings().fetchone()
        return result is not None

def is_valid_paketkelas(id_paketkelas: int):
    engine = get_connection()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM paketkelas WHERE id_paketkelas = :id"), {"id": id_paketkelas}).mappings().fetchone()
        return result is not None


"""#=== basic CRUD ===#"""
def get_tryout_list_by_user(id_user: int, role: str):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            if role == 'peserta':
                result = conn.execute(text("""
                    SELECT t.*, tp.id_paketkelas, pk.nama_kelas
                    FROM tryout t
                    JOIN to_paketkelas tp ON tp.id_tryout = t.id_tryout
                    JOIN paketkelas pk ON pk.id_paketkelas = tp.id_paketkelas
                    JOIN pesertakelas pu ON tp.id_paketkelas = pu.id_paketkelas
                    WHERE pu.id_user = :id_user AND t.status = 1 AND pk.status = 1 AND pu.status = 1
                    ORDER BY t.created_at DESC
                """), {"id_user": id_user}).mappings().fetchall()
            elif role == 'mentor':
                result = conn.execute(text("""
                    SELECT t.*, tp.id_paketkelas, pk.nama_kelas
                    FROM tryout t
                    JOIN to_paketkelas tp ON tp.id_tryout = t.id_tryout
                    JOIN paketkelas pk ON pk.id_paketkelas = tp.id_paketkelas
                    JOIN mentorkelas pm ON tp.id_paketkelas = pm.id_paketkelas
                    WHERE pm.id_user = :id_user AND t.status = 1 AND pk.status = 1 AND tp.status = 1
                    ORDER BY t.created_at DESC
                """), {"id_user": id_user}).mappings().fetchall()
            else:
                return []
            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"[ERROR get_tryout_list_by_user] {e}")
        return []
    
def get_tryout_list_admin(id_batch=None, id_paketkelas=None):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT
                    t.*,
                    tp.id_paketkelas,
                    pk.nama_kelas,
                    b.id_batch,
                    b.nama_batch
                FROM tryout t
                JOIN to_paketkelas tp ON tp.id_tryout = t.id_tryout AND tp.status = 1
                JOIN paketkelas pk ON pk.id_paketkelas = tp.id_paketkelas AND pk.status = 1
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                WHERE t.status = 1
            """
            params = {}

            if id_batch:
                query += " AND b.id_batch = :id_batch"
                params["id_batch"] = id_batch

            if id_paketkelas:
                query += " AND pk.id_paketkelas = :id_paketkelas"
                params["id_paketkelas"] = id_paketkelas

            query += " ORDER BY t.created_at DESC"

            result = conn.execute(text(query), params).mappings().fetchall()
            raw_data = [serialize_row(row) for row in result]

            # Gabungkan berdasarkan id_tryout
            tryout_map = {}
            for row in raw_data:
                id_tryout = row['id_tryout']
                if id_tryout not in tryout_map:
                    # Salin data dasar + inisialisasi array
                    tryout_map[id_tryout] = {
                        **{k: v for k, v in row.items() if k not in ['id_paketkelas', 'nama_kelas']},
                        "id_paketkelas": [],
                        "nama_kelas": [],
                    }

                # Tambahkan id_paketkelas & nama_kelas jika belum ada
                if row['id_paketkelas'] not in tryout_map[id_tryout]['id_paketkelas']:
                    tryout_map[id_tryout]['id_paketkelas'].append(row['id_paketkelas'])
                if row['nama_kelas'] not in tryout_map[id_tryout]['nama_kelas']:
                    tryout_map[id_tryout]['nama_kelas'].append(row['nama_kelas'])

            return list(tryout_map.values())

    except SQLAlchemyError as e:
        print(f"[ERROR get_tryout_list_admin] {e}")
        return []

def insert_new_tryout(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            q = text("""
                INSERT INTO tryout (judul, jumlah_soal, durasi, max_attempt, status, visibility, created_at, updated_at)
                VALUES (:judul, :jumlah_soal, :durasi, :max_attempt, 1, 'hold', :now, :now)
                RETURNING id_tryout
            """)
            result = conn.execute(q, {
                "judul": payload["judul"],
                "jumlah_soal": payload["jumlah_soal"],
                "durasi": payload["durasi"],
                "max_attempt": payload["max_attempt"],
                "now": get_wita()
            })

            id_tryout = result.scalar()
            return id_tryout
    except SQLAlchemyError as e:
        print(f"[ERROR insert_new_tryout] {e}")
        return None

def assign_tryout_to_classes(id_tryout: int, id_batch: int = None, id_paketkelas_list: list = None):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            kelas_list = []

            if id_batch:
                result = conn.execute(text("""
                    SELECT id_paketkelas FROM paketkelas
                    WHERE id_batch = :id_batch AND status = 1
                """), {"id_batch": id_batch}).mappings().fetchall()
                kelas_list.extend([row["id_paketkelas"] for row in result])

            if id_paketkelas_list:
                kelas_list.extend(id_paketkelas_list)

            # Hilangkan duplikat
            kelas_list = list(set(kelas_list))

            if not kelas_list:
                return False

            for id_paketkelas in kelas_list:
                conn.execute(text("""
                    INSERT INTO to_paketkelas (id_tryout, id_paketkelas, status, created_at, updated_at)
                    VALUES (:id_tryout, :id_paketkelas, 1, :now, :now)
                    ON CONFLICT (id_tryout, id_paketkelas) DO NOTHING
                """), {
                    "id_tryout": id_tryout,
                    "id_paketkelas": id_paketkelas,
                    "now": get_wita()
                })

        return True
    except SQLAlchemyError as e:
        print(f"[ERROR assign_tryout_to_classes] {e}")
        return False

"""#=== Mulai pengerjaan tryout ===#"""
def start_tryout_attempt(id_tryout: int, id_user: int):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # 1. Ambil info tryout (durasi, jumlah soal, max_attempt)
            tryout = conn.execute(text("""
                SELECT id_tryout, jumlah_soal, durasi, max_attempt
                FROM tryout
                WHERE id_tryout = :id_tryout AND status = 1
            """), {"id_tryout": id_tryout}).mappings().first()

            if not tryout:
                return None, "Tryout tidak ditemukan atau tidak aktif"

            # 2. Hitung attempt keberapa untuk user ini
            attempt_ke = conn.execute(text("""
                SELECT COUNT(*) + 1 AS next_attempt
                FROM hasiltryout
                WHERE id_tryout = :id_tryout AND id_user = :id_user AND status = 1
            """), {"id_tryout": id_tryout, "id_user": id_user}).scalar()

            if attempt_ke > tryout["max_attempt"]:
                return None, "Melebihi jumlah attempt yang diperbolehkan"

            # 3. Generate jawaban_user JSON sesuai jumlah_soal
            jawaban_user = {
                f"soal_{i+1}": {"jawaban": None, "ragu": 0, "timestamp": None}
                for i in range(tryout["jumlah_soal"])
            }

            # 4. Tentukan start_time & end_time
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=tryout["durasi"])

            # 5. Generate UUID untuk attempt_token
            attempt_token = str(uuid.uuid4())

            # 6. Insert ke hasiltryout
            result = conn.execute(text("""
                INSERT INTO hasiltryout (
                    id_tryout, id_user, attempt_token, attempt_ke,
                    start_time, end_time, jawaban_user, status_pengerjaan, status
                ) VALUES (
                    :id_tryout, :id_user, :attempt_token, :attempt_ke,
                    :start_time, :end_time, :jawaban_user, 'ongoing', 1
                )
                RETURNING id_hasiltryout, attempt_token, attempt_ke, start_time, end_time
            """), {
                "id_tryout": id_tryout,
                "id_user": id_user,
                "attempt_token": attempt_token,
                "attempt_ke": attempt_ke,
                "start_time": start_time,
                "end_time": end_time,
                "jawaban_user": json.dumps(jawaban_user),
            }).mappings().first()

            return serialize_datetime_uuid(result), None

    except SQLAlchemyError as e:
        print(f"[ERROR start_tryout_attempt] {e}")
        return None, "Gagal memulai attempt"
    
def get_tryout_questions(id_tryout: int, id_user: int):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # 1. Validasi apakah tryout aktif
            tryout = conn.execute(text("""
                SELECT id_tryout, jumlah_soal
                FROM tryout
                WHERE id_tryout = :id_tryout AND status = 1
            """), {"id_tryout": id_tryout}).mappings().first()

            if not tryout:
                return None, "Tryout tidak ditemukan atau tidak aktif"

            # 2. Ambil daftar soal aktif berdasarkan nomor_urut
            questions = conn.execute(text("""
                SELECT id_soaltryout, nomor_urut, pertanyaan, 
                       pilihan_a, pilihan_b, pilihan_c, pilihan_d, pilihan_e
                FROM soaltryout
                WHERE id_tryout = :id_tryout AND status = 1
                ORDER BY nomor_urut ASC
                LIMIT :jumlah
            """), {
                "id_tryout": id_tryout,
                "jumlah": tryout["jumlah_soal"]
            }).mappings().all()

            if not questions:
                return None, "Soal tidak tersedia"

            # 3. Format data agar sederhana
            result = []
            for q in questions:
                result.append({
                    "id_soaltryout": q["id_soaltryout"],
                    "nomor_urut": q["nomor_urut"],
                    "pertanyaan": q["pertanyaan"],
                    "opsi": {
                        "A": q["pilihan_a"],
                        "B": q["pilihan_b"],
                        "C": q["pilihan_c"],
                        "D": q["pilihan_d"],
                        "E": q["pilihan_e"],
                    }
                })

            return result, None

    except SQLAlchemyError as e:
        print(f"[ERROR get_tryout_questions] {e}")
        return None, "Gagal mengambil soal"
    
def get_remaining_attempts(id_tryout: int, id_user: int):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # 1. Ambil data max_attempt dari tryout
            tryout = conn.execute(text("""
                SELECT id_tryout, COALESCE(max_attempt, 0) AS max_attempt
                FROM tryout
                WHERE id_tryout = :id_tryout AND status = 1
                LIMIT 1
            """), {"id_tryout": id_tryout}).mappings().first()

            if not tryout:
                return None, "Tryout tidak ditemukan atau tidak aktif"

            # 2. Hitung jumlah attempt user pada tryout ini
            total_attempt = conn.execute(text("""
                SELECT COUNT(*) AS total
                FROM hasiltryout
                WHERE id_tryout = :id_tryout 
                  AND id_user = :id_user
                  AND status = 1
            """), {
                "id_tryout": id_tryout,
                "id_user": id_user
            }).scalar()

            # 3. Hitung sisa attempt
            remaining = tryout["max_attempt"] - total_attempt
            if remaining < 0:
                remaining = 0

            result = {
                "id_tryout": tryout["id_tryout"],
                "max_attempt": tryout["max_attempt"],
                "total_attempt": total_attempt,
                "remaining_attempts": remaining
            }

            return result, None

    except SQLAlchemyError as e:
        print(f"[ERROR get_remaining_attempts] {e}")
        return None, "Gagal menghitung sisa attempt"
    
def get_attempt_detail(id_tryout: int, id_user: int, attempt_token: str):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # 1. Ambil attempt berdasarkan id_tryout + token
            attempt = conn.execute(text("""
                SELECT id_hasiltryout, id_tryout, id_user, attempt_token, attempt_ke,
                       start_time, end_time, status_pengerjaan
                FROM hasiltryout
                WHERE id_tryout = :id_tryout 
                  AND id_user = :id_user
                  AND attempt_token = :attempt_token
                  AND status = 1
                LIMIT 1
            """), {
                "id_tryout": id_tryout,
                "id_user": id_user,
                "attempt_token": attempt_token
            }).mappings().first()

            if not attempt:
                return None, "Attempt tidak ditemukan"

            # 2. Hitung waktu tersisa (menit)
            waktu_tersisa = 0
            if attempt["status_pengerjaan"] == "ongoing" and attempt["end_time"]:
                now = datetime.now()
                selisih = (attempt["end_time"] - now).total_seconds() // 60
                waktu_tersisa = max(int(selisih), 0)

            # 3. Format response sederhana
            result = {
                "id_hasiltryout": attempt["id_hasiltryout"],
                "id_tryout": attempt["id_tryout"],
                "id_user": attempt["id_user"],
                "attempt_token": str(attempt["attempt_token"]),
                "attempt_ke": attempt["attempt_ke"],
                "start_time": attempt["start_time"],
                "end_time": attempt["end_time"],
                "status_pengerjaan": attempt["status_pengerjaan"],
                "waktu_tersisa": waktu_tersisa
            }

            return serialize_datetime_uuid(result), None

    except SQLAlchemyError as e:
        print(f"[ERROR get_attempt_detail] {e}")
        return None, "Gagal mengambil detail attempt"
