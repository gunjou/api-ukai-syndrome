from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita


"""#=== query helper ===#"""
def get_jumlah_soal_by_tryout(id_tryout):
    """Ambil jumlah soal maksimal dari tabel tryout"""
    engine = get_connection()
    with engine.connect() as conn:
        q = text("SELECT jumlah_soal FROM tryout WHERE id_tryout = :id_tryout")
        res = conn.execute(q, {"id_tryout": id_tryout}).mappings().fetchone()
        return res['jumlah_soal'] if res else 0

def get_jumlah_soal_tersimpan(id_tryout):
    """Hitung jumlah soal yang sudah disimpan untuk tryout tertentu"""
    engine = get_connection()
    with engine.connect() as conn:
        q = text("SELECT COUNT(*) FROM soaltryout WHERE id_tryout = :id_tryout")
        return conn.execute(q, {"id_tryout": id_tryout}).scalar()
    

"""#=== main query ===#"""
def insert_soal_tryout(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # Cek jumlah soal yang sudah ada
            q_check = text("SELECT COUNT(*) FROM soaltryout WHERE id_tryout = :id_tryout")
            existing_count = conn.execute(q_check, {"id_tryout": payload["id_tryout"]}).scalar()

            # Ambil batas maksimal jumlah soal dari tryout
            q_limit = text("SELECT jumlah_soal FROM tryout WHERE id_tryout = :id_tryout")
            max_soal = conn.execute(q_limit, {"id_tryout": payload["id_tryout"]}).scalar()

            if max_soal is None:
                return {"success": False, "message": "Tryout tidak ditemukan"}

            if existing_count >= max_soal:
                return {"success": False, "message": "Jumlah soal sudah mencapai batas"}

            # Cari nomor urut terakhir
            q_last = text("""
                SELECT COALESCE(MAX(nomor_urut), 0)
                FROM soaltryout
                WHERE id_tryout = :id_tryout
            """)
            last_num = conn.execute(q_last, {"id_tryout": payload["id_tryout"]}).scalar()
            next_num = last_num + 1

            # Insert soal baru
            q_insert = text("""
                INSERT INTO soaltryout (
                    id_tryout, nomor_urut, pertanyaan, 
                    pilihan_a, pilihan_b, pilihan_c, pilihan_d, pilihan_e,
                    jawaban_benar, pembahasan, status, created_at, updated_at
                ) VALUES (
                    :id_tryout, :nomor_urut, :pertanyaan,
                    :pilihan_a, :pilihan_b, :pilihan_c, :pilihan_d, :pilihan_e,
                    :jawaban_benar, :pembahasan, 1, :now, :now
                )
            """)
            conn.execute(q_insert, {
                "id_tryout": payload["id_tryout"],
                "nomor_urut": next_num,
                "pertanyaan": payload["pertanyaan"],
                "pilihan_a": payload["pilihan_a"],
                "pilihan_b": payload["pilihan_b"],
                "pilihan_c": payload["pilihan_c"],
                "pilihan_d": payload["pilihan_d"],
                "pilihan_e": payload["pilihan_e"],
                "jawaban_benar": payload["jawaban_benar"],
                "pembahasan": payload["pembahasan"],
                "now": get_wita()
            })

            return {"success": True, "message": f"Soal berhasil ditambahkan dengan nomor urut {next_num}"}

    except SQLAlchemyError as e:
        print(f"[ERROR insert_soal_tryout] {e}")
        return {"success": False, "message": "Terjadi kesalahan pada database"}
    
def insert_bulk_soaltryout(id_tryout, soal_list):
    engine = get_connection()
    now = get_wita()

    try:
        with engine.begin() as conn:
            values = []
            for index, soal in enumerate(soal_list):
                # Normalisasi jawaban
                jawaban_benar = soal.get("jawaban_benar", "").strip().upper()

                values.append({
                    "id_tryout": id_tryout,
                    "nomor_urut": index + 1,
                    "pertanyaan": soal.get("pertanyaan", "").strip(),
                    "pilihan_a": soal.get("pilihan_a", "").strip(),
                    "pilihan_b": soal.get("pilihan_b", "").strip(),
                    "pilihan_c": soal.get("pilihan_c", "").strip(),
                    "pilihan_d": soal.get("pilihan_d", "").strip(),
                    "pilihan_e": soal.get("pilihan_e", "").strip(),
                    "jawaban_benar": jawaban_benar,
                    "pembahasan": soal.get("pembahasan", "").strip(),
                    "now": now
                })

            q = text("""
                INSERT INTO soaltryout (
                    id_tryout, nomor_urut, pertanyaan, pilihan_a, pilihan_b, pilihan_c,
                    pilihan_d, pilihan_e, jawaban_benar, pembahasan,
                    status, created_at, updated_at
                ) VALUES (
                    :id_tryout, :nomor_urut, :pertanyaan, :pilihan_a, :pilihan_b, :pilihan_c,
                    :pilihan_d, :pilihan_e, :jawaban_benar, :pembahasan,
                    1, :now, :now
                )
            """)
            conn.execute(q, values)
            return True
    except SQLAlchemyError as e:
        print(f"[ERROR insert_bulk_soaltryout] {e}")
        return False

