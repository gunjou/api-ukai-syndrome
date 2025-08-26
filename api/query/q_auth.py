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
    
def register_peserta(payload):
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Cek duplikat email
            existing = connection.execute(
                text("SELECT 1 FROM users WHERE email = :email AND status = 1"),
                {"email": payload["email"]}
            ).fetchone()
            if existing:
                return False

            connection.execute(
                text("""
                    INSERT INTO users (nama, email, password, kode_pemulihan, role, status, created_at, updated_at)
                    VALUES (:nama, :email, :password, :kode_pemulihan, 'peserta', 1, :created_at, :created_at)
                """),
                {**payload,"created_at": get_wita()}
            )
            return True
    except SQLAlchemyError as e:
        print(f"Register Error: {str(e)}")
        return None