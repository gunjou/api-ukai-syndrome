from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita


def get_all_batch():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    b.id_batch,
                    b.nama_batch,
                    b.tanggal_mulai,
                    b.tanggal_selesai,
                    COUNT(u.id_user) AS total_peserta
                FROM batch b
                LEFT JOIN userbatch ub 
                    ON ub.id_batch = b.id_batch 
                   AND ub.status = 1
                LEFT JOIN users u 
                    ON u.id_user = ub.id_user 
                   AND u.role = 'peserta' 
                   AND u.status = 1
                WHERE b.status = 1
                GROUP BY b.id_batch, b.nama_batch, b.tanggal_mulai, b.tanggal_selesai
                ORDER BY b.tanggal_mulai ASC
            """)).mappings().fetchall()

            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []


def get_batch_by_id(id_batch):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_batch, nama_batch, tanggal_mulai, tanggal_selesai
                FROM batch
                WHERE id_batch = :id_batch AND status = 1
            """), {"id_batch": id_batch}).mappings().fetchone()
            return serialize_row(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []


def insert_batch(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO batch (nama_batch, tanggal_mulai, tanggal_selesai, status, created_at, updated_at)
                VALUES (:nama_batch, :tanggal_mulai, :tanggal_selesai, 1, :now, :now)
                RETURNING nama_batch
            """), {
                **payload,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None


def update_batch(id_batch, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE batch
                SET nama_batch = :nama_batch,
                    tanggal_mulai = :tanggal_mulai,
                    tanggal_selesai = :tanggal_selesai,
                    updated_at = :now
                WHERE id_batch = :id_batch AND status = 1
                RETURNING nama_batch
            """), {
                **payload,
                "id_batch": id_batch,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None


def delete_batch(id_batch):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE batch
                SET status = 0, updated_at = :now
                WHERE id_batch = :id_batch AND status = 1
                RETURNING nama_batch
            """), {
                "id_batch": id_batch,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None
    

"""#=== Query lainnya (selain CRUD) ===#"""
def get_batch_terbuka():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_batch, nama_batch, tanggal_mulai, tanggal_selesai
                FROM batch
                WHERE status = 1 AND tanggal_selesai >= CURRENT_DATE
                ORDER BY tanggal_mulai ASC
            """)).mappings().fetchall()
            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"[get_batch_terbuka] Error: {str(e)}")
        return []

def get_peserta_batch(id_batch):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    u.id_user, u.nama, u.email, u.no_hp, ub.id_userbatch, ub.tanggal_join
                FROM userbatch ub
                JOIN users u  ON ub.id_user = u.id_user AND u.role = 'peserta' AND u.status = 1
                WHERE ub.status = 1 AND ub.id_batch = :id_batch
                ORDER BY u.nama ASC
            """), {"id_batch": id_batch}).mappings().fetchall()

            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error get_peserta_batch: {e}")
        return []

def delete_peserta_in_batch(id_userbatch):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE userbatch
                SET status = 0, updated_at = :now
                WHERE id_userbatch = :id AND status = 1
            """), {
                "id": id_userbatch,
                "now": get_wita()
            })
            return result.rowcount > 0  # True kalau ada row ter-update
    except SQLAlchemyError:
        return False