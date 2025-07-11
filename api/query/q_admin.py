from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from ..utils.config import get_connection, get_wita


# query/q_admin.py
def get_all_admin():
    engine = get_connection()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT id_user, nama, email, password, kode_pemulihan, role
                FROM users
                WHERE role = 'admin' AND status = 1;   
            """)).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return []
    
# query/q_admin.py
def insert_admin(payload):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            payload['hash_password'] = generate_password_hash(payload['password'], method='pbkdf2:sha256')
            result = connection.execute(text("""
                INSERT INTO users (nama, email, password, kode_pemulihan, role, status, created_at, updated_at)
                VALUES (:nama, :email, :hash_password, :kode_pemulihan, 'admin', 1, :timestamp_wita, :timestamp_wita)
                RETURNING nama
            """), {**payload, "timestamp_wita": get_wita()}).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return None
    
def get_admin_by_id(id_admin):
    engine = get_connection()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT id_user, nama, email, role, kode_pemulihan
                FROM users
                WHERE id_user = :id_admin AND role = 'admin' AND status = 1;
            """), {'id_admin': id_admin}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return None

def update_admin(id_admin, payload):
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
                    SET nama = :nama, email = :email, password = :password, kode_pemulihan = :kode_pemulihan,
                        updated_at = :updated_at
                    WHERE id_user = :id_admin AND role = 'admin' AND status = 1
                    RETURNING nama
                """)
            else:
                query = text("""
                    UPDATE users
                    SET nama = :nama, email = :email, kode_pemulihan = :kode_pemulihan,
                        updated_at = :updated_at
                    WHERE id_user = :id_admin AND role = 'admin' AND status = 1
                    RETURNING nama
                """)

            result = connection.execute(query, {**fields_to_update, "id_admin": id_admin}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None
    
def delete_admin(id_admin):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            result = connection.execute(text("""
                UPDATE users
                SET status = 0,
                    updated_at = :timestamp_wita
                WHERE id_user = :id_admin AND role = 'admin' AND status = 1
                RETURNING nama;
            """), {
                "id_admin": id_admin,
                "timestamp_wita": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None
