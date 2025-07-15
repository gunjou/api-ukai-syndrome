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
                SELECT m.id_modul, m.judul, m.deskripsi, m.urutan_modul, m.visibility,
                       m.id_paketkelas, pk.nama_kelas
                FROM modul m
                JOIN paketkelas pk ON m.id_paketkelas = pk.id_paketkelas
                WHERE m.status = 1
                ORDER BY m.urutan_modul
            """)).mappings().fetchall()
            return [serialize_row(row) for row in result]
    except SQLAlchemyError:
        return []
    
def get_all_modul_by_mentor(id_mentor):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.*, pk.nama_kelas 
                FROM modul m
                JOIN paketkelas pk ON m.id_paketkelas = pk.id_paketkelas
                JOIN mentorkelas mk ON mk.id_paketkelas = pk.id_paketkelas
                WHERE mk.id_user = :id_mentor AND mk.status = 1 AND m.status = 1
                ORDER BY m.urutan_modul
            """), {"id_mentor": id_mentor}).mappings().fetchall()
            return [serialize_row(row) for row in result]
    except SQLAlchemyError:
        return []

def get_modul_by_id(id_modul):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.urutan_modul, m.visibility,
                       m.id_paketkelas, pk.nama_kelas
                FROM modul m
                JOIN paketkelas pk ON m.id_paketkelas = pk.id_paketkelas
                WHERE m.id_modul = :id AND m.status = 1
            """), {"id": id_modul}).mappings().fetchone()
            return dict(result) if result else None
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
def get_modul_by_user(id_user, role):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            if role == "mentor":
                query = text("""
                    SELECT m.id_modul, m.judul, m.deskripsi, m.urutan_modul, m.visibility, p.nama_kelas
                    FROM modul m
                    JOIN paketkelas p ON m.id_paketkelas = p.id_paketkelas
                    JOIN mentorkelas mk ON mk.id_paketkelas = p.id_paketkelas
                    WHERE mk.id_user = :id_user AND m.status = 1
                    ORDER BY m.urutan_modul
                """)
            elif role == "peserta":
                query = text("""
                    SELECT m.id_modul, m.judul, m.deskripsi, m.urutan_modul, m.visibility, p.nama_kelas
                    FROM modul m
                    JOIN paketkelas p ON m.id_paketkelas = p.id_paketkelas
                    JOIN pesertakelas pk ON pk.id_paketkelas = p.id_paketkelas
                    WHERE pk.id_user = :id_user AND m.visibility = 'open' AND m.status = 1
                    ORDER BY m.urutan_modul
                """)
            else:
                return []

            result = conn.execute(query, {"id_user": id_user}).mappings().fetchall()
            return [serialize_row(r) for r in result]

    except SQLAlchemyError as e:
        print(f"Error: {e}")
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

