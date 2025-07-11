from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..utils.config import get_connection, get_wita

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

def get_all_modul():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.urutan_modul,
                       m.id_paketkelas, pk.nama_kelas
                FROM modul m
                JOIN paketkelas pk ON m.id_paketkelas = pk.id_paketkelas
                WHERE m.status = 1
                ORDER BY m.urutan_modul ASC
            """)).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []

def get_modul_by_id(id_modul):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.urutan_modul,
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
            now = get_wita()
            result = conn.execute(text("""
                INSERT INTO modul (id_paketkelas, judul, deskripsi, urutan_modul, status, created_at, updated_at)
                VALUES (:id_paketkelas, :judul, :deskripsi, :urutan_modul, 1, :now, :now)
                RETURNING id_modul, judul
            """), {
                **payload,
                "now": now
            }).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def update_modul(id_modul, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            now = get_wita()
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
                "now": now
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
