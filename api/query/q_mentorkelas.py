from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..utils.config import get_connection, get_wita

def get_all_mentorkelas():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT mk.id_mentorkelas, u.id_user, u.nama as nama_mentor, u.email,
                       pk.id_paketkelas, pk.nama_kelas
                FROM mentorkelas mk
                JOIN users u ON mk.id_user = u.id_user
                JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas
                WHERE mk.status = 1
                ORDER BY mk.id_mentorkelas DESC
            """)).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return []

def get_mentorkelas_by_id(id_mentorkelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT mk.id_mentorkelas, u.id_user, u.nama as nama_mentor, u.email,
                       pk.id_paketkelas, pk.nama_kelas
                FROM mentorkelas mk
                JOIN users u ON mk.id_user = u.id_user
                JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas
                WHERE mk.id_mentorkelas = :id AND mk.status = 1
            """), {"id": id_mentorkelas}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def is_valid_mentor(id_user):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_user FROM users
                WHERE id_user = :id_user AND role = 'mentor' AND status = 1
            """), {"id_user": id_user}).scalar()
            return result is not None
    except SQLAlchemyError:
        return False

def is_valid_kelas(id_paketkelas):
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

def insert_mentorkelas(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO mentorkelas (id_user, id_paketkelas, status, created_at, updated_at)
                VALUES (:id_user, :id_paketkelas, 1, :now, :now)
                RETURNING id_mentorkelas
            """), {
                **payload,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def update_mentorkelas(id_mentorkelas, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE mentorkelas
                SET id_user = :id_user,
                    id_paketkelas = :id_paketkelas,
                    updated_at = :now
                WHERE id_mentorkelas = :id AND status = 1
                RETURNING id_mentorkelas
            """), {
                **payload,
                "id": id_mentorkelas,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def delete_mentorkelas(id_mentorkelas):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE mentorkelas
                SET status = 0, updated_at = :now
                WHERE id_mentorkelas = :id AND status = 1
                RETURNING id_mentorkelas
            """), {
                "id": id_mentorkelas,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None
