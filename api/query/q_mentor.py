import re
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash
from ..utils.config import get_connection, get_wita

def get_all_mentor():
    engine = get_connection()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT 
                    u.id_user, u.nama, u.email, u.kode_pemulihan, u.password, u.no_hp, u.role,
                    pk.id_paketkelas, pk.nama_kelas, p.id_paket, p.nama_paket, pk.deskripsi, 
                    b.id_batch, b.nama_batch
                FROM users u
                LEFT JOIN mentorkelas mk 
                    ON u.id_user = mk.id_user AND mk.status = 1
                LEFT JOIN paketkelas pk 
                    ON mk.id_paketkelas = pk.id_paketkelas AND pk.status = 1
                LEFT JOIN paket p 
                    ON p.id_paket = pk.id_paket AND p.status = 1
                LEFT JOIN batch b 
                    ON b.id_batch = pk.id_batch AND b.status = 1
                WHERE u.role = 'mentor' AND u.status = 1
                ORDER BY u.nama ASC;
            """)).mappings().fetchall()

            rows = [dict(row) for row in result]
            mentors = {}

            for row in rows:
                uid = row["id_user"]
                if uid not in mentors:
                    mentors[uid] = {
                        "id_user": row["id_user"],
                        "nama": row["nama"],
                        "email": row["email"],
                        "kode_pemulihan": row["kode_pemulihan"],
                        "password": row["password"],
                        "no_hp": row["no_hp"],
                        "role": row["role"],
                        "total_kelas": 0,
                        "paketkelas": []  # kumpulan kelas
                    }

                # Kalau ada kelas yang valid, tambahkan ke list
                if row["id_paketkelas"]:
                    mentors[uid]["paketkelas"].append({
                        "id_paketkelas": row["id_paketkelas"],
                        "nama_kelas": row["nama_kelas"],
                        "id_paket": row["id_paket"],
                        "nama_paket": row["nama_paket"],
                        "deskripsi": row["deskripsi"],
                        "id_batch": row["id_batch"],
                        "nama_batch": row["nama_batch"]
                    })

            # Hitung total kelas per mentor
            for mentor in mentors.values():
                mentor["total_kelas"] = len(mentor["paketkelas"])

            return list(mentors.values())
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return []

def insert_mentor(payload):
    engine = get_connection()
    now = get_wita()
    try:
        with engine.begin() as connection:
            email = payload.get("email").strip().lower()

            # 🔍 Cek apakah email sudah terdaftar untuk mentor aktif
            check = connection.execute(text("""
                SELECT id_user, nama FROM users 
                WHERE lower(email) = :email 
                  AND role = 'mentor' 
                  AND status = 1
            """), {"email": email}).mappings().fetchone()

            if check:
                return {
                    "error": True,
                    "message": f"Email {email} sudah terdaftar untuk mentor aktif",
                    "data": {"nama": check["nama"], "email": email}
                }

            # Hash password
            payload['hash_password'] = generate_password_hash(
                payload['password'], method='pbkdf2:sha256'
            )

            # ✅ Normalisasi no_hp
            raw_no_hp = payload.get("no_hp")
            if not raw_no_hp or str(raw_no_hp).strip() == "":
                raw_no_hp = None 
            else:
                raw_no_hp = str(payload.get("no_hp", "")).strip() 
                raw_no_hp = re.sub(r"[^\d+]", "", raw_no_hp)# Hapus semua karakter kecuali angka dan '+'
                if raw_no_hp.startswith("'"): # Hapus tanda kutip tunggal di depan
                    raw_no_hp = raw_no_hp[1:] 
                if raw_no_hp.startswith("+62"): # Jika diawali dengan +62 → ganti jadi 0...
                    raw_no_hp = "0" + raw_no_hp[3:] 
                if raw_no_hp and not raw_no_hp.startswith("0"): # Jika tidak kosong dan tidak diawali dengan 0 → tambahkan 0
                    raw_no_hp = "0" + raw_no_hp

            # ✅ Insert ke users
            user_result = connection.execute(text("""
                INSERT INTO users (nama, email, password, kode_pemulihan, role, status, created_at, updated_at, no_hp)
                VALUES (:nama, :email, :hash_password, :kode_pemulihan, 'mentor', 1, :now, :now, :no_hp)
                RETURNING id_user, nama, email
            """), {
                **payload,
                "email": email,
                "now": now,
                "no_hp": raw_no_hp
            }).mappings().fetchone()

            if not user_result:
                return None

            id_user = user_result["id_user"]

            # ✅ Insert ke mentorkelas (opsional)
            if payload.get("id_paketkelas"):
                connection.execute(text("""
                    INSERT INTO mentorkelas (id_user, id_paketkelas, status, created_at, updated_at)
                    VALUES (:id_user, :id_paketkelas, 1, :now, :now)
                """), {
                    "id_user": id_user,
                    "id_paketkelas": payload["id_paketkelas"],
                    "now": now
                })

            return {
                "id_user": id_user,
                "nama": user_result["nama"],
                "email": user_result["email"],
                "id_paketkelas": payload.get("id_paketkelas")  # bisa None
            }

    except SQLAlchemyError as e:
        print(f"[ERROR insert_mentor] {e}")
        return None

def get_mentor_by_id(id_mentor):
    engine = get_connection()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT id_user, nama, email, role, kode_pemulihan
                FROM users
                WHERE id_user = :id_mentor AND role = 'mentor' AND status = 1;
            """), {'id_mentor': id_mentor}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error occurred: {str(e)}")
        return None

def update_mentor(id_mentor, payload):
    engine = get_connection()
    now = get_wita()

    try:
        with engine.begin() as connection:
            # ✅ Normalisasi no_hp
            raw_no_hp = str(payload.get("no_hp", "")).strip() 
            raw_no_hp = re.sub(r"[^\d+]", "", raw_no_hp)# Hapus semua karakter kecuali angka dan '+'
            if raw_no_hp.startswith("'"): # Hapus tanda kutip tunggal di depan
                raw_no_hp = raw_no_hp[1:] 
            if raw_no_hp.startswith("+62"): # Jika diawali dengan +62 → ganti jadi 0...
                raw_no_hp = "0" + raw_no_hp[3:] 
            if raw_no_hp and not raw_no_hp.startswith("0"): # Jika tidak kosong dan tidak diawali dengan 0 → tambahkan 0
                raw_no_hp = "0" + raw_no_hp
                
            # --- Update data di users ---
            fields_to_update = {
                "nama": payload["nama"],
                "email": payload["email"],
                "no_hp": raw_no_hp if payload.get("no_hp") != "" else None,
                "kode_pemulihan": payload["kode_pemulihan"],
                "updated_at": now
            }

            if payload.get("password"):
                fields_to_update["password"] = generate_password_hash(payload["password"], method='pbkdf2:sha256')
                query_user = text("""
                    UPDATE users
                    SET nama = :nama, email = :email, no_hp = :no_hp,
                        password = :password, kode_pemulihan = :kode_pemulihan, 
                        updated_at = :updated_at
                    WHERE id_user = :id_mentor AND role = 'mentor' AND status = 1
                    RETURNING id_user, nama;
                """)
            else:
                query_user = text("""
                    UPDATE users
                    SET nama = :nama, email = :email, no_hp = :no_hp,
                        kode_pemulihan = :kode_pemulihan, updated_at = :updated_at
                    WHERE id_user = :id_mentor AND role = 'mentor' AND status = 1
                    RETURNING id_user, nama;
                """)

            user_result = connection.execute(query_user, {**fields_to_update, "id_mentor": id_mentor}).mappings().fetchone()
            if not user_result:
                return None

            # --- Handle data mentorkelas ---
            new_paketkelas = payload.get("id_paketkelas")

            # Cek apakah mentor sudah punya kelas aktif
            old_class = connection.execute(text("""
                SELECT id_mentorkelas, id_paketkelas
                FROM mentorkelas
                WHERE id_user = :id_mentor AND status = 1
                LIMIT 1;
            """), {"id_mentor": id_mentor}).mappings().fetchone()

            if not old_class and new_paketkelas:  
                # Case 1: belum ada kelas → insert baru
                connection.execute(text("""
                    INSERT INTO mentorkelas (id_user, id_paketkelas, status, created_at, updated_at)
                    VALUES (:id_mentor, :id_paketkelas, 1, :now, :now);
                """), {"id_mentor": id_mentor, "id_paketkelas": new_paketkelas, "now": now})

            elif old_class and new_paketkelas and old_class["id_paketkelas"] != new_paketkelas:  
                # Case 2: sudah ada kelas → update ke kelas baru
                connection.execute(text("""
                    UPDATE mentorkelas
                    SET id_paketkelas = :id_paketkelas, updated_at = :now
                    WHERE id_mentorkelas = :id_mentorkelas;
                """), {"id_paketkelas": new_paketkelas, "now": now, "id_mentorkelas": old_class["id_mentorkelas"]})

            elif old_class and not new_paketkelas:  
                # Case 3: awalnya ada kelas → hapus (nonaktifkan)
                connection.execute(text("""
                    UPDATE mentorkelas
                    SET status = 0, updated_at = :now
                    WHERE id_mentorkelas = :id_mentorkelas;
                """), {"id_mentorkelas": old_class["id_mentorkelas"], "now": now})

            # kalau sama2 null atau sama2 sama → tidak ada perubahan

            return dict(user_result)

    except SQLAlchemyError as e:
        print(f"Error update_mentor: {e}")
        return None

def delete_mentor(id_mentor):
    engine = get_connection()
    now = get_wita()
    try:
        with engine.begin() as connection:
            # Nonaktifkan mentor di tabel users
            result = connection.execute(text("""
                UPDATE users
                SET status = 0,
                    updated_at = :now
                WHERE id_user = :id_mentor 
                  AND role = 'mentor' 
                  AND status = 1
                RETURNING id_user, nama;
            """), {
                "id_mentor": id_mentor,
                "now": now
            }).mappings().fetchone()

            if not result:
                return None  # mentor tidak ditemukan atau sudah nonaktif

            # Nonaktifkan juga semua data di mentorkelas
            connection.execute(text("""
                UPDATE mentorkelas
                SET status = 0,
                    updated_at = :now
                WHERE id_user = :id_mentor
                  AND status = 1
            """), {
                "id_mentor": id_mentor,
                "now": now
            })

            return dict(result)
    except SQLAlchemyError as e:
        print(f"Error delete_mentor: {e}")
        return None

