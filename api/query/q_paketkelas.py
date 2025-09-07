from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..utils.config import get_connection, get_wita


def get_kelas_by_role(id_user, role):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            if role == 'admin':
                query = """
                    SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                           b.id_batch, b.nama_batch, p.id_paket, p.nama_paket
                    FROM paketkelas pk
                    JOIN batch b ON pk.id_batch = b.id_batch and b.status = 1
                    JOIN paket p ON pk.id_paket = p.id_paket and p.status = 1
                    WHERE pk.status = 1
                    ORDER BY pk.nama_kelas ASC
                """
                result = conn.execute(text(query)).mappings().fetchall()

            elif role == 'mentor':
                query = """
                    SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                           b.id_batch, b.nama_batch
                    FROM mentorkelas mk
                    JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas
                    JOIN batch b ON pk.id_batch = b.id_batch
                    WHERE mk.id_user = :id_user AND mk.status = 1 AND pk.status = 1
                    ORDER BY pk.nama_kelas ASC
                """
                result = conn.execute(text(query), {"id_user": id_user}).mappings().fetchall()
            else:
                # Role tidak diizinkan
                return []

            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Database error: {e}")
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
        # Normalisasi nama_kelas → hilangkan spasi depan/belakang
        if "nama_kelas" in payload and isinstance(payload["nama_kelas"], str):
            payload["nama_kelas"] = payload["nama_kelas"].strip()

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