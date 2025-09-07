from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita

"""=== helper ==="""
def is_mentor_of_kelas(id_mentor, id_paketkelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 1 FROM mentorkelas
                WHERE id_user = :id_user AND id_paketkelas = :id_paketkelas AND status = 1
            """), {
                "id_user": id_mentor,
                "id_paketkelas": id_paketkelas
            }).fetchone()
            return bool(result)
    except SQLAlchemyError:
        return False
    
def is_valid_paketkelas(id_paketkelas):
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

"""=== CRUD ==="""
def get_all_modul_admin():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.visibility, m.status,
                       pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                FROM modul m
                JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                WHERE m.status = 1
                ORDER BY m.id_modul
            """)).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError:
        return []
    

def get_all_modul_by_mentor(id_mentor):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.visibility, m.status,
                       pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                FROM modul m
                JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                JOIN mentorkelas mtk ON mtk.id_paketkelas = pk.id_paketkelas
                WHERE mtk.id_user = :id_mentor 
                  AND mtk.status = 1 
                  AND pk.status = 1 
                  AND m.status = 1
                ORDER BY m.id_modul
            """), {"id_mentor": id_mentor}).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError:
        return []

def get_modul_by_id(id_modul):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.visibility, m.status,
                       pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                FROM modul m
                JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                WHERE m.id_modul = :id AND m.status = 1 AND pk.status = 1
            """), {"id": id_modul}).mappings().fetchall()

            # Bisa ada banyak kelas untuk satu modul → return list
            return [dict(row) for row in result] if result else None
    except SQLAlchemyError:
        return None

def insert_modul(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO modul (id_paketkelas, judul, deskripsi, urutan_modul, status, created_at, updated_at)
                VALUES (:id_paketkelas, :judul, :deskripsi, :urutan_modul, 1, :now, :now)
                RETURNING id_modul, judul
            """), {
                **payload,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None
    
def insert_modul_for_mentor(payload, id_user):
    """
    Insert modul baru oleh mentor, lalu otomatis assign ke kelas yang dia ampu.
    """
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # 1️⃣ Buat modul baru
            modul = conn.execute(text("""
                INSERT INTO modul (judul, deskripsi, status, created_at, updated_at, visibility)
                VALUES (:judul, :deskripsi, 1, :now, :now, :visibility)
                RETURNING id_modul, judul
            """), {
                "judul": payload["judul"],
                "deskripsi": payload.get("deskripsi"),
                "visibility": payload.get("visibility", "hold"),
                "now": get_wita()
            }).mappings().fetchone()

            if not modul:
                return None

            id_modul = modul["id_modul"]

            # 2️⃣ Cari semua kelas yang diampu mentor
            kelas_list = conn.execute(text("""
                SELECT id_paketkelas 
                FROM mentorkelas
                WHERE id_user = :id_user AND status = 1
            """), {"id_user": id_user}).mappings().fetchall()

            if not kelas_list:
                raise Exception("Mentor tidak memiliki kelas aktif.")

            # 3️⃣ Assign modul ke semua kelas tersebut
            for kelas in kelas_list:
                conn.execute(text("""
                    INSERT INTO modulkelas (id_modul, id_paketkelas, status, created_at, updated_at)
                    VALUES (:id_modul, :id_paketkelas, 1, :now, :now)
                """), {
                    "id_modul": id_modul,
                    "id_paketkelas": kelas["id_paketkelas"],
                    "now": get_wita()
                })

            return dict(modul)

    except SQLAlchemyError as e:
        print(f"Error insert_modul_for_mentor: {e}")
        return None

def update_modul(id_modul, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE modul
                SET id_paketkelas = :id_paketkelas,
                    judul = :judul,
                    deskripsi = :deskripsi,
                    urutan_modul = :urutan_modul,
                    updated_at = :now
                WHERE id_modul = :id AND status = 1
                RETURNING id_modul, judul
            """), {
                **payload,
                "id": id_modul,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError:
        return None

def delete_modul(id_modul):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE modul
                SET status = 0, updated_at = :now
                WHERE id_modul = :id AND status = 1
                RETURNING id_modul, judul
            """), {
                "id": id_modul,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError:
        return None


"""#=== Query tambahan (selain CRUD) ===#"""
def get_all_modul_by_user(id_user, role):
    """
    Ambil modul berdasarkan role user:
    - mentor → modul yang diampu
    - peserta → modul dari kelas yang diikuti
    """
    engine = get_connection()
    try:
        with engine.connect() as conn:
            if role == "mentor":
                result = conn.execute(text("""
                    SELECT m.id_modul, m.judul, m.deskripsi, m.visibility, m.status,
                           pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                    FROM modul m
                    JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                    JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                    JOIN mentorkelas mtk ON mtk.id_paketkelas = pk.id_paketkelas
                    WHERE mtk.id_user = :id_user
                      AND mtk.status = 1
                      AND pk.status = 1
                      AND m.status = 1
                    ORDER BY m.id_modul
                """), {"id_user": id_user}).mappings().fetchall()

            elif role == "peserta":
                result = conn.execute(text("""
                    SELECT m.id_modul, m.judul, m.deskripsi, m.visibility, m.status,
                           pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                    FROM modul m
                    JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                    JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                    JOIN pesertakelas ps ON ps.id_paketkelas = pk.id_paketkelas
                    WHERE ps.id_user = :id_user
                      AND ps.status = 1
                      AND pk.status = 1
                      AND m.status = 1
                      AND m.visibility = 'open'
                    ORDER BY m.id_modul
                """), {"id_user": id_user}).mappings().fetchall()

            else:
                return []

            return [dict(row) for row in result]

    except SQLAlchemyError as e:
        print(f"[get_all_modul_by_user] Error: {e}")
        return []

def update_modul_visibility(id_modul, visibility):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE modul
                SET visibility = :visibility,
                    updated_at = :now
                WHERE id_modul = :id_modul AND status = 1
                RETURNING id_modul, judul
            """), {
                "visibility": visibility,
                "id_modul": id_modul,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

