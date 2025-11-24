from datetime import datetime, timedelta
import uuid
import json
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_datetime_uuid, serialize_row, serialize_value
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
    
def get_tryout_by_id(id_tryout: int):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM tryout
                WHERE id_tryout = :id_tryout AND status = 1
            """), {"id_tryout": id_tryout}).mappings().fetchone()
            
            return result  # Kembalikan data tryout jika ditemukan, atau None jika tidak
    except SQLAlchemyError as e:
        print(f"[ERROR get_tryout_by_id] {e}")
        return None
    
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
                LEFT JOIN to_paketkelas tp ON tp.id_tryout = t.id_tryout AND tp.status = 1
                LEFT JOIN paketkelas pk ON pk.id_paketkelas = tp.id_paketkelas AND pk.status = 1
                LEFT JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
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
    
def update_tryout(id_tryout, payload):
    engine = get_connection()
    now = get_wita()
    try:
        with engine.begin() as conn:
            # Cek apakah tryout ada
            q_check = text("SELECT id_tryout FROM tryout WHERE id_tryout = :id_tryout AND status = 1")
            exists = conn.execute(q_check, {"id_tryout": id_tryout}).fetchone()
            if not exists:
                return {"success": False, "message": "Tryout tidak ditemukan atau sudah dihapus"}

            # Buat field dinamis hanya untuk kolom yang dikirim
            fields = []
            params = {"id_tryout": id_tryout, "updated_at": now}
            for key in ["judul", "jumlah_soal", "durasi", "max_attempt", "visibility"]:
                value = payload.get(key)
                if value is not None:
                    fields.append(f"{key} = :{key}")
                    params[key] = value

            if not fields:
                return {"success": False, "message": "Tidak ada data yang diubah"}

            q_update = text(f"""
                UPDATE tryout
                SET {', '.join(fields)}, updated_at = :updated_at
                WHERE id_tryout = :id_tryout
            """)
            conn.execute(q_update, params)

            return {"success": True, "message": "Data tryout berhasil diperbarui"}

    except SQLAlchemyError as e:
        print(f"[ERROR update_tryout] {e}")
        return {"success": False, "message": "Terjadi kesalahan pada database"}
    
def soft_delete_tryout(id_tryout: int):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # Update status menjadi 0 (soft delete)
            result = conn.execute(text("""
                UPDATE tryout
                SET status = 0, updated_at = NOW()
                WHERE id_tryout = :id_tryout AND status = 1
            """), {"id_tryout": id_tryout})
            
            # Jika ada baris yang terupdate, berarti berhasil
            if result.rowcount > 0:
                return True
            else:
                return False
    except SQLAlchemyError as e:
        print(f"[ERROR soft_delete_tryout] {e}")
        return False

def update_tryout_visibility(id_tryout: int, visibility: str):
    engine = get_connection()
    now = get_wita()
    try:
        with engine.begin() as conn:
            # Cek apakah tryout ada
            q_check = text("SELECT id_tryout FROM tryout WHERE id_tryout = :id_tryout AND status = 1")
            exists = conn.execute(q_check, {"id_tryout": id_tryout}).fetchone()
            if not exists:
                return {"success": False, "message": "Tryout tidak ditemukan atau sudah dihapus"}

            # Update visibility
            q_update = text("""
                UPDATE tryout
                SET visibility = :visibility,
                    updated_at = :updated_at
                WHERE id_tryout = :id_tryout
            """)
            conn.execute(q_update, {
                "id_tryout": id_tryout,
                "visibility": visibility,
                "updated_at": now
            })

            return {"success": True, "message": f"Visibility tryout berhasil diubah menjadi '{visibility}'"}

    except SQLAlchemyError as e:
        print(f"[ERROR update_tryout_visibility] {e}")
        return {"success": False, "message": "Terjadi kesalahan pada database"}

"""#=== Mulai pengerjaan tryout ===#"""
def start_tryout_attempt(id_tryout: int, id_user: int):
    engine = get_connection()
    try:
        with engine.begin() as conn:

            # 1. Ambil info tryout
            tryout = conn.execute(text("""
                SELECT id_tryout, jumlah_soal, durasi, max_attempt
                FROM tryout
                WHERE id_tryout = :id_tryout AND status = 1
            """), {"id_tryout": id_tryout}).mappings().first()

            if not tryout:
                return None, "Tryout tidak ditemukan atau tidak aktif", 400

            # 2. Cek attempt terakhir (status aktif atau submitted)
            last_attempt = conn.execute(text("""
                SELECT *
                FROM hasiltryout
                WHERE id_tryout = :id_tryout AND id_user = :id_user AND status = 1
                ORDER BY id_hasiltryout DESC
                LIMIT 1
            """), {
                "id_tryout": id_tryout,
                "id_user": id_user
            }).mappings().first()

            # --- CASE A: Ada attempt ongoing ---
            if last_attempt and last_attempt["status_pengerjaan"] == "ongoing":

                now = datetime.now()
                # Case A1: Sudah lewat end_time → forced submitted → buat baru
                end_time = last_attempt.get("end_time")
                # Jika end_time tidak ada / None → anggap belum diset, treat sebagai ongoing
                if end_time is None:
                    return serialize_datetime_uuid(last_attempt), "Melanjutkan attempt yang masih aktif.", 200
                # Jika waktu sekarang > end_time → expired
                if now > end_time:
                    # update menjadi submitted
                    submit_tryout_attempt(last_attempt["attempt_token"], id_user)
                    # conn.execute(text("""
                    #     UPDATE hasiltryout
                    #     SET status_pengerjaan = 'submitted', updated_at = NOW()
                    #     WHERE id_hasiltryout = :id_hasiltryout
                    # """), {"id_hasiltryout": last_attempt["id_hasiltryout"]})

                    # buat attempt baru
                    new_attempt, _ = _create_new_attempt(conn, tryout, id_tryout, id_user)
                    return new_attempt, "Attempt sebelumnya sudah lewat waktu. Membuat attempt baru.", 201

                # Case A2: Masih ongoing dan masih ada waktu → lanjutkan
                return serialize_datetime_uuid(last_attempt), "Melanjutkan attempt yang masih aktif.", 200

            # --- CASE B: Ada attempt namun status_pengerjaan=submitted → buat baru ---
            if last_attempt and last_attempt["status_pengerjaan"] == "submitted":
                new_attempt, _ = _create_new_attempt(conn, tryout, id_tryout, id_user)
                return new_attempt, "Attempt sebelumnya sudah disubmit. Membuat attempt baru.", 201

            # --- CASE C: Tidak ada attempt sama sekali → attempt baru ---
            new_attempt, _ = _create_new_attempt(conn, tryout, id_tryout, id_user)
            return new_attempt, "Memulai attempt pertama atau tidak ada attempt aktif.", 201

    except SQLAlchemyError as e:
        print(f"[ERROR start_tryout_attempt] {e}")
        return None, "Gagal memulai attempt", 500


# =================================================================
# Helper untuk membuat attempt baru
# =================================================================
def _create_new_attempt(conn, tryout, id_tryout, id_user):
    # Hitung attempt keberapa
    attempt_ke = conn.execute(text("""
        SELECT COUNT(*) + 1 AS next_attempt
        FROM hasiltryout
        WHERE id_tryout = :id_tryout AND id_user = :id_user AND status = 1
    """), {"id_tryout": id_tryout, "id_user": id_user}).scalar()

    if attempt_ke > tryout["max_attempt"]:
        return None, "Melebihi jumlah attempt yang diperbolehkan"

    # generate template jawaban_user
    jawaban_user = {
        f"soal_{i+1}": {"jawaban": None, "ragu": 0, "timestamp": None}
        for i in range(tryout["jumlah_soal"])
    }

    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=tryout["durasi"])
    attempt_token = str(uuid.uuid4())

    result = conn.execute(text("""
        INSERT INTO hasiltryout (
            id_tryout, id_user, attempt_token, attempt_ke,
            start_time, end_time, jawaban_user,
            status_pengerjaan, status
        ) VALUES (
            :id_tryout, :id_user, :attempt_token, :attempt_ke,
            :start_time, :end_time, :jawaban_user,
            'ongoing', 1
        )
        RETURNING id_hasiltryout, attempt_token, attempt_ke, start_time, end_time, jawaban_user
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

def save_tryout_answer(attempt_token: str, id_user: int, nomor_soal: int, jawaban: str = None, ragu: int = 0, ts: datetime = None):
    """
    Update jawaban_user untuk sebuah attempt berdasarkan attempt_token.
    - nomor_soal: angka 1..N (1-based)
    - jawaban: nilai jawaban (misal "A" / "B" / "C" / "D" / "E" / string)
    - ragu: 0 atau 1
    - ts: datetime ketika menjawab; jika None => sekarang (get_wita())
    Returns: dict(updated_row) on success or (None, "message") on error
    """
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # Ambil attempt sesuai token
            row = conn.execute(text("""
                SELECT id_hasiltryout, id_user, jawaban_user, status_pengerjaan, end_time, start_time
                FROM hasiltryout
                WHERE attempt_token = :attempt_token AND status = 1
                LIMIT 1
            """), {"attempt_token": attempt_token}).mappings().fetchone()

            if not row:
                return None, "Attempt tidak ditemukan"

            # Pastikan pemiliknya sama
            if int(row["id_user"]) != int(id_user):
                return None, "Token tidak valid untuk user ini"

            # Pastikan status pengerjaan ongoing
            if row["status_pengerjaan"] != "ongoing":
                return None, "Attempt bukan dalam status ongoing"

            now = ts if ts is not None else get_wita()

            # Cek apakah sudah melewati end_time
            end_time = row["end_time"]
            if end_time is not None and now > end_time:
                # Bisa langsung set status ke 'time_up' atau 'submitted' sesuai kebijakan
                conn.execute(text("""
                    UPDATE hasiltryout
                    SET status_pengerjaan = 'time_up', updated_at = :now
                    WHERE id_hasiltryout = :id_hasiltryout
                """), {"now": now, "id_hasiltryout": row["id_hasiltryout"]})
                return None, "Waktu attempt telah habis"

            # Ambil JSON jawaban_user (bisa None atau JSON)
            jawaban_user = row["jawaban_user"] or {}
            # Pastikan jawaban_user adalah dict
            if isinstance(jawaban_user, str):
                try:
                    jawaban_user = json.loads(jawaban_user)
                except Exception:
                    jawaban_user = {}

            soal_key = f"soal_{int(nomor_soal)}"
            # Jika belum ada struktur soal_key, buat default
            if soal_key not in jawaban_user or not isinstance(jawaban_user[soal_key], dict):
                jawaban_user[soal_key] = {"jawaban": None, "ragu": 0, "timestamp": None}

            # Update nilai
            jawaban_user[soal_key]["jawaban"] = jawaban if jawaban is not None else jawaban_user[soal_key].get("jawaban")
            jawaban_user[soal_key]["ragu"] = int(ragu) if ragu is not None else jawaban_user[soal_key].get("ragu", 0)
            # Simpan timestamp dalam ISO format
            jawaban_user[soal_key]["timestamp"] = now.isoformat()

            # Tulis kembali ke DB
            conn.execute(text("""
                UPDATE hasiltryout
                SET jawaban_user = :jawaban_user, updated_at = :now
                WHERE id_hasiltryout = :id_hasiltryout
            """), {
                "jawaban_user": json.dumps(jawaban_user),
                "now": now,
                "id_hasiltryout": row["id_hasiltryout"]
            })

            # Kembalikan jawaban_user yang sudah diupdate
            # return jawaban_user, None
            return True, None

    except SQLAlchemyError as e:
        print(f"[save_tryout_answer] Error: {e}")
        return None, "Internal server error"

# query/q_tryout.py
def submit_tryout_attempt(attempt_token: str, id_user: int):
    """
    Submit sebuah attempt berdasarkan attempt_token.
    Mengembalikan dict hasil (nilai, benar, salah, kosong, ragu_ragu, total_soal, attempt_ke, id_hasiltryout)
    Aturan:
    - Validasi attempt ada dan status=1
    - Validasi owner id_user sama dengan row.id_user
    - Terlepas dari end_time, submit tetap diproses
    - Jika sudah submitted sebelumnya -> kembalikan error
    """
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # 1) Ambil attempt
            row = conn.execute(text("""
                SELECT h.id_hasiltryout, h.id_tryout, h.id_user, h.jawaban_user, h.status_pengerjaan, h.attempt_ke
                FROM hasiltryout h
                WHERE h.attempt_token = :attempt_token AND h.status = 1
                LIMIT 1
            """), {"attempt_token": attempt_token}).mappings().fetchone()

            if not row:
                return None, "Attempt tidak ditemukan"

            if int(row["id_user"]) != int(id_user):
                return None, "Token tidak valid untuk user ini"

            if row["status_pengerjaan"] == "submitted":
                return None, "Attempt sudah disubmit sebelumnya"

            id_hasiltryout = row["id_hasiltryout"]
            id_tryout = row["id_tryout"]
            jawaban_user = row["jawaban_user"] or {}
            # jika disimpan sebagai string JSON, parse
            if isinstance(jawaban_user, str):
                try:
                    jawaban_user = json.loads(jawaban_user)
                except Exception:
                    jawaban_user = {}

            # 2) Ambil kunci jawaban untuk tryout ini
            soal_rows = conn.execute(text("""
                SELECT nomor_urut, jawaban_benar
                FROM soaltryout
                WHERE id_tryout = :id_tryout AND status = 1
                ORDER BY nomor_urut
            """), {"id_tryout": id_tryout}).mappings().fetchall()

            if not soal_rows:
                return None, "Soal tryout tidak ditemukan"

            total_soal = len(soal_rows)
            benar = 0
            salah = 0
            kosong = 0
            ragu_ragu = 0

            # 3) Loop dan hitung
            for soal in soal_rows:
                nomor = int(soal["nomor_urut"])
                kunci = (soal["jawaban_benar"] or "").strip()
                key = f"soal_{nomor}"
                user_ans_obj = jawaban_user.get(key) if isinstance(jawaban_user, dict) else None

                # Normalisasi jawaban user jika ada
                user_answer = None
                user_ragu = 0
                if isinstance(user_ans_obj, dict):
                    # struktur expected: {"jawaban":..., "ragu":0/1, "timestamp": ...}
                    user_answer = user_ans_obj.get("jawaban")
                    user_ragu = int(user_ans_obj.get("ragu", 0) or 0)
                else:
                    # jawaban_user mungkin disimpan sebagai {"soal_1": "A"} (simple) — handle fallback
                    user_answer = user_ans_obj
                    user_ragu = 0

                # Normalisasi string
                if user_answer is None or str(user_answer).strip() == "" or str(user_answer).lower() == "none":
                    kosong += 1
                else:
                    ua = str(user_answer).strip().upper()
                    kb = str(kunci).strip().upper()
                    if kb == "" or kb.lower() == "none":
                        # jika kunci kosong, anggap tidak ada soal (treat as kosong)
                        kosong += 1
                    elif ua == kb:
                        benar += 1
                    else:
                        salah += 1

                if user_ragu:
                    ragu_ragu += 1

            # 4) Hitung nilai (skala 0-100)
            nilai = 0.0
            if total_soal > 0:
                nilai = round((benar / total_soal) * 100, 2)

            now = get_wita()

            # 5) Update hasiltryout
            conn.execute(text("""
                UPDATE hasiltryout
                SET nilai = :nilai,
                    benar = :benar,
                    salah = :salah,
                    kosong = :kosong,
                    ragu_ragu = :ragu_ragu,
                    status_pengerjaan = 'submitted',
                    tanggal_pengerjaan = :tanggal_pengerjaan,
                    updated_at = :now
                WHERE id_hasiltryout = :id_hasiltryout
            """), {
                "nilai": nilai,
                "benar": benar,
                "salah": salah,
                "kosong": kosong,
                "ragu_ragu": ragu_ragu,
                "tanggal_pengerjaan": now,
                "now": now,
                "id_hasiltryout": id_hasiltryout
            })

            # 6) Kembalikan ringkasan
            return {
                "id_hasiltryout": id_hasiltryout,
                "id_tryout": id_tryout,
                "attempt_ke": row["attempt_ke"],
                "total_soal": total_soal,
                "benar": benar,
                "salah": salah,
                "kosong": kosong,
                "ragu_ragu": ragu_ragu,
                "nilai": nilai,
                "tanggal_pengerjaan": now.isoformat()
            }, None

    except SQLAlchemyError as e:
        print(f"[submit_tryout_attempt] Error: {e}")
        return None, "Internal server error"
