from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita


"""#=== helper ===#"""
def is_valid_modul(id_modul):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_modul FROM modul WHERE id_modul = :id AND status = 1
            """), {"id": id_modul}).scalar()
            return result is not None
    except SQLAlchemyError:
        return False
    
def is_mentor_of_materi(id_mentor, id_materi):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 1
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                JOIN paketkelas pk ON mo.id_paketkelas = pk.id_paketkelas
                JOIN mentorkelas mk ON pk.id_paketkelas = mk.id_paketkelas
                WHERE m.id_materi = :id_materi
                AND mk.id_user = :id_mentor
                AND m.status = 1
            """), {"id_materi": id_materi, "id_mentor": id_mentor}).first()
            return result is not None
    except SQLAlchemyError:
        return False
    
def is_user_have_access_to_materi(id_user, id_materi, role):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT 1
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                JOIN paketkelas pk ON mo.id_paketkelas = pk.id_paketkelas
            """
            if role == 'mentor':
                query += """
                    JOIN mentorkelas mk ON pk.id_paketkelas = mk.id_paketkelas
                    WHERE mk.id_user = :id_user
                """
            elif role == 'peserta':
                query += """
                    JOIN pesertakelas ps ON pk.id_paketkelas = ps.id_paketkelas
                    WHERE ps.id_user = :id_user
                """
            else:
                return False

            query += " AND m.id_materi = :id_materi AND m.status = 1"

            result = conn.execute(text(query), {
                "id_user": id_user,
                "id_materi": id_materi
            }).first()
            return result is not None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return False


"""#=== CRUD ===#"""
def get_all_materi():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.*, mo.judul AS judul_modul
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                WHERE m.status = 1
                ORDER BY m.created_at DESC
            """)).mappings().fetchall()
            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []

def get_materi_by_id(id_materi):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.*, mo.judul AS judul_modul
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                WHERE m.id_materi = :id AND m.status = 1
            """), {"id": id_materi}).mappings().fetchone()
            return serialize_row(result) if result else None
    except SQLAlchemyError:
        return None

def insert_materi(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            now = get_wita()
            result = conn.execute(text("""
                INSERT INTO materi (id_modul, tipe_materi, judul, url_file, viewer_only, status, created_at, updated_at)
                VALUES (:id_modul, :tipe_materi, :judul, :url_file, :viewer_only, 1, :now, :now)
                RETURNING id_materi, judul
            """), {**payload, "now": now}).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError:
        return None

def update_materi(id_materi, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            now = get_wita()
            result = conn.execute(text("""
                UPDATE materi
                SET id_modul = :id_modul,
                    tipe_materi = :tipe_materi,
                    judul = :judul,
                    url_file = :url_file,
                    viewer_only = :viewer_only,
                    updated_at = :now
                WHERE id_materi = :id AND status = 1
                RETURNING id_materi, judul
            """), {**payload, "id": id_materi, "now": now}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError:
        return None

def delete_materi(id_materi):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE materi
                SET status = 0, updated_at = :now
                WHERE id_materi = :id AND status = 1
                RETURNING id_materi, judul
            """), {"id": id_materi, "now": get_wita()}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError:
        return None


""""#== Query lanjutan ==#"""
def get_materi_by_peserta(id_user):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_materi, m.judul, m.tipe_materi, m.url_file, m.viewer_only, m.id_modul, pk.id_paketkelas, pk.nama_kelas
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                JOIN paketkelas pk ON mo.id_paketkelas = pk.id_paketkelas
                JOIN userbatch ub ON ub.id_user = :id_user
                JOIN pesertakelas pkls ON pkls.id_user = :id_user
                WHERE pk.id_batch = ub.id_batch
                  AND pkls.id_paketkelas = pk.id_paketkelas
                  AND m.visibility = 'open' AND m.status = 1
                ORDER BY mo.urutan_modul ASC
            """), {"id_user": id_user}).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"[get_materi_by_peserta] Error: {str(e)}")
        return []
    
def get_materi_by_mentor(id_user):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_materi, m.judul, m.tipe_materi, m.url_file, m.viewer_only, m.id_modul, pk.id_paketkelas, pk.nama_kelas
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                JOIN paketkelas pk ON mo.id_paketkelas = pk.id_paketkelas
                JOIN mentorkelas mkls ON mkls.id_user = :id_user
                WHERE mkls.id_paketkelas = pk.id_paketkelas
                  AND m.status = 1
                ORDER BY mo.urutan_modul ASC
            """), {"id_user": id_user}).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"[get_materi_by_mentor] Error: {str(e)}")
        return []
    
def update_materi_visibility(id_materi, visibility):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            now = get_wita()
            result = conn.execute(text("""
                UPDATE materi
                SET visibility = :visibility,
                    updated_at = :now
                WHERE id_materi = :id_materi AND status = 1
                RETURNING id_materi, judul
            """), {
                "id_materi": id_materi,
                "visibility": visibility,
                "now": now
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError:
        return None

