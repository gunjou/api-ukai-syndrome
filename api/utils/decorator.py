from functools import wraps
from sqlalchemy import text
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, get_jwt

from .config import get_connection

def role_required(expected_roles):
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            jwt_data = get_jwt()
            role = jwt_data.get("role")

            # Cek apakah `expected_roles` adalah list/tuple/set
            if isinstance(expected_roles, (list, tuple, set)):
                if role not in expected_roles:
                    return {"status": "Forbidden", "message": "Role tidak diizinkan"}, 403
            else:
                if role != expected_roles:
                    return {"status": "Forbidden", "message": "Role tidak diizinkan"}, 403

            return fn(*args, **kwargs)
        return decorator
    return wrapper

def session_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Step 1: Verify JWT
        verify_jwt_in_request()
        claims = get_jwt()
        user_id = get_jwt_identity()
        role = claims.get("role")

        # Step 2: Jika role peserta → validasi session
        if role == "peserta":
            session_id = claims.get("session_id")
            device_type = claims.get("device_type")

            engine = get_connection()
            with engine.connect() as connection:
                result = connection.execute(
                    text("""
                        SELECT id_session 
                        FROM sessions 
                        WHERE id_user = :user_id 
                          AND session_id = :session_id 
                          AND device_type = :device_type
                          AND status = 1
                        LIMIT 1
                    """),
                    {
                        "user_id": user_id,
                        "session_id": session_id,
                        "device_type": device_type
                    }
                ).fetchone()

            if not result:
                return {"message": "Session invalid or expired"}, 401

        # Kalau role bukan peserta → skip validasi session
        return fn(*args, **kwargs)
    return wrapper