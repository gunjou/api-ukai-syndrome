from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def role_required(expected_role):
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            jwt_data = get_jwt()
            role = jwt_data.get("role")  # akses role dari claims
            if role != expected_role:
                return {"status": "Forbidden"}, 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper
