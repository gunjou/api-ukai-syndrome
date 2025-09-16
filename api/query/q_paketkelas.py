from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..utils.config import get_connection, get_wita


def get_kelas_by_admin():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                        b.id_batch, b.nama_batch, p.id_paket, p.nama_paket,
                        COALESCE(tp.total_peserta, 0) AS total_peserta,
                        COALESCE(tm.total_mentor, 0) AS total_mentor,
                        COALESCE(tmd.total_modul, 0) AS total_modul
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                JOIN paket p ON pk.id_paket = p.id_paket AND p.status = 1
                LEFT JOIN (
                    SELECT pk.id_paketkelas, COUNT(pk.*) AS total_peserta
                    FROM pesertakelas pk
                    INNER JOIN paketkelas p ON p.id_paketkelas = pk.id_pesertakelas AND p.status = 1
                    INNER JOIN users u ON u.id_user = pk.id_user AND u.status = 1 AND u.role = 'peserta'
                    WHERE p.status = 1
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
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(mk.*) AS total_modul
                    FROM modulkelas mk
                    INNER JOIN modul m ON m.id_modul = mk.id_modul AND m.status = 1
                    INNER JOIN paketkelas p ON p.id_paketkelas = mk.id_paketkelas AND p.status = 1
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tmd ON pk.id_paketkelas = tmd.id_paketkelas
                WHERE pk.status = 1
                ORDER BY pk.nama_kelas ASC
            """
            result = conn.execute(text(query)).mappings().fetchall()
            # Pastikan count hasilnya integer, bukan Decimal
            return [
                {
                    **dict(row),
                    "total_peserta": int(row["total_peserta"]),
                    "total_mentor": int(row["total_mentor"]),
                    "total_modul": int(row["total_modul"]),
                }
                for row in result
            ]
    except SQLAlchemyError as e:
        print(f"[get_kelas_by_role] Database error: {e}")
        return []
    
def get_kelas_by_mentor(id_user):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT pk.id_paketkelas, 
                    pk.nama_kelas, 
                    pk.deskripsi, 
                    b.id_batch, 
                    b.nama_batch
                FROM mentorkelas mk
                JOIN paketkelas pk ON mk.id_paketkelas = pk.id_paketkelas
                JOIN batch b ON pk.id_batch = b.id_batch
                WHERE mk.id_user = :id_user 
                AND mk.status = 1 
                AND pk.status = 1
                ORDER BY pk.nama_kelas ASC
            """
            result = conn.execute(text(query), {"id_user": id_user}).mappings().fetchall()

            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        print(f"[get_kelas_by_role] Database error: {e}")
        return []

def get_kelas_by_id(id_kelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi,
                       b.id_batch, b.nama_batch, p.id_paket, p.nama_paket
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                JOIN paket p ON pk.id_paket = p.id_paket AND p.status = 1
                WHERE pk.id_paketkelas = :id_kelas AND pk.status = 1
            """), {"id_kelas": id_kelas}).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None

def is_batch_exist(id_batch):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_batch FROM batch
                WHERE id_batch = :id_batch AND status = 1
            """), {"id_batch": id_batch}).scalar()
            return result is not None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return False

def insert_kelas(payload):
    engine = get_connection()
    try:
        # Normalisasi nama_kelas → hilangkan spasi depan/belakang
        if "nama_kelas" in payload and isinstance(payload["nama_kelas"], str):
            payload["nama_kelas"] = payload["nama_kelas"].strip()

        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO paketkelas (id_batch, id_paket, nama_kelas, deskripsi, status, created_at, updated_at)
                VALUES (:id_batch, :id_paket, :nama_kelas, :deskripsi, 1, :now, :now)
                RETURNING nama_kelas
            """), {
                **payload,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result)
    except SQLAlchemyError as e:
        print(f"[insert_kelas] Error: {e}")
        return None

def update_kelas(id_kelas, payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE paketkelas
                SET id_batch   = :id_batch,
                    id_paket   = :id_paket,
                    nama_kelas = :nama_kelas,
                    deskripsi  = :deskripsi,
                    updated_at = :now
                WHERE id_paketkelas = :id_kelas AND status = 1
                RETURNING nama_kelas
            """), {
                **payload,
                "id_kelas": id_kelas,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"[update_kelas] Error: {e}")
        return None


def delete_kelas(id_kelas):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE paketkelas
                SET status = 0, updated_at = :now
                WHERE id_paketkelas = :id_kelas AND status = 1
                RETURNING nama_kelas
            """), {
                "id_kelas": id_kelas,
                "now": get_wita()
            }).mappings().fetchone()
            return dict(result) if result else None
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        return None