from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt

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
