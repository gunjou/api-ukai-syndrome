import random
import string
import uuid
from flask_jwt_extended import create_access_token
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash

from ..utils.config import get_connection, get_wita


def get_user_by_id(user_id):
    engine = get_connection()
    with engine.connect() as connection:
        result = connection.execute(text("""
            SELECT id_user, nama, email, role, status
            FROM users
            WHERE id_user = :id_user AND status = 1
        """), {"id_user": user_id}).mappings().fetchone()
        return dict(result) if result else None

def get_login(payload):
    engine = get_connection()
    try:
        with engine.connect() as connection:
            # Ambil data user + join ke kelas
            result = connection.execute(
                text("""
                    SELECT u.id_user, u.nama, u.email, u.password, u.role, u.status,
                           pk.nama_kelas
                    FROM users u
                    LEFT JOIN pesertakelas pkls ON u.id_user = pkls.id_user AND pkls.status = 1
                    LEFT JOIN paketkelas pk ON pkls.id_paketkelas = pk.id_paketkelas AND pk.status = 1
                    WHERE u.email = :email
                    AND u.status = 1
                    LIMIT 1;
                """),
                {"email": payload['email']}
            ).mappings().fetchone()

            # Cek apakah password ada dan cocok dengan hash
            if result and result['password']:
                if check_password_hash(result['password'], payload['password']):
                    access_token = create_access_token(
                        identity=str(result['id_user']),
                        additional_claims={"role": result['role']}
                    )
                    return {
                        'access_token': access_token,
                        'message': 'login success',
                        'id_user': result['id_user'],
                        'nama': result['nama'],
                        'email': result['email'],
                        'role': result['role'],
                        'nama_kelas': result['nama_kelas']  # Bisa NULL kalau belum ikut kelas
                    }
            return None
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return {'msg': 'Internal server error'}
    
def ambil_kelas_saya(id_user):
    engine = get_connection()
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT u.id_user, u.nama, u.email, u.role, u.status,
                           pk.id_paketkelas, pk.nama_kelas
                    FROM users u
                    LEFT JOIN pesertakelas pkls ON u.id_user = pkls.id_user AND pkls.status = 1
                    LEFT JOIN paketkelas pk ON pkls.id_paketkelas = pk.id_paketkelas AND pk.status = 1
                    WHERE u.id_user = :id_user
                    AND u.status = 1
                    LIMIT 1;
                """),
                {"id_user": id_user}
            ).mappings().fetchone()

            if result:
                return {
                    'id_user': result['id_user'],
                    'nama': result['nama'],
                    'email': result['email'],
                    'role': result['role'],
                    'status': result['status'],
                    'id_kelas': result['id_paketkelas'],   # bisa NULL kalau belum ikut kelas
                    'nama_kelas': result['nama_kelas']     # bisa NULL kalau belum ikut kelas
                }
            return None
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return {'msg': 'Internal server error'}
    
def get_login_web(payload):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Ambil data user
            result = connection.execute(
                text("""
                    SELECT u.id_user, u.nama, u.email, u.password, u.role, u.status,
                           pk.nama_kelas
                    FROM users u
                    LEFT JOIN pesertakelas pkls ON u.id_user = pkls.id_user AND pkls.status = 1
                    LEFT JOIN paketkelas pk ON pkls.id_paketkelas = pk.id_paketkelas AND pk.status = 1
                    WHERE u.email = :email
                    AND u.status = 1
                    LIMIT 1;
                """),
                {"email": payload['email']}
            ).mappings().fetchone()

            if result and result['password']:
                if check_password_hash(result['password'], payload['password']):
                    # 🔑 Kalau role = admin / mentor → return sederhana
                    if result['role'] in ["admin", "mentor"]:
                        access_token = create_access_token(
                            identity=str(result['id_user']),
                            additional_claims={"role": result['role']}
                        )
                        return {
                            'access_token': access_token,
                            'message': 'login success',
                            'id_user': result['id_user'],
                            'nama': result['nama'],
                            'email': result['email'],
                            'role': result['role'],
                            'nama_kelas': result['nama_kelas']  # Bisa NULL
                        }

                    # 🔑 Kalau role = peserta → pakai mekanisme session (seperti kode awalmu)
                    new_session_id = str(uuid.uuid4())

                    access_token = create_access_token(
                        identity=str(result['id_user']),
                        additional_claims={
                            "role": result['role'],
                            "session_id": new_session_id,
                            "device_type": "web"
                        }
                    )

                    # Cek apakah sudah ada session lama
                    old_session = connection.execute(
                        text("""
                            SELECT id_session FROM sessions
                            WHERE id_user = :id_user AND device_type = 'web'
                            LIMIT 1
                        """),
                        {"id_user": result['id_user']}
                    ).fetchone()

                    if old_session:
                        connection.execute(
                            text("""
                                UPDATE sessions
                                SET session_id = :session_id,
                                    jwt_token = :jwt_token,
                                    status = 1,
                                    updated_at = NOW()
                                WHERE id_session = :id_session
                            """),
                            {
                                "session_id": new_session_id,
                                "jwt_token": access_token,
                                "id_session": old_session.id_session
                            }
                        )
                    else:
                        connection.execute(
                            text("""
                                INSERT INTO sessions (id_user, device_type, session_id, jwt_token, status, created_at, updated_at)
                                VALUES (:id_user, 'web', :session_id, :jwt_token, 1, NOW(), NOW())
                            """),
                            {
                                "id_user": result['id_user'],
                                "session_id": new_session_id,
                                "jwt_token": access_token
                            }
                        )

                    return {
                        'access_token': access_token,
                        'message': 'login success',
                        'id_user': result['id_user'],
                        'nama': result['nama'],
                        'email': result['email'],
                        'role': result['role'],
                        'nama_kelas': result['nama_kelas']
                    }

        return None
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return {'msg': 'Internal server error'}
    
def get_login_mobile(payload):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Ambil data user
            result = connection.execute(
                text("""
                    SELECT u.id_user, u.nama, u.email, u.password, u.role, u.status,
                           pk.nama_kelas
                    FROM users u
                    LEFT JOIN pesertakelas pkls ON u.id_user = pkls.id_user AND pkls.status = 1
                    LEFT JOIN paketkelas pk ON pkls.id_paketkelas = pk.id_paketkelas AND pk.status = 1
                    WHERE u.email = :email
                    AND u.status = 1
                    LIMIT 1;
                """),
                {"email": payload['email']}
            ).mappings().fetchone()

            if result and result['password']:
                if check_password_hash(result['password'], payload['password']):
                    # Generate session baru
                    new_session_id = str(uuid.uuid4())

                    # Buat JWT baru dengan session_id
                    access_token = create_access_token(
                        identity=str(result['id_user']),
                        additional_claims={
                            "role": result['role'],
                            "session_id": new_session_id,
                            "device_type": "mobile"
                        }
                    )

                    # Cek apakah ada session existing
                    old_session = connection.execute(
                        text("""
                            SELECT id_session FROM sessions
                            WHERE id_user = :id_user AND device_type = 'mobile'
                            LIMIT 1
                        """),
                        {"id_user": result['id_user']}
                    ).fetchone()

                    if old_session:
                        # Update session lama jadi session baru
                        connection.execute(
                            text("""
                                UPDATE sessions
                                SET session_id = :session_id,
                                    jwt_token = :jwt_token,
                                    status = 1,
                                    updated_at = NOW()
                                WHERE id_session = :id_session
                            """),
                            {
                                "session_id": new_session_id,
                                "jwt_token": access_token,
                                "id_session": old_session.id_session
                            }
                        )
                    else:
                        # Kalau belum ada → insert session baru
                        connection.execute(
                            text("""
                                INSERT INTO sessions (id_user, device_type, session_id, jwt_token, status, created_at, updated_at)
                                VALUES (:id_user, 'mobile', :session_id, :jwt_token, 1, NOW(), NOW())
                            """),
                            {
                                "id_user": result['id_user'],
                                "session_id": new_session_id,
                                "jwt_token": access_token
                            }
                        )

                    return {
                        'access_token': access_token,
                        'message': 'login success',
                        'id_user': result['id_user'],
                        'nama': result['nama'],
                        'email': result['email'],
                        'role': result['role'],
                        'nama_kelas': result['nama_kelas']
                    }

        return None
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return {'msg': 'Internal server error'}
    
# def register_peserta(payload):
#     engine = get_connection()
#     try:
#         with engine.begin() as connection:
#             # Cek duplikat email
#             existing = connection.execute(
#                 text("SELECT 1 FROM users WHERE email = :email AND status = 1"),
#                 {"email": payload["email"]}
#             ).fetchone()
#             if existing:
#                 return False

#             connection.execute(
#                 text("""
#                     INSERT INTO users (nama, email, password, kode_pemulihan, role, status, created_at, updated_at)
#                     VALUES (:nama, :email, :password, :kode_pemulihan, 'peserta', 1, :created_at, :created_at)
#                 """),
#                 {**payload,"created_at": get_wita()}
#             )
#             return True
#     except SQLAlchemyError as e:
#         print(f"Register Error: {str(e)}")
#         return None

# query/q_auth.py
import random
from sqlalchemy import text

def register_step1(email):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Cek apakah email sudah ada dengan nama terisi
            existing_full = connection.execute(
                text("SELECT 1 FROM users WHERE email = :email AND nama IS NOT NULL AND status = 1"),
                {"email": email}
            ).fetchone()

            if existing_full:
                # Sudah ada akun dengan nama → tidak boleh daftar ulang
                return False, None

            # Kode pemulihan hanya angka (6 digit)
            kode_pemulihan = ''.join(random.choice("0123456789") for _ in range(6))

            # Cek apakah email ada tapi nama masih NULL
            existing_empty = connection.execute(
                text("SELECT 1 FROM users WHERE email = :email AND nama IS NULL AND status = 1"),
                {"email": email}
            ).fetchone()

            if existing_empty:
                # Update kode pemulihan saja
                connection.execute(
                    text("""
                        UPDATE users
                        SET kode_pemulihan = :kode_pemulihan,
                            updated_at = NOW()
                        WHERE email = :email AND nama IS NULL AND status = 1
                    """),
                    {"email": email, "kode_pemulihan": kode_pemulihan}
                )
                return True, kode_pemulihan

            # Kalau belum ada sama sekali → insert baru
            connection.execute(
                text("""
                    INSERT INTO users (email, kode_pemulihan, role, status, created_at, updated_at)
                    VALUES (:email, :kode_pemulihan, 'peserta', 1, NOW(), NOW())
                """),
                {"email": email, "kode_pemulihan": kode_pemulihan}
            )
            return True, kode_pemulihan

    except Exception as e:
        print(f"Register Step1 Error: {e}")
        return None, None

def register_step2(email, kode_pemulihan):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            user = connection.execute(
                text("""
                    SELECT id_user FROM users
                    WHERE email = :email AND kode_pemulihan = :kode_pemulihan AND status = 1
                """),
                {"email": email, "kode_pemulihan": kode_pemulihan}
            ).fetchone()

            if not user:
                return False

            # opsional: update status jadi "verified" (misalnya status = 2)
            connection.execute(
                text("""
                    UPDATE users
                    SET updated_at = :updated_at
                    WHERE id_user = :id_user
                """),
                {"id_user": user.id_user, "updated_at": get_wita()}
            )
            return True
    except SQLAlchemyError as e:
        print(f"Register Step 2 Error: {str(e)}")
        return None

def register_step3(email, nama, no_hp, hashed_password):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("SELECT id_user FROM users WHERE email = :email AND status = 1"),
                {"email": email}
            ).fetchone()

            if not result:
                return False
            
            kode_pemulihan = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(6))

            connection.execute(
                text("""
                    UPDATE users
                    SET nama = :nama,
                        no_hp = :no_hp,
                        kode_pemulihan = :kode_pemulihan,
                        password = :password,
                        updated_at = :updated_at
                    WHERE id_user = :id_user
                """),
                {
                    "id_user": result.id_user,
                    "nama": nama,
                    "no_hp": no_hp,
                    "kode_pemulihan": kode_pemulihan,
                    "password": hashed_password,
                    "updated_at": get_wita()
                }
            )
            return True
    except SQLAlchemyError as e:
        print(f"Register Step 3 Error: {str(e)}")
        return None
