from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash
from ..utils.config import get_connection, get_wita

def get_all_peserta():
    engine = get_connection()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT id_user, nama, email, password, kode_pemulihan, role
                FROM users
                WHERE role = 'peserta' 
                  AND status = 1
                  AND nama IS NOT NULL;
            """)).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return []

def insert_peserta(payload):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            payload['hash_password'] = generate_password_hash(payload['password'], method='pbkdf2:sha256')
            result = connection.execute(text("""
                INSERT INTO users (nama, email, password, kode_pemulihan, role, status, created_at, updated_at)
                VALUES (:nama, :email, :hash_password, :kode_pemulihan, 'peserta', 1, :timestamp_wita, :timestamp_wita)
                RETURNING nama
            """), {**payload, "timestamp_wita": get_wita()}).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return None

def get_peserta_by_id(id_peserta):
    engine = get_connection()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT id_user, nama, email, role, kode_pemulihan
                FROM users
                WHERE id_user = :id_peserta AND role = 'peserta' AND status = 1;
            """), {'id_peserta': id_peserta}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return None

def update_peserta(id_peserta, payload):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            fields_to_update = {
                "nama": payload["nama"],
                "email": payload["email"],
                "kode_pemulihan": payload["kode_pemulihan"],
                "updated_at": get_wita()
            }

            if payload["password"]:
                fields_to_update["password"] = generate_password_hash(payload["password"], method='pbkdf2:sha256')
                query = text("""
                    UPDATE users
                    SET nama = :nama, email = :email, password = :password,
                        kode_pemulihan = :kode_pemulihan, updated_at = :updated_at
                    WHERE id_user = :id_peserta AND role = 'peserta' AND status = 1
                    RETURNING nama
                """)
            else:
                query = text("""
                    UPDATE users
                    SET nama = :nama, email = :email,
                        kode_pemulihan = :kode_pemulihan, updated_at = :updated_at
                    WHERE id_user = :id_peserta AND role = 'peserta' AND status = 1
                    RETURNING nama
                """)

            result = connection.execute(query, {**fields_to_update, "id_peserta": id_peserta}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def delete_peserta(id_peserta):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            result = connection.execute(text("""
                UPDATE users
                SET status = 0,
                    updated_at = :timestamp_wita
                WHERE id_user = :id_peserta AND role = 'peserta' AND status = 1
                RETURNING nama;
            """), {
                "id_peserta": id_peserta,
                "timestamp_wita": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None
