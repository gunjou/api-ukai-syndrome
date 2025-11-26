import requests
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import convert_to_html_question, remove_images_from_html, sanitize_html, serialize_row, serialize_row_datetime
from ..utils.config import CDN_API_KEY, CDN_UPLOAD_URL, get_connection, get_wita


"""#=== query helper ===#"""
def get_jumlah_soal_by_tryout(id_tryout):
    """Ambil jumlah soal maksimal dari tabel tryout"""
    engine = get_connection()
    with engine.connect() as conn:
        q = text("SELECT jumlah_soal FROM tryout WHERE id_tryout = :id_tryout AND status = 1")
        res = conn.execute(q, {"id_tryout": id_tryout}).mappings().fetchone()
        return res['jumlah_soal'] if res else 0

def get_jumlah_soal_tersimpan(id_tryout):
    """Hitung jumlah soal yang sudah disimpan untuk tryout tertentu"""
    engine = get_connection()
    with engine.connect() as conn:
        q = text("SELECT COUNT(*) FROM soaltryout WHERE id_tryout = :id_tryout AND status = 1")
        return conn.execute(q, {"id_tryout": id_tryout}).scalar()
    

"""#=== main query ===#"""
def insert_soal_tryout(payload):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # Cek jumlah soal yang sudah ada
            q_check = text("SELECT COUNT(*) FROM soaltryout WHERE id_tryout = :id_tryout AND status = 1")
            existing_count = conn.execute(q_check, {"id_tryout": payload["id_tryout"]}).scalar()

            # Ambil batas maksimal jumlah soal dari tryout
            q_limit = text("SELECT jumlah_soal FROM tryout WHERE id_tryout = :id_tryout AND status = 1")
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
                AND status = 1
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
    
def insert_bulk_soaltryout(id_tryout, soal_list, existing_count):
    engine = get_connection()
    now = get_wita()

    try:
        with engine.begin() as conn:
            values = []
            for index, soal in enumerate(soal_list):
                nomor_urut = existing_count + index + 1

                values.append({
                    "id_tryout": id_tryout,
                    "nomor_urut": nomor_urut,
                    "pertanyaan": soal["pertanyaan"],  # sudah HTML
                    "pilihan_a": soal["pilihan_a"],
                    "pilihan_b": soal["pilihan_b"],
                    "pilihan_c": soal["pilihan_c"],
                    "pilihan_d": soal["pilihan_d"],
                    "pilihan_e": soal["pilihan_e"],
                    "jawaban_benar": soal["jawaban_benar"],
                    "pembahasan": soal["pembahasan"],
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


def get_soal_by_tryout(id_tryout):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            # Pastikan tryout-nya ada
            cek_tryout = conn.execute(
                text("SELECT id_tryout FROM tryout WHERE id_tryout = :id_tryout AND status = 1"),
                {"id_tryout": id_tryout}
            ).fetchone()
            if not cek_tryout:
                return None  # Tryout tidak ditemukan
            # Ambil semua soal dari tryout tersebut
            q = text("""
                SELECT 
                    id_soaltryout, id_tryout, nomor_urut, pertanyaan, pilihan_a, pilihan_b, pilihan_c, pilihan_d,
                    pilihan_e, jawaban_benar, pembahasan, status, created_at, updated_at
                FROM soaltryout
                WHERE id_tryout = :id_tryout AND status = 1
                ORDER BY nomor_urut ASC
            """)
            result = conn.execute(q, {"id_tryout": id_tryout}).mappings().all()
            # Jika tidak ada soal, kembalikan list kosong
            if not result:
                return []
            return [serialize_row_datetime(row) for row in result]
    except SQLAlchemyError as e:
        print(f"[ERROR get_soal_by_tryout] {e}")
        return None


def get_detail_soaltryout(id_soaltryout):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            q = text("""
                SELECT 
                    id_soaltryout, id_tryout, nomor_urut, pertanyaan, pilihan_a, pilihan_b, pilihan_c, pilihan_d,
                    pilihan_e, jawaban_benar, pembahasan, status, created_at, updated_at
                FROM soaltryout
                WHERE id_soaltryout = :id_soaltryout AND status = 1
                LIMIT 1
            """)
            result = conn.execute(q, {"id_soaltryout": id_soaltryout}).mappings().first()
            if not result:
                return None
            return serialize_row_datetime(result)
    except SQLAlchemyError as e:
        print(f"[ERROR get_detail_soaltryout] {e}")
        return None

def update_soaltryout(id_soaltryout, data):
    engine = get_connection()
    now = get_wita()

    # Ambil semua field yang dikirim kecuali None
    fields = {k: v for k, v in data.items() if v is not None}

    if not fields:
        return {"success": False, "message": "Tidak ada data yang dikirim untuk diperbarui"}

    # =============== VALIDASI JAWABAN BENAR ===============
    if "jawaban_benar" in fields:
        valid = ["A", "B", "C", "D", "E"]
        if fields["jawaban_benar"].upper() not in valid:
            return {"success": False, "message": "Jawaban benar harus A, B, C, D, atau E"}
        fields["jawaban_benar"] = fields["jawaban_benar"].upper()

    # =============== HANDLE GAMBAR BARU ===============
    new_image_url = None
    if "gambar" in fields and fields["gambar"]:
        image_file = fields["gambar"]

        cdn_response = requests.post(
            f"{CDN_UPLOAD_URL}/tryout",
            headers={"X-API-KEY": CDN_API_KEY},
            files={"file": (image_file.filename, image_file.stream)}
        )

        if not cdn_response.ok:
            return {"success": False, "message": "Gagal upload gambar ke CDN"}

        new_image_url = cdn_response.json().get("url")

        del fields["gambar"]  # hindari masuk DB

    # Ambil flag hapus gambar
    hapus_gambar = fields.get("hapus_gambar", False)
    fields.pop("hapus_gambar", None)

    try:
        with engine.begin() as conn:

            # Cek soal
            row = conn.execute(
                text("SELECT pertanyaan FROM soaltryout WHERE id_soaltryout=:id AND status=1"),
                {"id": id_soaltryout}
            ).mappings().fetchone()

            if not row:
                return {"success": False, "message": "Soal tidak ditemukan"}

            # ============= PROSES PERTANYAAN (jika perlu) =============
            # Jika perlu update gambar, tetapi pertanyaan tidak dikirim → pakai pertanyaan lama
            if (new_image_url or hapus_gambar) and "pertanyaan" not in fields:
                fields["pertanyaan"] = row["pertanyaan"]

            # Jika pertanyaan ada (baik dikirim atau pakai default lama)
            if "pertanyaan" in fields:
                html = fields["pertanyaan"]

                # hapus semua gambar lama
                if hapus_gambar:
                    html = remove_images_from_html(html)

                # replace dengan gambar baru
                if new_image_url:
                    html = remove_images_from_html(html)
                    html += f'<img src="{new_image_url}" alt="gambar-soal">'

                html = convert_to_html_question(html)
                html = sanitize_html(html)
                fields["pertanyaan"] = html

            # ============= PROSES PEMBAHASAN (normal) =============
            if "pembahasan" in fields:
                html = convert_to_html_question(fields["pembahasan"])
                html = sanitize_html(html)
                fields["pembahasan"] = html

            # Jika TIDAK ADA field apapun setelah proses → error
            if not fields:
                return {"success": False, "message": "Tidak ada perubahan yang dilakukan"}

            # ============= UPDATE DB =============
            set_clause = ", ".join([f"{k} = :{k}" for k in fields.keys()])
            fields["updated_at"] = now
            fields["id"] = id_soaltryout

            q = text(f"""
                UPDATE soaltryout
                SET {set_clause}, updated_at = :updated_at
                WHERE id_soaltryout = :id
            """)
            conn.execute(q, fields)

            return {"success": True, "message": "Soal berhasil diperbarui"}

    except SQLAlchemyError as e:
        print(f"[ERROR update_soaltryout] {e}")
        return {"success": False, "message": "Gagal memperbarui soal"}

def soft_delete_soaltryout(id_soaltryout: int):
    engine = get_connection()
    try:
        with engine.begin() as conn:
            # Update status menjadi 0 (soft delete)
            result = conn.execute(text("""
                UPDATE soaltryout
                SET status = 0, updated_at = NOW()
                WHERE id_soaltryout = :id_soaltryout AND status = 1
            """), {"id_soaltryout": id_soaltryout})

            # Jika ada baris yang terupdate, berarti berhasil
            if result.rowcount > 0:
                return True
            else:
                return False
    except SQLAlchemyError as e:
        print(f"[ERROR soft_delete_soaltryout] {e}")
        return False


def get_soal_by_id(id_soaltryout: int):
    engine = get_connection()
    try:
        with engine.connect() as conn:
            q = text("""
                SELECT * FROM soaltryout
                WHERE id_soaltryout = :id_soaltryout AND status = 1
            """)
            result = conn.execute(q, {"id_soaltryout": id_soaltryout}).mappings().first()
            return result  # Kembalikan data soal jika ditemukan, atau None jika tidak
    except SQLAlchemyError as e:
        print(f"[ERROR get_soal_by_id] {e}")
        return None