import random
import re
import string
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita

def get_all_peserta():
    engine = get_connection()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT 
                    u.id_user,
                    u.nama,
                    u.email,
                    u.no_hp,
                    u.password,
                    u.kode_pemulihan,
                    u.role,
                    b.nama_batch,
                    b.tanggal_mulai,
                    b.tanggal_selesai,
                    ub.tanggal_join,
                    ub.status_enroll,
                    pk.nama_kelas,
                    pk.id_paketkelas,
                    pk.id_batch,
                    p.id_paket,
                    p.nama_paket
                FROM users u
                LEFT JOIN userbatch ub 
                    ON ub.id_user = u.id_user 
                   AND ub.status = 1
                LEFT JOIN batch b 
                    ON b.id_batch = ub.id_batch 
                   AND b.status = 1
                LEFT JOIN pesertakelas pkls 
                    ON pkls.id_user = u.id_user 
                   AND pkls.status = 1
                LEFT JOIN paketkelas pk 
                    ON pk.id_paketkelas = pkls.id_paketkelas 
                   AND pk.status = 1
                LEFT JOIN paket p 
                    ON p.id_paket = pk.id_paket AND p.status = 1
                WHERE u.role = 'peserta'
                  AND u.status = 1
                  AND u.nama IS NOT NULL;
            """)).mappings().fetchall()

            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return []


# def insert_peserta(payload):
#     engine = get_connection()
#     try:
#         with engine.begin() as connection:
#             payload['hash_password'] = generate_password_hash(payload['password'], method='pbkdf2:sha256')
#             result = connection.execute(text("""
#                 INSERT INTO users (nama, email, password, kode_pemulihan, role, status, created_at, updated_at)
#                 VALUES (:nama, :email, :hash_password, :kode_pemulihan, 'peserta', 1, :timestamp_wita, :timestamp_wita)
#                 RETURNING nama
#             """), {**payload, "timestamp_wita": get_wita()}).mappings().fetchone()
#             return dict(result)
#     except SQLAlchemyError as e:
#         print(f"Error occurred: {str(e)}")
#         return None

def insert_peserta_with_batch_kelas(payload):
    engine = get_connection()
    now = datetime.now()

    try:
        with engine.begin() as conn:
            email = payload.get("email")
            id_kelas = payload.get("id_kelas")
            id_batch = payload.get("id_batch")
            nama = payload.get("nama")
            no_hp = payload.get("no_hp")
            password = payload.get("password")

            # 1️⃣ Cek apakah email sudah ada di users
            user = conn.execute(
                text("SELECT id_user, nama FROM users WHERE email = :email"),
                {"email": email}
            ).mappings().fetchone()

            if user:
                id_user = user["id_user"]
                existing_nama = user["nama"]

                # 2️⃣ Cek apakah user sudah ada di kelas
                kelas_check = conn.execute(
                    text("""
                        SELECT * FROM pesertakelas 
                        WHERE id_user = :id_user AND status = 1
                    """),
                    {"id_user": id_user}
                ).mappings().fetchone()

                if kelas_check:
                    # Sudah ada peserta di kelas → return error
                    return {
                        "error": True,
                        "message": "Email sudah terdaftar di kelas ini",
                        "data": {"nama": existing_nama, "email": email}
                    }

            else:
                # Email belum ada → insert ke users
                hash_password = generate_password_hash(password, method='pbkdf2:sha256')
                kode_pemulihan = ''.join(random.choices("0123456789", k=6))

                result = conn.execute(
                    text("""
                        INSERT INTO users (nama, email, password, kode_pemulihan, role, status, created_at, updated_at, no_hp)
                        VALUES (:nama, :email, :password, :kode_pemulihan, 'peserta', 1, :now, :now, :no_hp)
                        RETURNING id_user, nama, email
                    """),
                    {
                        "nama": nama,
                        "email": email,
                        "password": hash_password,
                        "kode_pemulihan": kode_pemulihan,
                        "now": now,
                        "no_hp": no_hp
                    }
                ).mappings().fetchone()

                if not result:
                    return None

                id_user = result["id_user"]

            # 3️⃣ Insert ke pesertakelas
            conn.execute(
                text("""
                    INSERT INTO pesertakelas (id_user, id_paketkelas, status, created_at, updated_at)
                    VALUES (:id_user, :id_kelas, 1, :now, :now)
                """),
                {"id_user": id_user, "id_kelas": id_kelas, "now": now}
            )

            # 4️⃣ Insert ke userbatch
            conn.execute(
                text("""
                    INSERT INTO userbatch (id_user, id_batch, tanggal_join, status, created_at, updated_at)
                    VALUES (:id_user, :id_batch, :tanggal_join, 1, :now, :now)
                """),
                {"id_user": id_user, "id_batch": id_batch, "tanggal_join": now, "now": now}
            )

            return {"id_user": id_user, "nama": nama, "email": email}

    except Exception as e:
        print(f"[ERROR insert_peserta_with_batch_kelas] {e}")
        return None
    
# query/q_peserta.py
def insert_bulk_peserta(peserta_list):
    engine = get_connection()
    now = get_wita()

    try:
        with engine.begin() as conn:
            print(peserta_list)
            emails = [p["email"].strip().lower() for p in peserta_list if p.get("email")]
            if not emails:
                return {"inserted": [], "duplicates": [], "invalid_kelas": []}

            # 1️⃣ Ambil semua email existing
            q_check = text("""
                SELECT email, nama 
                FROM users 
                WHERE lower(email) = ANY(:emails) AND status = 1
            """)
            existing = conn.execute(q_check, {"emails": emails}).mappings().all()
            existing_emails = {row["email"].lower(): row["nama"] for row in existing}

            # 2️⃣ Ambil semua kelas unik dari CSV
            kelas_names = {str(p["kelas"]).strip().lower() for p in peserta_list if p.get("kelas")}
            kelas_in_db = conn.execute(
                text("""
                    SELECT lower(nama_kelas) AS nama_kelas, id_paketkelas, id_batch
                    FROM paketkelas 
                    WHERE lower(nama_kelas) = ANY(:kelas_names) AND status = 1
                """),
                {"kelas_names": list(kelas_names)}
            ).mappings().all()

            kelas_map = {row["nama_kelas"]: row for row in kelas_in_db}
            kelas_not_found = [k for k in kelas_names if k not in kelas_map]

            # 🚨 Kalau ada kelas yang tidak ada → return error
            if kelas_not_found:
                return {
                    "inserted": [],
                    "duplicates": [],
                    "invalid_kelas": [{"kelas": k} for k in kelas_not_found],
                }

            inserted = []
            duplicates = []

            # 3️⃣ Loop peserta
            for peserta in peserta_list:
                email = str(peserta["email"]).strip().lower()

                # ✅ Cek duplikat
                if email in existing_emails:
                    duplicates.append({
                        "nama": peserta.get("nama"),
                        "email": peserta.get("email")
                    })
                    continue

                # ✅ Normalisasi no_hp
                raw_no_hp = str(peserta.get("no_hp", "")).strip() 
                raw_no_hp = re.sub(r"[^\d+]", "", raw_no_hp)# Hapus semua karakter kecuali angka dan '+'
                if raw_no_hp.startswith("'"): # Hapus tanda kutip tunggal di depan
                    raw_no_hp = raw_no_hp[1:] 
                if raw_no_hp.startswith("+62"): # Jika diawali dengan +62 → ganti jadi 0...
                    raw_no_hp = "0" + raw_no_hp[3:] 
                if raw_no_hp and not raw_no_hp.startswith("0"): # Jika tidak kosong dan tidak diawali dengan 0 → tambahkan 0
                    raw_no_hp = "0" + raw_no_hp

                # ✅ Ambil kelas dari mapping (dijamin ada)
                kelas = kelas_map.get(str(peserta.get("kelas")).strip().lower())
                if not kelas:
                    continue  # (safety, meski sudah difilter di atas)

                # ✅ Insert ke users
                hash_password = generate_password_hash("123456", method="pbkdf2:sha256")
                kode_pemulihan = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

                user_result = conn.execute(
                    text("""
                        INSERT INTO users (nama, email, no_hp, password, kode_pemulihan, role, status, created_at, updated_at)
                        VALUES (:nama, :email, :no_hp, :password, :kode_pemulihan, 'peserta', 1, :now, :now)
                        RETURNING id_user, nama, email
                    """),
                    {
                        "nama": str(peserta["nama"]).strip(),
                        "email": email,
                        "no_hp": raw_no_hp,
                        "password": hash_password,
                        "kode_pemulihan": kode_pemulihan,
                        "now": now
                    }
                ).mappings().fetchone()

                if not user_result:
                    continue

                id_user = user_result["id_user"]

                # ✅ Insert ke pesertakelas
                conn.execute(
                    text("""
                        INSERT INTO pesertakelas (id_user, id_paketkelas, status, created_at, updated_at)
                        VALUES (:id_user, :id_paketkelas, 1, :now, :now)
                    """),
                    {"id_user": id_user, "id_paketkelas": kelas["id_paketkelas"], "now": now}
                )

                # ✅ Insert ke userbatch
                conn.execute(
                    text("""
                        INSERT INTO userbatch (id_user, id_batch, tanggal_join, status, created_at, updated_at)
                        VALUES (:id_user, :id_batch, :tanggal_join, 1, :now, :now)
                    """),
                    {"id_user": id_user, "id_batch": kelas["id_batch"], "tanggal_join": now, "now": now}
                )

                inserted.append({
                    "id_user": id_user,
                    "nama": user_result["nama"],
                    "email": user_result["email"]
                })

            return {
                "inserted": inserted,
                "duplicates": duplicates,
                "invalid_kelas": []
            }

    except SQLAlchemyError as e:
        print(f"[ERROR insert_bulk_peserta] {e}")
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
    now = get_wita()
    try:
        with engine.begin() as connection:
            # --- Ambil data lama peserta ---
            old_data = connection.execute(
                text("""
                    SELECT u.id_user, u.nama, u.email, u.no_hp, u.password, u.kode_pemulihan,
                           pk.id_paketkelas AS id_kelas,
                           ub.id_batch
                    FROM users u
                    LEFT JOIN pesertakelas pk ON pk.id_user = u.id_user AND pk.status = 1
                    LEFT JOIN userbatch ub ON ub.id_user = u.id_user AND ub.status = 1
                    WHERE u.id_user = :id_peserta AND u.role = 'peserta' AND u.status = 1
                """),
                {"id_peserta": id_peserta}
            ).mappings().fetchone()

            if not old_data:
                return None

            # --- Users update ---
            # ✅ Normalisasi no_hp
            raw_no_hp = str(payload.get("no_hp", "")).strip() 
            raw_no_hp = re.sub(r"[^\d+]", "", raw_no_hp)# Hapus semua karakter kecuali angka dan '+'
            if raw_no_hp.startswith("'"): # Hapus tanda kutip tunggal di depan
                raw_no_hp = raw_no_hp[1:] 
            if raw_no_hp.startswith("+62"): # Jika diawali dengan +62 → ganti jadi 0...
                raw_no_hp = "0" + raw_no_hp[3:] 
            if raw_no_hp and not raw_no_hp.startswith("0"): # Jika tidak kosong dan tidak diawali dengan 0 → tambahkan 0
                raw_no_hp = "0" + raw_no_hp

            fields_to_update = {
                "nama": payload.get("nama", old_data["nama"]),
                "email": payload.get("email", old_data["email"]),
                "kode_pemulihan": payload.get("kode_pemulihan", old_data["kode_pemulihan"]),
                "no_hp": raw_no_hp,
                "updated_at": now,
                "id_peserta": id_peserta
            }

            if payload.get("password"):  # password hanya diupdate jika tidak kosong/null
                fields_to_update["password"] = generate_password_hash(payload["password"], method='pbkdf2:sha256')
                query_users = text("""
                    UPDATE users
                    SET nama = :nama, email = :email, password = :password,
                        kode_pemulihan = :kode_pemulihan, no_hp = :no_hp,
                        updated_at = :updated_at
                    WHERE id_user = :id_peserta AND role = 'peserta' AND status = 1
                    RETURNING nama
                """)
            else:
                query_users = text("""
                    UPDATE users
                    SET nama = :nama, email = :email,
                        kode_pemulihan = :kode_pemulihan, no_hp = :no_hp,
                        updated_at = :updated_at
                    WHERE id_user = :id_peserta AND role = 'peserta' AND status = 1
                    RETURNING nama
                """)

            result = connection.execute(query_users, fields_to_update).mappings().fetchone()
            if not result:
                return None

            # --- Pesertakelas update ---
            id_kelas_baru = payload.get("id_kelas", old_data["id_kelas"])
            if id_kelas_baru != old_data["id_kelas"]:
                connection.execute(
                    text("""
                        UPDATE pesertakelas
                        SET id_paketkelas = :id_kelas,
                            updated_at = :now
                        WHERE id_user = :id_peserta AND status = 1
                    """),
                    {"id_kelas": id_kelas_baru, "id_peserta": id_peserta, "now": now}
                )

            # --- Userbatch update ---
            id_batch_baru = payload.get("id_batch", old_data["id_batch"])
            if id_batch_baru != old_data["id_batch"]:
                connection.execute(
                    text("""
                        UPDATE userbatch
                        SET id_batch = :id_batch,
                            updated_at = :now
                        WHERE id_user = :id_peserta AND status = 1
                    """),
                    {"id_batch": id_batch_baru, "id_peserta": id_peserta, "now": now}
                )

            return dict(result)

    except SQLAlchemyError as e:
        print(f"[ERROR update_peserta] {e}")
        return None


# def delete_peserta(id_peserta):
#     engine = get_connection()
#     try:
#         with engine.begin() as connection:
#             result = connection.execute(text("""
#                 UPDATE users
#                 SET status = 0,
#                     updated_at = :timestamp_wita
#                 WHERE id_user = :id_peserta AND role = 'peserta' AND status = 1
#                 RETURNING nama;
#             """), {
#                 "id_peserta": id_peserta,
#                 "timestamp_wita": get_wita()
#             }).mappings().fetchone()
#             return dict(result) if result else None
#     except SQLAlchemyError as e:
#         print(f"Error: {e}")
#         return None

def delete_peserta(id_peserta):
    engine = get_connection()
    now = get_wita()
    try:
        with engine.begin() as connection:
            # 1️⃣ Nonaktifkan pesertakelas
            connection.execute(
                text("""
                    UPDATE pesertakelas
                    SET status = 0,
                        updated_at = :now
                    WHERE id_user = :id_user AND status = 1
                """),
                {"id_user": id_peserta, "now": now}
            )

            # 2️⃣ Nonaktifkan userbatch
            connection.execute(
                text("""
                    UPDATE userbatch
                    SET status = 0,
                        updated_at = :now
                    WHERE id_user = :id_user AND status = 1
                """),
                {"id_user": id_peserta, "now": now}
            )

            # 3️⃣ Nonaktifkan users
            result = connection.execute(
                text("""
                    UPDATE users
                    SET status = 0,
                        updated_at = :now
                    WHERE id_user = :id_user AND role = 'peserta' AND status = 1
                    RETURNING nama
                """),
                {"id_user": id_peserta, "now": now}
            ).mappings().fetchone()

            return dict(result) if result else None

    except SQLAlchemyError as e:
        print(f"[ERROR delete_peserta] {e}")
        return None

