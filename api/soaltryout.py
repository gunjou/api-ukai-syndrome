import requests
import pandas as pd
from flask_restx import Namespace, Resource, reqparse
from flask_restx.reqparse import FileStorage
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from .utils.helper import convert_to_html_question
from .utils.config import CDN_API_KEY, CDN_UPLOAD_URL
from .utils.decorator import role_required, session_required
from .query.q_soaltryout import *


soaltryout_ns = Namespace('soaltryout', description='Manajemen Soal Tryout')

soal_tryout_parser = reqparse.RequestParser()
soal_tryout_parser.add_argument('id_tryout', type=int, required=True)
soal_tryout_parser.add_argument('nomor_urut', type=int, required=True)
soal_tryout_parser.add_argument('pertanyaan', type=str, required=True)
soal_tryout_parser.add_argument('pilihan_a', type=str, required=True)
soal_tryout_parser.add_argument('pilihan_b', type=str, required=True)
soal_tryout_parser.add_argument('pilihan_c', type=str, required=True)
soal_tryout_parser.add_argument('pilihan_d', type=str, required=True)
soal_tryout_parser.add_argument('pilihan_e', type=str, required=True)
soal_tryout_parser.add_argument('jawaban_benar', type=str, required=True, choices=('A', 'B', 'C', 'D', 'E'))
soal_tryout_parser.add_argument('pembahasan', type=str, required=False, default='')
soal_tryout_parser.add_argument('gambar', type=FileStorage, location='files', required=False)

upload_soal_parser = reqparse.RequestParser()
upload_soal_parser.add_argument("id_tryout", type=int, required=True, help="ID tryout harus diisi")
upload_soal_parser.add_argument("file", type=FileStorage, location="files", required=True, help="File soal harus diunggah")

edit_soal_parser = reqparse.RequestParser()
edit_soal_parser.add_argument('pertanyaan', type=str, required=False)
edit_soal_parser.add_argument('pilihan_a', type=str, required=False)
edit_soal_parser.add_argument('pilihan_b', type=str, required=False)
edit_soal_parser.add_argument('pilihan_c', type=str, required=False)
edit_soal_parser.add_argument('pilihan_d', type=str, required=False)
edit_soal_parser.add_argument('pilihan_e', type=str, required=False)
edit_soal_parser.add_argument('jawaban_benar', type=str, required=False, choices=('A', 'B', 'C', 'D', 'E'))
edit_soal_parser.add_argument('pembahasan', type=str, required=False)
edit_soal_parser.add_argument('gambar', type=FileStorage, location='files', required=False)
edit_soal_parser.add_argument('hapus_gambar', type=bool, required=False, default=False)


# ===== HELPER FUNCTION =====
def map_soal_tuple_to_dict(soal_tuple):
    keys = ['pertanyaan', 'pilihan_a', 'pilihan_b', 'pilihan_c', 'pilihan_d', 'pilihan_e', 'jawaban_benar', 'pembahasan']
    return dict(zip(keys, soal_tuple))


# ===== MAIN ENDPOINT =====
@soaltryout_ns.route('')
class SoalTryoutCreateResource(Resource):
    @soaltryout_ns.expect(soal_tryout_parser)
    @jwt_required()
    @role_required('admin')
    def post(self):
        """Akses: (Admin) | Menambahkan soal tryout secara manual"""
        data = soal_tryout_parser.parse_args()

        # --- NEW: Proses gambar opsional ---
        image_file = data.get("gambar")
        image_url = None

        try:
            # Jika admin upload gambar, upload dulu ke CDN
            if image_file:
                cdn_response = requests.post(
                    f"{CDN_UPLOAD_URL}/tryout",   # service upload tryout
                    headers={"X-API-KEY": CDN_API_KEY},
                    files={"file": (image_file.filename, image_file.stream)}
                )

                if cdn_response.ok:
                    image_url = cdn_response.json().get("url")
                else:
                    return {
                        "message": "Gagal mengupload gambar ke CDN",
                        "detail": cdn_response.text
                    }, 400

            # --- Convert pertanyaan ke HTML ---
            # jika tidak ada gambar, tetap wrap <p>text</p>
            pertanyaan_html = convert_to_html_question(data["pertanyaan"], image_url)
            data["pertanyaan"] = pertanyaan_html

            # --- Insert ke database (fungsi existing) ---
            result = insert_soal_tryout(data)

            if result["success"]:
                return {"message": result["message"]}, 201
            return {"message": result["message"]}, 400

        except Exception as e:
            print(f"[ERROR POST /soaltryout] {e}")
            return {"message": "Terjadi kesalahan saat menambahkan soal"}, 500
        

@soaltryout_ns.route('/upload-soal')
class UploadSoalTryoutResource(Resource):
    @soaltryout_ns.expect(upload_soal_parser)
    @jwt_required()
    @role_required('admin')
    def post(self):
        """Akses: (Admin) | Upload soal tryout via file CSV/XLSX"""
        args = upload_soal_parser.parse_args()
        file = args['file']
        id_tryout = args['id_tryout']

        try:
            # Load file CSV/XLSX
            filename = file.filename.lower()

            if filename.endswith(".csv"):
                df = pd.read_csv(file)
            elif filename.endswith(".xlsx"):
                df = pd.read_excel(file)
            else:
                return {"message": "Format file harus .csv atau .xlsx"}, 400

            # Normalisasi nama kolom
            df.columns = [c.strip().lower() for c in df.columns]

            expected_columns = [
                'no', 'pertanyaan', 'pilihan_a', 'pilihan_b', 'pilihan_c',
                'pilihan_d', 'pilihan_e', 'jawaban_benar', 'pembahasan'
            ]

            missing = [col for col in expected_columns if col not in df.columns]
            if missing:
                return {"message": f"Kolom berikut tidak ditemukan: {missing}"}, 400

            soal_list = df.to_dict(orient='records')

            # Ambil jumlah existing soal
            count_existing = get_jumlah_soal_tersimpan(id_tryout)
            max_soal = get_jumlah_soal_by_tryout(id_tryout)

            if max_soal is None:
                return {"message": "Tryout tidak ditemukan"}, 404

            if count_existing + len(soal_list) > max_soal:
                return {
                    "message": f"Melebihi kuota. Sisa slot: {max_soal - count_existing}"
                }, 400

            # Validasi & normalisasi
            cleaned_list = []
            for s in soal_list:
                jb = str(s['jawaban_benar']).strip().upper()
                if jb not in ['A', 'B', 'C', 'D', 'E']:
                    return {"message": f"Jawaban salah pada soal no {s['no']}"}, 400

                cleaned_list.append({
                    "pertanyaan": convert_to_html_question(str(s["pertanyaan"]).strip()),
                    "pilihan_a": str(s["pilihan_a"]).strip(),
                    "pilihan_b": str(s["pilihan_b"]).strip(),
                    "pilihan_c": str(s["pilihan_c"]).strip(),
                    "pilihan_d": str(s["pilihan_d"]).strip(),
                    "pilihan_e": str(s["pilihan_e"]).strip(),
                    "jawaban_benar": jb,
                    "pembahasan": str(s["pembahasan"]).strip()
                })

            # Insert bulk (fix nomor urut)
            inserted = insert_bulk_soaltryout(id_tryout, cleaned_list, count_existing)

            if inserted:
                return {
                    "message": f"{len(cleaned_list)} soal berhasil ditambahkan"
                }, 201

            return {"message": "Gagal menambahkan soal"}, 400

        except Exception as e:
            print(f"[ERROR UPLOAD SOAL] {e}")
            return {"message": "Terjadi kesalahan saat mengunggah soal"}, 500


@soaltryout_ns.route('/<int:id_tryout>')
class SoalTryoutListResource(Resource):
    @jwt_required()
    @role_required('admin')
    def get(self, id_tryout):
        """Akses: (Admin) | Ambil semua soal berdasarkan ID Tryout"""
        try:
            result = get_soal_by_tryout(id_tryout)
            # Jika tryout tidak ditemukan
            if result is None:
                return {
                    "status": "not_found",
                    "message": f"Tryout dengan ID {id_tryout} tidak ditemukan",
                    "data": None
                }, 404
            # Jika tryout valid tapi belum ada soal
            if isinstance(result, list) and len(result) == 0:
                return {
                    "status": "empty",
                    "message": f"Tryout dengan ID {id_tryout} belum memiliki soal",
                    "data": []
                }, 200
            # Jika ada data soal
            return {
                "status": "success",
                "message": "Data soal berhasil diambil",
                "data": result
            }, 200
        except Exception as e:
            print(f"[ERROR GET /soal-tryout/{id_tryout}] {e}")
            return {
                "status": "error",
                "message": "Terjadi kesalahan saat mengambil data soal"
            }, 500


@soaltryout_ns.route('/soal/<int:id_soaltryout>')
class SoalTryoutDetailResource(Resource):
    @jwt_required()
    @role_required('admin')
    def get(self, id_soaltryout):
        """Akses: (Admin) | Ambil detail satu soal tryout berdasarkan ID Soal"""
        try:
            result = get_detail_soaltryout(id_soaltryout)
            if result is None:
                return {
                    "status": "not_found",
                    "message": f"Soal dengan ID {id_soaltryout} tidak ditemukan",
                    "data": None
                }, 404
            return {
                "status": "success",
                "message": "Data soal berhasil diambil",
                "data": result
            }, 200
        except Exception as e:
            print(f"[ERROR GET /soal-tryout/soal/{id_soaltryout}] {e}")
            return {
                "status": "error",
                "message": "Terjadi kesalahan saat mengambil data soal"
            }, 500


@soaltryout_ns.route('/<int:id_soaltryout>/edit')
class SoalTryoutEditResource(Resource):
    @soaltryout_ns.expect(edit_soal_parser)
    @jwt_required()
    @role_required('admin')
    def put(self, id_soaltryout):
        try:
            args = edit_soal_parser.parse_args()
            result = update_soaltryout(id_soaltryout, args)

            status = 200 if result["success"] else 400
            return {
                "status": "success" if result["success"] else "failed",
                "message": result["message"]
            }, status

        except Exception as e:
            print(f"[ERROR PUT /soal-tryout/{id_soaltryout}/edit] {e}")
            return {
                "status": "error",
                "message": "Terjadi kesalahan saat memperbarui soal"
            }, 500
            

@soaltryout_ns.route('/soal-delete/<int:id_soaltryout>')
class SoalTryoutDeleteResource(Resource):
    @jwt_required()
    @role_required('admin')
    def delete(self, id_soaltryout):
        """Akses: (Admin) | Soft delete soal tryout (ubah status menjadi 0)"""
        try:
            # Cek apakah soal tryout dengan ID tersebut ada
            soal = get_soal_by_id(id_soaltryout)
            if not soal:
                return {
                    "status": "not_found",
                    "message": f"Soal dengan ID {id_soaltryout} tidak ditemukan",
                    "data": None
                }, 404

            # Lakukan soft delete dengan mengubah status menjadi 0
            if soft_delete_soaltryout(id_soaltryout):
                return {
                    "status": "success",
                    "message": "Soal tryout berhasil dihapus (soft delete)"
                }, 200
            else:
                return {
                    "status": "error",
                    "message": "Terjadi kesalahan saat menghapus soal tryout"
                }, 500
        except Exception as e:
            print(f"[ERROR DELETE /soal-tryout/soal-delete/{id_soaltryout}] {e}")
            return {
                "status": "error",
                "message": "Terjadi kesalahan saat menghapus soal tryout"
            }, 500
            