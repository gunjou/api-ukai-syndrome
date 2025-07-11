from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..utils.config import get_connection, get_wita

def get_all_userbatch():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT ub.id_userbatch, u.id_user, u.nama, u.email,
                       b.id_batch, b.nama_batch, ub.tanggal_join
                FROM userbatch ub
                JOIN users u ON ub.id_user = u.id_user
                JOIN batch b ON ub.id_batch = b.id_batch
                WHERE ub.status = 1
                ORDER BY ub.id_userbatch DESC
            """)).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []

def get_userbatch_by_id(id_userbatch):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT ub.id_userbatch, u.id_user, u.nama, u.email,
                       b.id_batch, b.nama_batch, ub.tanggal_join
                FROM userbatch ub
                JOIN users u ON ub.id_user = u.id_user
                JOIN batch b ON ub.id_batch = b.id_batch
                WHERE ub.id_userbatch = :id AND ub.status = 1
            """), {"id": id_userbatch}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError:
        return None

def is_valid_peserta(id_user):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_user FROM users
                WHERE id_user = :id AND role = 'peserta' AND status = 1
            """), {"id": id_user}).scalar()
            return result is not None
    except SQLAlchemyError:
        return False

def is_valid_batch(id_batch):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_batch FROM batch
                WHERE id_batch = :id AND status = 1
            """), {"id": id_batch}).scalar()
            return result is not None
    except SQLAlchemyError:
        return False

def insert_userbatch(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            now = get_wita()
            result = conn.execute(text("""
                INSERT INTO userbatch (id_user, id_batch, tanggal_join, status, created_at, updated_at)
                VALUES (:id_user, :id_batch, :tanggal_join, 1, :now, :now)
                RETURNING id_userbatch
            """), {
                **payload,
                "now": now
            }).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def update_userbatch(id_userbatch, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE userbatch
                SET id_user = :id_user,
                    id_batch = :id_batch,
                    tanggal_join = :tanggal_join,
                    updated_at = :now
                WHERE id_userbatch = :id AND status = 1
                RETURNING id_userbatch
            """), {
                **payload,
                "id": id_userbatch,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError:
        return None

def delete_userbatch(id_userbatch):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE userbatch
                SET status = 0, updated_at = :now
                WHERE id_userbatch = :id AND status = 1
                RETURNING id_userbatch
            """), {
                "id": id_userbatch,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError:
        return None
