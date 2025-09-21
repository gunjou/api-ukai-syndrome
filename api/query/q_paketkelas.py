from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita


def get_kelas_by_admin():
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi, pk.id_user, u.nama as wali_kelas,
                       b.id_batch, b.nama_batch, p.id_paket, p.nama_paket,
                       COALESCE(tp.total_peserta, 0) AS total_peserta,
                       COALESCE(tm.total_mentor, 0) AS total_mentor,
                       COALESCE(tmd.total_modul, 0) AS total_modul
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                JOIN paket p ON pk.id_paket = p.id_paket AND p.status = 1
                LEFT JOIN users u ON pk.id_user = u.id_user AND u.status = 1 AND u.role = 'mentor'

                -- Hitung peserta aktif
                LEFT JOIN (
                    SELECT pk.id_paketkelas, COUNT(*) AS total_peserta
                    FROM pesertakelas ps
                    JOIN paketkelas pk ON pk.id_paketkelas = ps.id_paketkelas AND pk.status = 1
                    JOIN users u ON u.id_user = ps.id_user 
                                AND u.status = 1 
                                AND u.role = 'peserta'
                    WHERE ps.status = 1
                    GROUP BY pk.id_paketkelas
                ) tp ON pk.id_paketkelas = tp.id_paketkelas

                -- Hitung mentor aktif
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(*) AS total_mentor
                    FROM mentorkelas mk
                    JOIN paketkelas pk ON pk.id_paketkelas = mk.id_paketkelas AND pk.status = 1
                    JOIN users u ON u.id_user = mk.id_user 
                                AND u.status = 1 
                                AND u.role = 'mentor'
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tm ON pk.id_paketkelas = tm.id_paketkelas

                -- Hitung modul aktif
                LEFT JOIN (
                    SELECT mk.id_paketkelas, COUNT(*) AS total_modul
                    FROM modulkelas mk
                    JOIN modul m ON m.id_modul = mk.id_modul AND m.status = 1
                    JOIN paketkelas pk ON pk.id_paketkelas = mk.id_paketkelas AND pk.status = 1
                    WHERE mk.status = 1
                    GROUP BY mk.id_paketkelas
                ) tmd ON pk.id_paketkelas = tmd.id_paketkelas

                WHERE pk.status = 1
                ORDER BY pk.nama_kelas ASC
            """
            result = conn.execute(text(query)).mappings().fetchall()
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
        print(f"[get_kelas_by_admin] Database error: {e}")
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
    
def get_kelas_by_walikelas(id_user):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            query = """
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi, pk.id_user, u.nama,
                       b.id_batch, b.nama_batch, p.id_paket, p.nama_paket
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                JOIN paket p ON pk.id_paket = p.id_paket AND p.status = 1
                LEFT JOIN users u ON pk.id_user = u.id_user AND u.status = 1 AND u.role = 'mentor'
                WHERE pk.id_user = 111 AND pk.status = 1
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
                SELECT pk.id_paketkelas, pk.nama_kelas, pk.deskripsi, pk.id_user, u.nama,
                       b.id_batch, b.nama_batch, p.id_paket, p.nama_paket
                FROM paketkelas pk
                JOIN batch b ON pk.id_batch = b.id_batch AND b.status = 1
                JOIN paket p ON pk.id_paket = p.id_paket AND p.status = 1
                LEFT JOIN users u ON pk.id_user = u.id_user AND u.status = 1 AND u.role = 'mentor'
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
                INSERT INTO paketkelas (id_batch, id_paket, id_user, nama_kelas, deskripsi, status, created_at, updated_at)
                VALUES (:id_batch, :id_paket, :id_user, :nama_kelas, :deskripsi, 1, :now, :now)
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
                    id_user   = :id_user,
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
    
def get_peserta_kelas(id_kelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    pk.id_pesertakelas, u.id_user, u.nama, u.email, u.no_hp, u.created_at as tanggal_join
                FROM pesertakelas pk
                JOIN users u  ON pk.id_user = u.id_user AND u.role = 'peserta' AND u.status = 1
                WHERE pk.status = 1 AND pk.id_paketkelas = :id_kelas
                ORDER BY u.nama ASC
            """), {"id_kelas": id_kelas}).mappings().fetchall()

            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error get_peserta_batch: {e}")
        return []
    
def get_mentor_kelas(id_kelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    mk.id_mentorkelas, u.nama, u.email, u.no_hp
                FROM mentorkelas mk
                JOIN users u  ON mk.id_user = u.id_user AND u.status = 1
                WHERE mk.status = 1 AND mk.id_paketkelas = :id_kelas
                ORDER BY u.nama ASC
            """), {"id_kelas": id_kelas}).mappings().fetchall()

            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error get_peserta_batch: {e}")
        return []
    
def get_modul_kelas(id_kelas):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    mk.id_modulkelas, m.judul, m.owner, m.deskripsi, m.visibility
                FROM modulkelas mk
                JOIN modul m  ON mk.id_modul = m.id_modul AND m.status = 1
                WHERE mk.status = 1 AND mk.id_paketkelas = :id_kelas
                ORDER BY m.judul ASC
            """), {"id_kelas": id_kelas}).mappings().fetchall()

            return [serialize_row(row) for row in result]
    except SQLAlchemyError as e:
        print(f"Error get_peserta_batch: {e}")
        return []
    
def soft_delete(table_name, id_column, id_value):
    """
    Fungsi umum untuk soft delete (status = 0) pada tabel tertentu.
    table_name: nama tabel (pesertakelas / mentorkelas / modulkelas)
    id_column: nama kolom primary key (id_pesertakelas / id_mentorkelas / id_modulkelas)
    id_value: nilai primary key yang mau dihapus
    """
    engine = get_connection()
    try:
        with engine.begin() as conn:
            sql = text(f"""
                UPDATE {table_name}
                SET status = 0, updated_at = :now
                WHERE {id_column} = :id AND status = 1
            """)
            result = conn.execute(sql, {
                "id": id_value,
                "now": get_wita()
            })
            return result.rowcount > 0
    except SQLAlchemyError as e:
        print(f"Error in soft_delete: {e}")
        return False
