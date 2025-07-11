from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..utils.config import get_connection, get_wita


def get_all_kelas():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                       b.id_batch, b.nama_batch
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch
                WHERE pk.status = 1
                ORDER BY pk.id_paketkelas DESC
            """)).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []

def get_kelas_by_id(id_kelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                       b.id_batch, b.nama_batch
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch
                WHERE pk.id_paketkelas = :id_kelas AND pk.status = 1
            """), {"id_kelas": id_kelas}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def is_batch_exist(id_batch):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_batch FROM batch
                WHERE id_batch = :id_batch AND status = 1
            """), {"id_batch": id_batch}).scalar()
            return result is not None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return False

def insert_kelas(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO paketkelas (id_batch, nama_kelas, deskripsi, status, created_at, updated_at)
                VALUES (:id_batch, :nama_kelas, :deskripsi, 1, :now, :now)
                RETURNING nama_kelas
            """), {
                **payload,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def update_kelas(id_kelas, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE paketkelas
                SET id_batch = :id_batch,
                    nama_kelas = :nama_kelas,
                    deskripsi = :deskripsi,
                    updated_at = :now
                WHERE id_paketkelas = :id_kelas AND status = 1
                RETURNING nama_kelas
            """), {
                **payload,
                "id_kelas": id_kelas,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def delete_kelas(id_kelas):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE paketkelas
                SET status = 0, updated_at = :now
                WHERE id_paketkelas = :id_kelas AND status = 1
                RETURNING nama_kelas
            """), {
                "id_kelas": id_kelas,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None