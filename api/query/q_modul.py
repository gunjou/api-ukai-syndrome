from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita

"""=== helper ==="""
def is_mentor_of_kelas(id_mentor, id_paketkelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 1 FROM mentorkelas
                WHERE id_user = :id_user AND id_paketkelas = :id_paketkelas AND status = 1
            """), {
                "id_user": id_mentor,
                "id_paketkelas": id_paketkelas
            }).fetchone()
            return bool(result)
    except SQLAlchemyError:
        return False
    
def is_valid_paketkelas(id_paketkelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_paketkelas FROM paketkelas
                WHERE id_paketkelas = :id AND status = 1
            """), {"id": id_paketkelas}).scalar()
            return result is not None
    except SQLAlchemyError:
        return False

"""=== CRUD ==="""
def get_all_modul_admin():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.owner, m.visibility, m.status,
                       pk.id_paketkelas, pk.nama_kelas
                FROM modul m
                LEFT JOIN modulkelas mkls 
                    ON mkls.id_modul = m.id_modul AND mkls.status = 1
                LEFT JOIN paketkelas pk 
                    ON mkls.id_paketkelas = pk.id_paketkelas AND pk.status = 1
                WHERE m.status = 1
                ORDER BY m.id_modul, pk.nama_kelas
            """)).mappings().fetchall()

            modul_dict = {}
            for row in result:
                id_modul = row["id_modul"]
                if id_modul not in modul_dict:
                    modul_dict[id_modul] = {
                        "id_modul": row["id_modul"],
                        "judul": row["judul"],
                        "deskripsi": row["deskripsi"],
                        "owner": row["owner"],
                        "visibility": row["visibility"],
                        "status": row["status"],
                        "paketkelas": []
                    }
                # hanya append kalau ada paketkelas valid
                if row["id_paketkelas"]:
                    modul_dict[id_modul]["paketkelas"].append({
                        "id_paketkelas": row["id_paketkelas"],
                        "nama_kelas": row["nama_kelas"]
                    })

            for modul in modul_dict.values():
                modul["total_kelas"] = len(modul["paketkelas"])
            return list(modul_dict.values())
    except SQLAlchemyError as e:
        print(f"DB Error: {e}")
        return []

def get_all_modul_by_mentor(id_mentor):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.owner, m.visibility, m.status,
                       pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                FROM modul m
                JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                JOIN mentorkelas mtk ON mtk.id_paketkelas = pk.id_paketkelas
                WHERE mtk.id_user = :id_mentor 
                  AND mtk.status = 1 
                  AND pk.status = 1 
                  AND m.status = 1
                ORDER BY m.id_modul
            """), {"id_mentor": id_mentor}).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError:
        return []
    
def get_all_modul_by_kelas_mentor(id_paketkelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.owner, m.visibility, m.status,
                       pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                FROM modul m
                JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas AND pk.status = 1
                WHERE pk.id_paketkelas = :id_paketkelas
                  AND m.status = 1
                ORDER BY m.id_modul
            """), {"id_paketkelas": id_paketkelas}).mappings().fetchall()
            return [dict(row) for row in result]
    except SQLAlchemyError:
        return []
    
def get_all_kelas_by_modul(id_modul):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                       b.id_batch, b.nama_batch, p.id_paket, p.nama_paket,
                       COALESCE(tmd.total_modul, 0) AS total_modul,
                       COALESCE(tp.total_peserta, 0) AS total_peserta,
                       COALESCE(tm.total_mentor, 0) AS total_mentor
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                JOIN paket p ON pk.id_paket = p.id_paket AND p.status = 1
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(mk.*) AS total_modul
                    FROM modulkelas mk
                    INNER JOIN modul m ON m.id_modul = mk.id_modul AND m.status = 1
                    INNER JOIN paketkelas p ON p.id_paketkelas = mk.id_paketkelas AND p.status = 1
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tmd ON pk.id_paketkelas = tmd.id_paketkelas
                LEFT JOIN (
                    SELECT pk.id_paketkelas, COUNT(pk.*) AS total_peserta
                    FROM pesertakelas pk
                    INNER JOIN paketkelas p ON p.id_paketkelas = pk.id_pesertakelas AND p.status = 1
                    INNER JOIN users u ON u.id_user = pk.id_user AND u.status = 1 AND u.role = 'peserta'
                    WHERE pk.status = 1
                    GROUP BY pk.id_paketkelas
                ) tp ON pk.id_paketkelas = tp.id_paketkelas
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(mk.*) AS total_mentor
                    FROM mentorkelas mk
                    INNER JOIN paketkelas p ON p.id_paketkelas = mk.id_paketkelas AND p.status = 1
                    INNER JOIN users u ON u.id_user = mk.id_user AND u.status = 1 AND u.role = 'mentor'
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tm ON pk.id_paketkelas = tm.id_paketkelas
                WHERE pk.status = 1
                  AND NOT EXISTS (
                      SELECT 1 
                      FROM modulkelas mk
                      WHERE mk.id_paketkelas = pk.id_paketkelas
                        AND mk.id_modul = :id_modul
                        AND mk.status = 1
                  )
                ORDER BY pk.nama_kelas ASC
            """
            result = conn.execute(text(query), {"id_modul": id_modul}).mappings().fetchall()

            return [
                {
                    **dict(row),
                    "total_peserta": int(row["total_peserta"]),
                    "total_mentor": int(row["total_mentor"]),
                }
                for row in result
            ]
    except SQLAlchemyError as e:
        print(f"[get_all_kelas_by_modul] Database error: {e}")
        return []
    
def get_kelas_by_modul(id_modul):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                        b.id_batch, b.nama_batch, p.id_paket, p.nama_paket, mkls.id_modulkelas,
                        COALESCE(tmd.total_modul, 0) AS total_modul,
                        COALESCE(tp.total_peserta, 0) AS total_peserta,
                        COALESCE(tm.total_mentor, 0) AS total_mentor
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                JOIN paket p ON pk.id_paket = p.id_paket AND p.status = 1
                JOIN modulkelas mkls ON mkls.id_paketkelas = pk.id_paketkelas AND mkls.status = 1
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(mk.*) AS total_modul
                    FROM modulkelas mk
                    INNER JOIN modul m ON m.id_modul = mk.id_modul AND m.status = 1
                    INNER JOIN paketkelas p ON p.id_paketkelas = mk.id_paketkelas AND p.status = 1
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tmd ON pk.id_paketkelas = tmd.id_paketkelas
                LEFT JOIN (
                    SELECT pk.id_paketkelas, COUNT(pk.*) AS total_peserta
                    FROM pesertakelas pk
                    INNER JOIN paketkelas p ON p.id_paketkelas = pk.id_pesertakelas AND p.status = 1
                    INNER JOIN users u ON u.id_user = pk.id_user AND u.status = 1 AND u.role = 'peserta'
                    WHERE pk.status = 1
                    GROUP BY pk.id_paketkelas
                ) tp ON pk.id_paketkelas = tp.id_paketkelas
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(mk.*) AS total_mentor
                    FROM mentorkelas mk
                    INNER JOIN paketkelas p ON p.id_paketkelas = mk.id_paketkelas AND p.status = 1
                    INNER JOIN users u ON u.id_user = mk.id_user AND u.status = 1 AND u.role = 'mentor'
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tm ON pk.id_paketkelas = tm.id_paketkelas
                WHERE pk.status = 1 and mkls.id_modul = :id_modul
                ORDER BY pk.nama_kelas ASC
            """
            result = conn.execute(text(query), {'id_modul': id_modul}).mappings().fetchall()
            # Pastikan count hasilnya integer, bukan Decimal
            return [
                {
                    **dict(row),
                    "total_peserta": int(row["total_peserta"]),
                    "total_mentor": int(row["total_mentor"]),
                }
                for row in result
            ]
    except SQLAlchemyError as e:
        print(f"[get_kelas_by_role] Database error: {e}")
        return []
    
def delete_kelas_in_modul(id_modulkelas):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE modulkelas
                SET status = 0, updated_at = :now
                WHERE id_modulkelas = :id AND status = 1
            """), {
                "id": id_modulkelas,
                "now": get_wita()
            })
            return result.rowcount > 0  # True kalau ada row ter-update
    except SQLAlchemyError:
        return False
    
def assign_kelas_to_modul(id_modul, id_paketkelas_list):
    """
    Assign satu atau banyak kelas ke modul tertentu.
    """
    engine = get_connection()
    try:
        with engine.begin() as conn:
            now = get_wita()
            inserted_count = 0

            for id_paketkelas in id_paketkelas_list:
                # Cek apakah sudah ada relasi aktif
                existing = conn.execute(text("""
                    SELECT 1 FROM modulkelas
                    WHERE id_modul = :id_modul 
                      AND id_paketkelas = :id_paketkelas
                      AND status = 1
                """), {
                    "id_modul": id_modul,
                    "id_paketkelas": id_paketkelas
                }).fetchone()

                if existing:
                    continue  # skip jika sudah ada

                # Insert baru
                conn.execute(text("""
                    INSERT INTO modulkelas (id_modul, id_paketkelas, status, created_at, updated_at)
                    VALUES (:id_modul, :id_paketkelas, 1, :now, :now)
                """), {
                    "id_modul": id_modul,
                    "id_paketkelas": id_paketkelas,
                    "now": now
                })
                inserted_count += 1

            return inserted_count
    except SQLAlchemyError as e:
        print(f"[assign_kelas_to_modul] Error: {e}")
        return 0

def get_old_modul_by_id(id_modul):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_modul, judul, deskripsi, owner, visibility
                FROM modul
                WHERE id_modul = :id AND status = 1
                LIMIT 1
            """), {"id": id_modul}).mappings().fetchone()

            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"[get_old_modul_by_id] Error: {e}")
        return None
    
def get_modul_by_id(id_modul):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT m.id_modul, m.judul, m.deskripsi, m.owner, m.visibility, m.status,
                       pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                FROM modul m
                JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                WHERE m.id_modul = :id AND m.status = 1 AND pk.status = 1
            """), {"id": id_modul}).mappings().fetchall()

            # Bisa ada banyak kelas untuk satu modul → return list
            return [dict(row) for row in result] if result else None
    except SQLAlchemyError:
        return None

def insert_modul(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO modul (judul, deskripsi, owner, status, created_at, updated_at, visibility)
                VALUES (:judul, :deskripsi, :owner, 1, :now, :now, :visibility)
                RETURNING id_modul, judul
            """), {
                **payload,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"[insert_modul] Error: {e}")
        return None
    
def insert_modul_for_mentor(payload, id_user):
    """
    Insert modul baru oleh mentor, lalu otomatis assign ke kelas yang dia ampu.
    """
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # 1️⃣ Buat modul baru
            modul = conn.execute(text("""
                INSERT INTO modul (judul, deskripsi, owner, status, created_at, updated_at, visibility)
                VALUES (:judul, :deskripsi, :owner, 1, :now, :now, :visibility)
                RETURNING id_modul, judul
            """), {
                "judul": payload["judul"],
                "owner": payload.get("owner"),
                "deskripsi": payload.get("deskripsi"),
                "visibility": payload.get("visibility", "hold"),
                "now": get_wita()
            }).mappings().fetchone()

            if not modul:
                return None

            id_modul = modul["id_modul"]

            # 2️⃣ Cari semua kelas yang diampu mentor
            kelas_list = conn.execute(text("""
                SELECT id_paketkelas 
                FROM mentorkelas
                WHERE id_user = :id_user AND status = 1
            """), {"id_user": id_user}).mappings().fetchall()

            if not kelas_list:
                raise Exception("Mentor tidak memiliki kelas aktif.")

            # 3️⃣ Assign modul ke semua kelas tersebut
            for kelas in kelas_list:
                conn.execute(text("""
                    INSERT INTO modulkelas (id_modul, id_paketkelas, status, created_at, updated_at)
                    VALUES (:id_modul, :id_paketkelas, 1, :now, :now)
                """), {
                    "id_modul": id_modul,
                    "id_paketkelas": kelas["id_paketkelas"],
                    "now": get_wita()
                })

            return dict(modul)

    except SQLAlchemyError as e:
        print(f"Error insert_modul_for_mentor: {e}")
        return None
    
def is_mentor_of_modul(id_user, id_modul):
    """
    Cek apakah user dengan role mentor punya akses ke modul tertentu.
    Akses valid jika user adalah mentor di salah satu kelas yang terhubung ke modul.
    """
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT 1
                FROM modulkelas mk
                JOIN mentorkelas mtk ON mk.id_paketkelas = mtk.id_paketkelas
                WHERE mk.id_modul = :id_modul
                  AND mtk.id_user = :id_user
                  AND mk.status = 1
                  AND mtk.status = 1
                LIMIT 1
            """)
            result = conn.execute(query, {"id_modul": id_modul, "id_user": id_user}).fetchone()
            return bool(result)
    except SQLAlchemyError as e:
        print(f"[is_mentor_of_modul] Error: {e}")
        return False


def update_modul(id_modul, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE modul
                SET judul = :judul,
                    deskripsi = :deskripsi,
                    visibility = :visibility,
                    updated_at = :now
                WHERE id_modul = :id AND status = 1
                RETURNING id_modul, judul
            """), {
                **payload,
                "id": id_modul,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"[update_modul] Error: {e}")
        return None

def delete_modul(id_modul):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE modul
                SET status = 0, updated_at = :now
                WHERE id_modul = :id AND status = 1
                RETURNING id_modul, judul
            """), {
                "id": id_modul,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError:
        return None


"""#=== Query tambahan (selain CRUD) ===#"""
def get_all_modul_by_user(id_user, role):
    """
    Ambil modul berdasarkan role user:
    - mentor → modul yang diampu
    - peserta → modul dari kelas yang diikuti
    """
    engine = get_connection()
    try:
        with engine.connect() as conn:
            if role == "mentor":
                result = conn.execute(text("""
                    SELECT m.id_modul, m.judul, m.deskripsi, m.owner, m.visibility, m.status,
                           pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                    FROM modul m
                    JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                    JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                    JOIN mentorkelas mtk ON mtk.id_paketkelas = pk.id_paketkelas
                    WHERE mtk.id_user = :id_user
                      AND mtk.status = 1
                      AND pk.status = 1
                      AND m.status = 1
                    ORDER BY m.id_modul
                """), {"id_user": id_user}).mappings().fetchall()

            elif role == "peserta":
                result = conn.execute(text("""
                    SELECT m.id_modul, m.judul, m.deskripsi, m.owner, m.visibility, m.status,
                           pk.id_paketkelas, pk.nama_kelas, pk.deskripsi AS deskripsi_kelas
                    FROM modul m
                    JOIN modulkelas mkls ON mkls.id_modul = m.id_modul AND mkls.status = 1
                    JOIN paketkelas pk ON mkls.id_paketkelas = pk.id_paketkelas
                    JOIN pesertakelas ps ON ps.id_paketkelas = pk.id_paketkelas
                    WHERE ps.id_user = :id_user
                      AND ps.status = 1
                      AND pk.status = 1
                      AND m.status = 1
                      AND m.visibility = 'open'
                    ORDER BY m.id_modul
                """), {"id_user": id_user}).mappings().fetchall()

            else:
                return []

            return [dict(row) for row in result]

    except SQLAlchemyError as e:
        print(f"[get_all_modul_by_user] Error: {e}")
        return []

def update_modul_visibility(id_modul, visibility):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE modul
                SET visibility = :visibility,
                    updated_at = :now
                WHERE id_modul = :id_modul AND status = 1
                RETURNING id_modul, judul
            """), {
                "visibility": visibility,
                "id_modul": id_modul,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

