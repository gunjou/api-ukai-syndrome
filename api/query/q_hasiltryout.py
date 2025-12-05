from datetime import datetime, timedelta
import uuid
import json
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_datetime_uuid, serialize_row, serialize_value
from ..utils.config import get_connection, get_wita


def get_statistik_by_tryout(id_tryout: int):
    """
    Mengambil statistik untuk satu tryout berdasarkan id_tryout.
    """
    engine = get_connection()

    try:
        with engine.connect() as conn:
            query = text("""
                SELECT
                    COUNT(*) AS total_attempt,
                    COUNT(DISTINCT id_user) AS total_peserta,
                    AVG(nilai) AS rata_rata_nilai,
                    AVG(benar) AS rata_rata_benar,
                    AVG(salah) AS rata_rata_salah,
                    AVG(kosong) AS rata_rata_kosong,
                    SUM(CASE WHEN status_pengerjaan = 'selesai' THEN 1 ELSE 0 END) AS total_selesai,
                    SUM(CASE WHEN status_pengerjaan != 'selesai' THEN 1 ELSE 0 END) AS total_belum_selesai
                FROM hasiltryout
                WHERE status = 1 AND id_tryout = :id_tryout
            """)

            result = conn.execute(query, {"id_tryout": id_tryout}).mappings().fetchone()

            if not result:
                return None

            return {
                "id_tryout": id_tryout,
                "total_attempt": result["total_attempt"] or 0,
                "total_peserta": result["total_peserta"] or 0,
                "rata_rata_nilai": float(result["rata_rata_nilai"] or 0),
                "rata_rata_benar": float(result["rata_rata_benar"] or 0),
                "rata_rata_salah": float(result["rata_rata_salah"] or 0),
                "rata_rata_kosong": float(result["rata_rata_kosong"] or 0),
                "total_selesai": int(result["total_selesai"] or 0),
                "total_belum_selesai": int(result["total_belum_selesai"] or 0),
            }

    except SQLAlchemyError as e:
        print(f"[ERROR get_statistik_by_tryout] {e}")
        return None
    
def get_hasiltryout_list(filters: dict):
    """
    Mengambil daftar hasil tryout dengan filter dinamis.
    """
    engine = get_connection()

    try:
        with engine.connect() as conn:

            base_query = """
                SELECT
                    h.id_hasiltryout, h.id_tryout, h.id_user, h.attempt_token, h.attempt_ke, h.start_time, 
                    h.end_time, h.tanggal_pengerjaan, h.nilai, h.benar, h.salah, h.kosong, 
                    h.ragu_ragu, h.status_pengerjaan,
                    u.nama AS nama_user,
                    u.nickname,
                    t.judul AS judul_tryout
                FROM hasiltryout h
                LEFT JOIN users u ON u.id_user = h.id_user
                LEFT JOIN tryout t ON t.id_tryout = h.id_tryout
                WHERE h.status = 1
            """

            params = {}

            # === FILTERS DINAMIS ===
            if filters.get("id_tryout"):
                base_query += " AND h.id_tryout = :id_tryout"
                params["id_tryout"] = filters["id_tryout"]

            if filters.get("id_user"):
                base_query += " AND h.id_user = :id_user"
                params["id_user"] = filters["id_user"]

            if filters.get("tanggal_mulai"):
                base_query += " AND h.tanggal_pengerjaan >= :tanggal_mulai"
                params["tanggal_mulai"] = filters["tanggal_mulai"]

            if filters.get("tanggal_akhir"):
                base_query += " AND h.tanggal_pengerjaan <= :tanggal_akhir"
                params["tanggal_akhir"] = filters["tanggal_akhir"]

            if filters.get("attempt_ke"):
                base_query += " AND h.attempt_ke = :attempt_ke"
                params["attempt_ke"] = filters["attempt_ke"]

            if filters.get("nilai_min") is not None:
                base_query += " AND h.nilai >= :nilai_min"
                params["nilai_min"] = filters["nilai_min"]

            if filters.get("nilai_max") is not None:
                base_query += " AND h.nilai <= :nilai_max"
                params["nilai_max"] = filters["nilai_max"]

            if filters.get("status_pengerjaan"):
                base_query += " AND h.status_pengerjaan = :status_pengerjaan"
                params["status_pengerjaan"] = filters["status_pengerjaan"]

            # urutkan berdasarkan waktu pengerjaan terbaru
            base_query += " AND h.status = 1 ORDER BY h.tanggal_pengerjaan DESC, h.start_time DESC"

            result = conn.execute(text(base_query), params).mappings().fetchall()

            return [serialize_datetime_uuid(row) for row in result]

    except SQLAlchemyError as e:
        print(f"[ERROR get_hasiltryout_list] {e}")
        return []
    
def get_detail_hasiltryout(id_hasiltryout: int):
    """
    Mengambil detail 1 hasil tryout (1 attempt).
    """
    engine = get_connection()

    try:
        with engine.connect() as conn:
            query = text("""
                SELECT
                    h.*,
                    
                    -- user info
                    u.nama AS nama_user,
                    u.nickname AS nickname_user,
                    u.email AS email_user,

                    -- tryout info
                    t.judul AS judul_tryout,
                    t.jumlah_soal,
                    t.durasi,
                    t.max_attempt

                FROM hasiltryout h
                LEFT JOIN users u ON u.id_user = h.id_user
                LEFT JOIN tryout t ON t.id_tryout = h.id_tryout
                WHERE h.id_hasiltryout = :id_hasiltryout
                  AND h.status = 1
            """)

            result = conn.execute(query, {"id_hasiltryout": id_hasiltryout}).mappings().fetchone()

            if not result:
                return None

            return serialize_datetime_uuid(result)

    except SQLAlchemyError as e:
        print(f"[ERROR get_detail_hasiltryout] {e}")
        return None


def get_leaderboard_tryout(id_tryout: int, limit: int | None = None):
    """
    Leaderboard berdasarkan attempt pertama valid dari setiap user.
    Attempt pertama = id_hasiltryout terkecil dengan status submitted.
    """
    engine = get_connection()

    try:
        with engine.connect() as conn:

            query = text(f"""
                WITH first_attempt AS (
                    SELECT 
                        h.id_hasiltryout,
                        h.id_user,
                        h.id_tryout,
                        h.nilai,
                        h.benar,
                        h.salah,
                        h.kosong,
                        h.start_time,
                        h.end_time,
                        h.tanggal_pengerjaan,
                        ROW_NUMBER() OVER (
                            PARTITION BY h.id_user 
                            ORDER BY h.id_hasiltryout ASC
                        ) AS rn
                    FROM hasiltryout h
                    WHERE 
                        h.status = 1
                        AND h.status_pengerjaan = 'submitted'
                        AND h.id_tryout = :id_tryout
                )
                SELECT 
                    f.*,
                    u.nama AS nama_user,
                    u.nickname,
                    u.email
                FROM first_attempt f
                LEFT JOIN users u ON u.id_user = f.id_user
                WHERE f.rn = 1
                ORDER BY f.nilai DESC, (f.end_time - f.start_time) ASC
                { "LIMIT :limit" if limit is not None else "" }
            """)
            params = {"id_tryout": id_tryout}
            if limit is not None:
                params["limit"] = limit
            rows = conn.execute(query, params).mappings().fetchall()
            if not rows:
                return None
            return [serialize_value(row) for row in rows]
    except SQLAlchemyError as e:
        print(f"[ERROR get_leaderboard_tryout] {e}")
        return None



def get_rekap_tryout_user(id_user: int, id_tryout: int = None):
    """
    Mengambil semua tryout yang pernah dikerjakan user.
    Bisa difilter berdasarkan id_tryout.
    """
    engine = get_connection()

    try:
        with engine.connect() as conn:

            base_query = """
                SELECT
                    h.id_hasiltryout,
                    h.id_tryout,
                    t.judul AS judul_tryout,
                    h.attempt_ke,
                    h.tanggal_pengerjaan,
                    h.start_time,
                    h.end_time,
                    h.nilai,
                    h.benar,
                    h.salah,
                    h.kosong,
                    h.status_pengerjaan
                FROM hasiltryout h
                LEFT JOIN tryout t ON t.id_tryout = h.id_tryout
                WHERE h.status = 1
                  AND h.id_user = :id_user
            """

            params = {"id_user": id_user}

            if id_tryout:
                base_query += " AND h.id_tryout = :id_tryout"
                params["id_tryout"] = id_tryout

            base_query += " ORDER BY h.tanggal_pengerjaan DESC, h.start_time DESC"

            result = conn.execute(text(base_query), params).mappings().fetchall()

            return [serialize_datetime_uuid(r) for r in result]

    except SQLAlchemyError as e:
        print(f"[ERROR get_rekap_tryout_user] {e}")
        return None


def get_hasiltryout_by_tryout(id_tryout: int):
    """
    Mengambil semua hasil dari satu tryout.
    """
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT
                    h.*,
                    u.nama AS nama_user,
                    u.nickname
                FROM hasiltryout h
                LEFT JOIN users u ON u.id_user = h.id_user
                WHERE h.status = 1 AND h.id_tryout = :id_tryout
                ORDER BY h.nilai DESC, h.benar DESC
            """)
            result = conn.execute(query, {"id_tryout": id_tryout}).mappings().fetchall()
            return [serialize_datetime_uuid(row) for row in result]
    except SQLAlchemyError as e:
        print(f"[ERROR get_hasiltryout_by_tryout] {e}")
        return None


def delete_hasil_tryout(id_hasiltryout: int) -> int:
    """
    Menghapus 1 attempt hasil tryout berdasarkan id_hasiltryout.
    Return:
        1  → berhasil menghapus
        0  → tidak ada data yang dihapus (id tidak ditemukan)
    """
    conn = get_connection()
    try:
        with conn.begin() as trans:
            query = text("""
                UPDATE hasiltryout set status = 0, updated_at = :now
                WHERE id_hasiltryout = :id_hasiltryout
            """)
            # query = text("""
            #     DELETE FROM hasiltryout
            #     WHERE id_hasiltryout = :id_hasiltryout
            # """)
            result = trans.execute(query, {"id_hasiltryout": id_hasiltryout, "now": get_wita()})
            return result.rowcount  # jumlah baris terhapus
    except Exception as e:
        print("Error delete_hasil_tryout:", e)
        return None
    
    
# ====== Hasil Tryout Mentor ====== #
def get_hasiltryout_list_for_mentor(id_mentor, id_tryout=None):
    """
    Ambil hasil tryout berdasarkan paket kelas yang diajar mentor.
    Mentor hanya boleh melihat tryout yang berada di paket kelas miliknya.
    """
    engine = get_connection()

    try:
        with engine.connect() as conn:

            # 1. Ambil paket kelas milik mentor
            paketkelas_query = text("""
                SELECT id_paketkelas 
                FROM mentorkelas
                WHERE id_user = :id_mentor AND status = 1
            """)
            paketkelas = conn.execute(paketkelas_query, {"id_mentor": id_mentor}).fetchall()

            if not paketkelas:
                return []  # Mentor tidak pegang kelas apa pun

            paketkelas_ids = [row[0] for row in paketkelas]

            # 2. Ambil tryout dari paket kelas itu
            tryout_query = text(f"""
                SELECT id_tryout FROM to_paketkelas
                WHERE status = 1 AND id_paketkelas = ANY(:kelas_ids)
            """)
            tryout_list = conn.execute(tryout_query, {"kelas_ids": paketkelas_ids}).fetchall()

            if not tryout_list:
                return []  # Tidak ada tryout di kelas mentor

            tryout_ids = [row[0] for row in tryout_list]

            # 3. Ambil hasil tryout
            base_query = """
                SELECT
                    h.id_hasiltryout, h.id_tryout, h.id_user, h.attempt_token,
                    h.attempt_ke, h.start_time, h.end_time, h.tanggal_pengerjaan,
                    h.nilai, h.benar, h.salah, h.kosong, h.ragu_ragu,
                    h.status_pengerjaan,
                    u.nama AS nama_user, u.nickname,
                    t.judul AS judul_tryout
                FROM hasiltryout h
                LEFT JOIN users u ON u.id_user = h.id_user
                LEFT JOIN tryout t ON t.id_tryout = h.id_tryout
                WHERE h.status = 1
                  AND h.id_tryout = ANY(:tryout_ids)
            """

            params = {"tryout_ids": tryout_ids}

            # Filter opsional: id_tryout tertentu
            if id_tryout:
                base_query += " AND h.id_tryout = :id_tryout"
                params["id_tryout"] = id_tryout

            # Urutkan terbaru
            base_query += " ORDER BY h.tanggal_pengerjaan DESC, h.start_time DESC"

            result = conn.execute(text(base_query), params).mappings().fetchall()

            return [serialize_datetime_uuid(r) for r in result]

    except SQLAlchemyError as e:
        print(f"[ERROR get_hasiltryout_list_for_mentor] {e}")
        return []


# ====== Hasil Tryout Peserta ====== #
def get_hasiltryout_list_peserta(filters: dict):
    """
    Mengambil daftar hasil tryout milik 1 user tertentu.
    """
    engine = get_connection()

    try:
        with engine.connect() as conn:

            base_query = """
                SELECT
                    h.id_hasiltryout, h.id_tryout, h.id_user, h.attempt_token, h.attempt_ke, 
                    h.start_time, h.end_time, h.tanggal_pengerjaan, h.nilai, 
                    h.benar, h.salah, h.kosong, h.ragu_ragu, h.status_pengerjaan,
                    t.judul AS judul_tryout
                FROM hasiltryout h
                LEFT JOIN tryout t ON t.id_tryout = h.id_tryout
                WHERE h.status = 1
                  AND h.id_user = :id_user
            """

            params = {
                "id_user": filters["id_user"]
            }

            # Filter opsional id_tryout
            if filters.get("id_tryout"):
                base_query += " AND h.id_tryout = :id_tryout"
                params["id_tryout"] = filters["id_tryout"]

            # Urutkan terbaru
            base_query += " ORDER BY h.tanggal_pengerjaan DESC, h.start_time DESC"

            result = conn.execute(text(base_query), params).mappings().fetchall()

            return [serialize_datetime_uuid(r) for r in result]

    except SQLAlchemyError as e:
        print(f"[ERROR get_hasiltryout_list_peserta] {e}")
        return []
