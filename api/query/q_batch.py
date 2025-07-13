from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita


def get_all_batch():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_batch, nama_batch, tanggal_mulai, tanggal_selesai
                FROM batch
                WHERE status = 1
                ORDER BY tanggal_mulai DESC
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
            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None


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