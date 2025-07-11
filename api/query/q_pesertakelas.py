from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..utils.config import get_connection, get_wita

def get_all_pesertakelas():
    engine = get_connection()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT pk.id_pesertakelas, pk.id_user, u.nama, pk.id_paketkelas, p.nama_kelas
            FROM pesertakelas pk
            JOIN users u ON u.id_user = pk.id_user
            JOIN paketkelas p ON p.id_paketkelas = pk.id_paketkelas
            WHERE pk.status = 1
        """)).mappings().fetchall()
        return [dict(row) for row in result]

def get_pesertakelas_by_id(id_pesertakelas):
    engine = get_connection()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id_pesertakelas, id_user, id_paketkelas
            FROM pesertakelas
            WHERE id_pesertakelas = :id AND status = 1
        """), {"id": id_pesertakelas}).mappings().fetchone()
        return dict(result) if result else None

def insert_pesertakelas(data):
    engine = get_connection()
    with engine.begin() as conn:
        # Validasi user
        user_check = conn.execute(text("""
            SELECT id_user FROM users
            WHERE id_user = :id_user AND role = 'peserta' AND status = 1
        """), {"id_user": data["id_user"]}).fetchone()
        if not user_check:
            return None
        
        # Validasi paketkelas
        kelas_check = conn.execute(text("""
            SELECT id_paketkelas FROM paketkelas
            WHERE id_paketkelas = :id_paketkelas AND status = 1
        """), {"id_paketkelas": data["id_paketkelas"]}).fetchone()
        if not kelas_check:
            return None

        # Cek duplikasi
        duplicate = conn.execute(text("""
            SELECT 1 FROM pesertakelas
            WHERE id_user = :id_user AND id_paketkelas = :id_paketkelas AND status = 1
        """), data).fetchone()
        if duplicate:
            return None
        
        result = conn.execute(text("""
            INSERT INTO pesertakelas (id_user, id_paketkelas, status, created_at, updated_at)
            VALUES (:id_user, :id_paketkelas, 1, :now, :now)
            RETURNING id_user, id_paketkelas
        """), {**data, "now": get_wita()}).mappings().fetchone()
        return dict(result)

def update_pesertakelas(id_pesertakelas, data):
    engine = get_connection()
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE pesertakelas
            SET id_user = :id_user,
                id_paketkelas = :id_paketkelas,
                updated_at = :now
            WHERE id_pesertakelas = :id AND status = 1
            RETURNING id_user
        """), {**data, "id": id_pesertakelas, "now": get_wita()}).mappings().fetchone()
        return dict(result) if result else None

def delete_pesertakelas(id_pesertakelas):
    engine = get_connection()
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE pesertakelas
            SET status = 0, updated_at = :now
            WHERE id_pesertakelas = :id AND status = 1
            RETURNING id_user
        """), {"id": id_pesertakelas, "now": get_wita()}).mappings().fetchone()
        return dict(result) if result else None
