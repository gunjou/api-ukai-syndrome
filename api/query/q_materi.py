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
                SELECT id_modul 
                FROM modul 
                WHERE id_modul = :id AND status = 1
            """), {"id": id_modul}).scalar()
            return result is not None
    except SQLAlchemyError:
        return False

def is_mentor_of_materi(id_mentor, id_materi, id_paketkelas):
    """Cek apakah mentor tertentu mengampu materi dalam paket kelas tertentu"""
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 1
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                JOIN modulkelas mkls ON mo.id_modul = mkls.id_modul
                JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                JOIN mentorkelas mk ON pk.id_paketkelas = mk.id_paketkelas
                WHERE m.id_materi = :id_materi
                  AND pk.id_paketkelas = :id_paketkelas
                  AND mk.id_user = :id_mentor
                  AND m.status = 1
                  AND mk.status = 1
                  AND mkls.status = 1
            """), {
                "id_materi": id_materi,
                "id_paketkelas": id_paketkelas,
                "id_mentor": id_mentor
            }).first()
            return result is not None
    except SQLAlchemyError as e:
        print(f"[is_mentor_of_materi] Error: {e}")
        return False
    
def is_mentor_of_modul(id_user, id_modul):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 1
                FROM modul m
                JOIN modulkelas mkls ON m.id_modul = mkls.id_modul AND mkls.status = 1
                JOIN mentorkelas mtr ON mkls.id_paketkelas = mtr.id_paketkelas AND mtr.status = 1
                WHERE m.id_modul = :id_modul
                  AND mtr.id_user = :id_user
                  AND m.status = 1
                LIMIT 1
            """), {"id_user": id_user, "id_modul": id_modul}).first()
            return result is not None
    except SQLAlchemyError as e:
        print(f"Error is_mentor_of_modul: {e}")
        return False

def is_user_have_access_to_materi(id_user, id_materi, role, id_paketkelas):
    """Validasi apakah user (mentor/peserta) punya akses ke materi dalam paket kelas tertentu"""
    engine = get_connection()
    try:
        with engine.connect() as conn:
            base_query = """
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                JOIN modulkelas mkls ON mo.id_modul = mkls.id_modul
                JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
            """

            if role == 'mentor':
                query = f"""
                    SELECT 1 {base_query}
                    JOIN mentorkelas mk ON pk.id_paketkelas = mk.id_paketkelas
                    WHERE mk.id_user = :id_user
                      AND pk.id_paketkelas = :id_paketkelas
                      AND m.id_materi = :id_materi
                      AND m.status = 1
                      AND mk.status = 1
                      AND mkls.status = 1
                """
            elif role == 'peserta':
                query = f"""
                    SELECT 1 {base_query}
                    JOIN pesertakelas ps ON pk.id_paketkelas = ps.id_paketkelas
                    WHERE ps.id_user = :id_user
                      AND pk.id_paketkelas = :id_paketkelas
                      AND m.id_materi = :id_materi
                      AND m.status = 1
                      AND ps.status = 1
                      AND mkls.status = 1
                """
            else:
                return False

            result = conn.execute(text(query), {
                "id_user": id_user,
                "id_materi": id_materi,
                "id_paketkelas": id_paketkelas
            }).first()
            return result is not None
    except SQLAlchemyError as e:
        print(f"[is_user_have_access_to_materi] Error: {e}")
        return False


"""#=== CRUD ===#"""
def get_all_materi():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_materi, m.id_owner, u.nickname as owner, m.id_modul, m.tipe_materi, m.judul, m.url_file,
                       m.visibility, m.status, m.created_at, m.updated_at,
                       mo.judul AS judul_modul
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul AND mo.status = 1
                LEFT JOIN users u ON m.id_owner = u.id_user AND u.status = 1
                WHERE m.status = 1
                ORDER BY m.created_at DESC
            """)).mappings().fetchall()
            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []

def get_old_materi_by_id(id_materi):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_materi, id_modul, tipe_materi, judul, url_file,
                       visibility, status, created_at, updated_at
                FROM materi
                WHERE id_materi = :id AND status = 1
            """), {"id": id_materi}).mappings().fetchone()
            return serialize_row(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None
    
def get_materi_by_id(id_materi):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_materi, m.id_owner, m.id_modul, m.tipe_materi, m.judul, m.url_file,
                       m.visibility, m.status, m.created_at, m.updated_at,
                       mo.judul AS judul_modul
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul AND mo.status = 1
                WHERE m.id_materi = :id AND m.status = 1
            """), {"id": id_materi}).mappings().fetchone()
            return serialize_row(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def insert_materi(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            now = get_wita()
            result = conn.execute(text("""
                INSERT INTO materi (id_modul, id_owner, tipe_materi, judul, url_file, status, created_at, updated_at)
                VALUES (:id_modul, :id_owner, :tipe_materi, :judul, :url_file, 1, :now, :now)
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
                    id_owner = :id_owner,
                    tipe_materi = :tipe_materi,
                    judul = :judul,
                    url_file = :url_file,
                    visibility = :visibility,
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
                SELECT m.id_materi, m.judul, m.tipe_materi, m.url_file,
                       m.id_modul, pk.id_paketkelas, pk.nama_kelas
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                JOIN modulkelas mk ON mk.id_modul = mo.id_modul
                JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas
                JOIN userbatch ub ON ub.id_user = :id_user
                JOIN pesertakelas pkls ON pkls.id_user = :id_user
                WHERE pk.id_batch = ub.id_batch
                  AND pkls.id_paketkelas = pk.id_paketkelas
                  AND m.visibility = 'open'
                  AND m.status = 1
                  AND mk.status = 1
                ORDER BY mo.created_at ASC
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
                SELECT m.id_materi, m.judul, m.tipe_materi, m.url_file,
                       m.id_modul, pk.id_paketkelas, pk.nama_kelas
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                JOIN modulkelas mk ON mk.id_modul = mo.id_modul
                JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas
                JOIN mentorkelas mkls ON mkls.id_user = :id_user
                WHERE mkls.id_paketkelas = pk.id_paketkelas
                  AND m.status = 1
                  AND mk.status = 1
                  AND mkls.status = 1
                ORDER BY mo.created_at ASC
            """), {"id_user": id_user}).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"[get_materi_by_mentor] Error: {str(e)}")
        return []
    
def get_materi_by_mentor_and_kelas(id_user, id_paketkelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_materi, m.judul, m.tipe_materi, m.url_file,
                       m.id_modul, pk.id_paketkelas, pk.nama_kelas
                FROM materi m
                JOIN modul mo ON m.id_modul = mo.id_modul
                JOIN modulkelas mk ON mk.id_modul = mo.id_modul
                JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas AND pk.id_paketkelas = :id_paketkelas
                JOIN mentorkelas mkls ON mkls.id_user = :id_user
                WHERE mkls.id_paketkelas = pk.id_paketkelas
                  AND m.status = 1
                  AND mk.status = 1
                  AND mkls.status = 1
                ORDER BY mo.created_at ASC
            """), {"id_user": id_user, "id_paketkelas": id_paketkelas}).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"[get_materi_by_mentor] Error: {str(e)}")
        return []
    
def update_materi_visibility(id_materi, visibility):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE materi
                SET visibility = :visibility,
                    updated_at = :now
                WHERE id_materi = :id_materi AND status = 1
                RETURNING id_materi, judul
            """), {
                "id_materi": id_materi,
                "visibility": visibility,
                "now": get_wita()
            }).mappings().fetchone()

            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"[update_materi_visibility] Error: {e}")
        return None


