from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row, serialize_row_datetime
from ..utils.config import get_connection, get_wita


"""#=== helper ===#"""
def is_valid_parent_komentar(id_materi, parent_id):
    engine = get_connection()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 1 FROM komentarmateri
            WHERE id_komentarmateri = :parent_id AND id_materi = :id_materi AND status = 1
        """), {"parent_id": parent_id, "id_materi": id_materi}).fetchone()
        return bool(result)


"""#=== basic CRUD ===#"""
def get_komentar_by_materi(id_materi):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT km.id_komentarmateri, km.id_user, u.nama, km.isi_komentar, km.parent_id, km.is_deleted, km.deleted_by_mentor,
                       km.created_at, km.updated_at
                FROM komentarmateri km
                JOIN users u ON km.id_user = u.id_user
                WHERE km.id_materi = :id_materi AND km.status = 1
                ORDER BY km.created_at ASC
            """), {"id_materi": id_materi})
            komentar = [serialize_row_datetime(row) for row in result.mappings().fetchall()]
            return komentar
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []

def insert_komentar_materi(id_materi, id_user, isi_komentar, parent_id=None):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            query = text("""
                INSERT INTO komentarmateri (id_materi, id_user, isi_komentar, parent_id, status, created_at, updated_at)
                VALUES (:id_materi, :id_user, :isi_komentar, :parent_id, 1, :created_at, :updated_at)
                RETURNING id_komentarmateri
            """)
            now = get_wita()
            result = conn.execute(query, {
                "id_materi": id_materi,
                "id_user": id_user,
                "isi_komentar": isi_komentar,
                "parent_id": parent_id,
                "created_at": now,
                "updated_at": now
            }).mappings().fetchone()
            return result['id_komentarmateri'] if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def get_komentar_by_id(id_komentarmateri):
    engine = get_connection()
    with engine.connect() as conn:
        query = text("""
            SELECT id_komentarmateri, id_user, updated_at 
            FROM komentarmateri 
            WHERE id_komentarmateri = :id AND status = 1
        """)
        result = conn.execute(query, {"id": id_komentarmateri}).mappings().fetchone()
        return dict(result) if result else None

def update_komentar(id_komentarmateri, isi_komentar):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            query = text("""
                UPDATE komentarmateri
                SET isi_komentar = :isi_komentar, updated_at = :updated_at
                WHERE id_komentarmateri = :id
            """)
            conn.execute(query, {
                "isi_komentar": isi_komentar,
                "updated_at": get_wita(),
                "id": id_komentarmateri
            })
        return True
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return False

def soft_delete_komentar_materi(id_komentarmateri, id_user, role):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # Ambil komentar terlebih dahulu
            get_query = text("""
                SELECT id_user FROM komentarmateri WHERE id_komentarmateri = :id
            """)
            result = conn.execute(get_query, {"id": id_komentarmateri}).mappings().fetchone()
            if not result:
                return {"status": False, "msg": "Komentar tidak ditemukan"}

            pemilik_komentar = result['id_user']
            now = get_wita()

            # Validasi kepemilikan dan hak akses
            if role == "peserta":
                if int(id_user) != int(pemilik_komentar):
                    return {"status": False, "msg": "Peserta hanya bisa menghapus komentar sendiri"}
                update_query = text("""
                    UPDATE komentarmateri
                    SET isi_komentar = 'Komentar telah dihapus',
                        is_deleted = TRUE,
                        deleted_by_mentor = FALSE,
                        updated_at = :updated_at
                    WHERE id_komentarmateri = :id
                """)
            elif role == "mentor":
                update_query = text("""
                    UPDATE komentarmateri
                    SET isi_komentar = 'Komentar telah dihapus oleh mentor',
                        is_deleted = TRUE,
                        deleted_by_mentor = TRUE,
                        updated_at = :updated_at
                    WHERE id_komentarmateri = :id
                """)
            else:
                return {"status": False, "msg": "Role tidak dikenali"}

            conn.execute(update_query, {
                "id": id_komentarmateri,
                "updated_at": now
            })
            return {"status": True, "msg": "Komentar berhasil dihapus"}

    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return {"status": False, "msg": "Gagal menghapus komentar"}