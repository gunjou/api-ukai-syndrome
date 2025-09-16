from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..utils.config import get_connection, get_wita

def get_all_mentorkelas():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT mk.id_mentorkelas, u.id_user, u.nama as nama_mentor, u.email,
                       pk.id_paketkelas, pk.nama_kelas
                FROM mentorkelas mk
                JOIN users u ON mk.id_user = u.id_user
                JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas
                WHERE mk.status = 1
                ORDER BY mk.id_mentorkelas DESC
            """)).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []

def get_mentorkelas_by_id(id_mentorkelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT mk.id_mentorkelas, u.id_user, u.nama as nama_mentor, u.email,
                       pk.id_paketkelas, pk.nama_kelas
                FROM mentorkelas mk
                JOIN users u ON mk.id_user = u.id_user
                JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas
                WHERE mk.id_mentorkelas = :id AND mk.status = 1
            """), {"id": id_mentorkelas}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def is_valid_mentor(id_user):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_user FROM users
                WHERE id_user = :id_user AND role = 'mentor' AND status = 1
            """), {"id_user": id_user}).scalar()
            return result is not None
    except SQLAlchemyError:
        return False

def is_valid_kelas(id_paketkelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_paketkelas FROM paketkelas
                WHERE id_paketkelas = :id AND status = 1
            """), {"id": id_paketkelas}).scalar()
            return result is not None
    except SQLAlchemyError:
        return False

def insert_mentorkelas(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO mentorkelas (id_user, id_paketkelas, status, created_at, updated_at)
                VALUES (:id_user, :id_paketkelas, 1, :now, :now)
                RETURNING id_mentorkelas
            """), {
                **payload,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def update_mentorkelas(id_mentorkelas, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE mentorkelas
                SET id_user = :id_user,
                    id_paketkelas = :id_paketkelas,
                    updated_at = :now
                WHERE id_mentorkelas = :id AND status = 1
                RETURNING id_mentorkelas
            """), {
                **payload,
                "id": id_mentorkelas,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def delete_mentorkelas(id_mentorkelas):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE mentorkelas
                SET status = 0, updated_at = :now
                WHERE id_mentorkelas = :id AND status = 1
                RETURNING id_mentorkelas
            """), {
                "id": id_mentorkelas,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None


def get_list_kelas_mentor(id_mentor):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                        b.id_batch, b.nama_batch, p.id_paket, p.nama_paket, mkls.id_mentorkelas,
                        COALESCE(tmd.total_modul, 0) AS total_modul,
                        COALESCE(tp.total_peserta, 0) AS total_peserta,
                        COALESCE(tm.total_mentor, 0) AS total_mentor
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                JOIN paket p ON pk.id_paket = p.id_paket AND p.status = 1
                JOIN mentorkelas mkls ON mkls.id_paketkelas = pk.id_paketkelas AND mkls.status = 1
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(mk.*) AS total_modul
                    FROM modulkelas mk
                    INNER JOIN modul m ON m.id_modul = mk.id_modul AND m.status = 1
                    INNER JOIN paketkelas p ON p.id_paketkelas = mk.id_paketkelas AND p.status = 1
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tmd ON pk.id_paketkelas = tmd.id_paketkelas
                LEFT JOIN (
                    SELECT pk.id_paketkelas, COUNT(pk.*) AS total_peserta
                    FROM pesertakelas pk
                    INNER JOIN paketkelas p ON p.id_paketkelas = pk.id_pesertakelas AND p.status = 1
                    INNER JOIN users u ON u.id_user = pk.id_user AND u.status = 1 AND u.role = 'peserta'
                    WHERE pk.status = 1
                    GROUP BY pk.id_paketkelas
                ) tp ON pk.id_paketkelas = tp.id_paketkelas
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(mk.*) AS total_mentor
                    FROM mentorkelas mk
                    INNER JOIN paketkelas p ON p.id_paketkelas = mk.id_paketkelas AND p.status = 1
                    INNER JOIN users u ON u.id_user = mk.id_user AND u.status = 1 AND u.role = 'mentor'
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tm ON pk.id_paketkelas = tm.id_paketkelas
                WHERE pk.status = 1 and mkls.id_user = :id_mentor
                ORDER BY pk.nama_kelas ASC
            """
            result = conn.execute(text(query), {'id_mentor': id_mentor}).mappings().fetchall()
            # Pastikan count hasilnya integer, bukan Decimal
            return [
                {
                    **dict(row),
                    "total_peserta": int(row["total_peserta"]),
                    "total_mentor": int(row["total_mentor"]),
                }
                for row in result
            ]
    except SQLAlchemyError as e:
        print(f"[get_kelas_by_role] Database error: {e}")
        return []
    
def get_all_mentor_kelas(id_mentor):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                       b.id_batch, b.nama_batch, p.id_paket, p.nama_paket,
                       COALESCE(tmd.total_modul, 0) AS total_modul,
                       COALESCE(tp.total_peserta, 0) AS total_peserta,
                       COALESCE(tm.total_mentor, 0) AS total_mentor
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                JOIN paket p ON pk.id_paket = p.id_paket AND p.status = 1
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(mk.*) AS total_modul
                    FROM modulkelas mk
                    INNER JOIN modul m ON m.id_modul = mk.id_modul AND m.status = 1
                    INNER JOIN paketkelas p ON p.id_paketkelas = mk.id_paketkelas AND p.status = 1
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tmd ON pk.id_paketkelas = tmd.id_paketkelas
                LEFT JOIN (
                    SELECT pk.id_paketkelas, COUNT(pk.*) AS total_peserta
                    FROM pesertakelas pk
                    INNER JOIN paketkelas p ON p.id_paketkelas = pk.id_pesertakelas AND p.status = 1
                    INNER JOIN users u ON u.id_user = pk.id_user AND u.status = 1 AND u.role = 'peserta'
                    WHERE pk.status = 1
                    GROUP BY pk.id_paketkelas
                ) tp ON pk.id_paketkelas = tp.id_paketkelas
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(mk.*) AS total_mentor
                    FROM mentorkelas mk
                    INNER JOIN paketkelas p ON p.id_paketkelas = mk.id_paketkelas AND p.status = 1
                    INNER JOIN users u ON u.id_user = mk.id_user AND u.status = 1 AND u.role = 'mentor'
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tm ON pk.id_paketkelas = tm.id_paketkelas
                WHERE pk.status = 1
                  AND NOT EXISTS (
                      SELECT 1 
                      FROM mentorkelas mk
                      WHERE mk.id_paketkelas = pk.id_paketkelas
                        AND mk.id_user = :id_mentor
                        AND mk.status = 1
                  )
                ORDER BY pk.nama_kelas ASC
            """
            result = conn.execute(text(query), {"id_mentor": id_mentor}).mappings().fetchall()

            return [
                {
                    **dict(row),
                    "total_peserta": int(row["total_peserta"]),
                    "total_mentor": int(row["total_mentor"]),
                }
                for row in result
            ]
    except SQLAlchemyError as e:
        print(f"[get_all_mentor_kelas] Database error: {e}")
        return []
    
def assign_kelas_to_mentor(id_mentor, id_paketkelas_list):
    """
    Assign satu atau banyak kelas ke mentor tertentu.
    """
    engine = get_connection()
    try:
        with engine.begin() as conn:
            now = get_wita()
            inserted_count = 0

            for id_paketkelas in id_paketkelas_list:
                # Cek apakah sudah ada relasi aktif
                existing = conn.execute(text("""
                    SELECT 1 FROM mentorkelas
                    WHERE id_user = :id_mentor 
                      AND id_paketkelas = :id_paketkelas
                      AND status = 1
                """), {
                    "id_mentor": id_mentor,
                    "id_paketkelas": id_paketkelas
                }).fetchone()

                if existing:
                    continue  # skip jika sudah ada

                # Insert baru
                conn.execute(text("""
                    INSERT INTO mentorkelas (id_user, id_paketkelas, status, created_at, updated_at)
                    VALUES (:id_mentor, :id_paketkelas, 1, :now, :now)
                """), {
                    "id_mentor": id_mentor,
                    "id_paketkelas": id_paketkelas,
                    "now": now
                })
                inserted_count += 1

            return inserted_count
    except SQLAlchemyError as e:
        print(f"[assign_kelas_to_mentor] Error: {e}")
        return 0
    
def delete_kelas_in_mentor(id_mentorkelas):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE mentorkelas
                SET status = 0, updated_at = :now
                WHERE id_mentorkelas = :id AND status = 1
            """), {
                "id": id_mentorkelas,
                "now": get_wita()
            })
            return result.rowcount > 0  # True kalau ada row ter-update
    except SQLAlchemyError:
        return False