from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from ..utils.config import get_connection, get_wita


def get_user_by_id(user_id):
    engine = get_connection()
    with engine.connect() as connection:
        result = connection.execute(text("""
            SELECT id_user, nama, email, no_hp, role, status
            FROM users
            WHERE id_user = :id_user AND status = 1
        """), {"id_user": user_id}).mappings().fetchone()
        return dict(result) if result else None
    
def update_profile(id_user, nama=None, email=None, no_hp=None):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            fields_to_update = []
            params = {"id_user": id_user, "now": get_wita()}

            if nama:
                fields_to_update.append("nama = :nama")
                params["nama"] = nama
            if email:
                fields_to_update.append("email = :email")
                params["email"] = email
            if no_hp:
                fields_to_update.append("no_hp = :no_hp")
                params["no_hp"] = no_hp

            if not fields_to_update:
                return {"status": "error", "message": "Tidak ada data untuk diperbarui"}, 400

            set_clause = ", ".join(fields_to_update)

            conn.execute(
                text(f"""
                    UPDATE users
                    SET {set_clause}, updated_at = :now
                    WHERE id_user = :id_user
                      AND status = 1
                """),
                params
            )

            return {"status": "success", "message": "Profil berhasil diperbarui"}, 200

    except SQLAlchemyError as e:
        print(f"[update_profile] Error: {str(e)}")
        return {"status": "error", "message": "Internal server error"}, 500
    
def change_password(id_user, password_lama, password_baru, konfirmasi_password_baru):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # 🔎 Ambil password lama user
            user = conn.execute(
                text("SELECT password FROM users WHERE id_user = :id_user AND status = 1 LIMIT 1"),
                {"id_user": id_user}
            ).mappings().fetchone()
            if not user:
                return {"status": "error", "message": "User tidak ditemukan"}, 404
            # ✅ Cek password lama
            if not check_password_hash(user['password'], password_lama):
                return {"status": "error", "message": "Password lama tidak sesuai"}, 400
            # ✅ Validasi password baru dan konfirmasi
            if password_baru != konfirmasi_password_baru:
                return {"status": "error", "message": "Konfirmasi password baru tidak cocok"}, 400
            # 🔐 Hash password baru
            hashed_new_password = generate_password_hash(password_baru, method='pbkdf2:sha256')
            # 🔄 Update password
            conn.execute(
                text("""
                    UPDATE users
                    SET password = :password, updated_at = NOW()
                    WHERE id_user = :id_user
                """),
                {"password": hashed_new_password, "id_user": id_user}
            )

            return {"status": "success", "message": "Password berhasil diperbarui"}, 200

    except SQLAlchemyError as e:
        print(f"[change_password] Error: {str(e)}")
        return {"status": "error", "message": "Internal server error"}, 500
    
def ambil_kelas_saya(id_user, role):
    engine = get_connection()
    try:
        with engine.connect() as connection:
            # Ambil data user dulu
            user_result = connection.execute(
                text("""
                    SELECT id_user, nama, email, no_hp, role, status
                    FROM users
                    WHERE id_user = :id_user AND status = 1
                    LIMIT 1
                """),
                {"id_user": id_user}
            ).mappings().fetchone()

            if not user_result:
                return None

            response = {
                "id_user": user_result["id_user"],
                "nama": user_result["nama"],
                "email": user_result["email"],
                "role": user_result["role"],
                "status": user_result["status"],
                "id_paketkelas": None,
                "nama_kelas": None
            }

            if role == "peserta":
                kelas_result = connection.execute(
                    text("""
                        SELECT pk.id_paketkelas, pk.nama_kelas
                        FROM pesertakelas pkls
                        JOIN paketkelas pk ON pkls.id_paketkelas = pk.id_paketkelas
                        WHERE pkls.id_user = :id_user
                          AND pkls.status = 1
                          AND pk.status = 1
                        LIMIT 1
                    """),
                    {"id_user": id_user}
                ).mappings().fetchone()

                if kelas_result:
                    response["id_paketkelas"] = kelas_result["id_paketkelas"]
                    response["nama_kelas"] = kelas_result["nama_kelas"]

            elif role == "mentor":
                kelas_result = connection.execute(
                    text("""
                        SELECT pk.id_paketkelas, pk.nama_kelas
                        FROM mentorkelas mk
                        JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas
                        WHERE mk.id_user = :id_user
                          AND mk.status = 1
                          AND pk.status = 1
                        LIMIT 1
                    """),
                    {"id_user": id_user}
                ).mappings().fetchone()

                if kelas_result:
                    response["id_paketkelas"] = kelas_result["id_paketkelas"]
                    response["nama_kelas"] = kelas_result["nama_kelas"]

            return response

    except SQLAlchemyError as e:
        print(f"[ambil_kelas_saya] Error: {str(e)}")
        return {"msg": "Internal server error"}
