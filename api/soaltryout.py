import pandas as pd
from flask_restx import Namespace, Resource, reqparse
from flask_restx.reqparse import FileStorage
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

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

upload_soal_parser = reqparse.RequestParser()
upload_soal_parser.add_argument("id_tryout", type=int, required=True, help="ID tryout harus diisi")
upload_soal_parser.add_argument("file", type=FileStorage, location="files", required=True, help="File soal harus diunggah")


def map_soal_tuple_to_dict(soal_tuple):
    keys = ['pertanyaan', 'pilihan_a', 'pilihan_b', 'pilihan_c', 'pilihan_d', 'pilihan_e', 'jawaban_benar', 'pembahasan']
    return dict(zip(keys, soal_tuple))

@soaltryout_ns.route('')
class SoalTryoutCreateResource(Resource):
    @soaltryout_ns.expect(soal_tryout_parser)
    # @session_required
    @jwt_required()
    @role_required('admin')
    def post(self):
        """Akses: (Admin) | Menambahkan soal tryout secara manual"""
        data = soal_tryout_parser.parse_args()

        try:
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
    # @session_required
    @jwt_required()
    @role_required('admin')
    def post(self):
        """Akses: (Admin) | Upload soal tryout via file CSV/XLSX"""
        args = upload_soal_parser.parse_args()
        file = args['file']
        id_tryout = args['id_tryout']

        try:
            # Load file
            if file.filename.endswith(".csv"):
                df = pd.read_csv(file)
            elif file.filename.endswith(".xlsx"):
                df = pd.read_excel(file)
            else:
                return {"message": "Format file harus .csv atau .xlsx"}, 400

            # Validasi kolom
            expected_columns = ['no', 'pertanyaan', 'pilihan_a', 'pilihan_b', 'pilihan_c', 'pilihan_d', 'pilihan_e', 'jawaban_benar', 'pembahasan']
            if list(df.columns) != expected_columns:
                return {"message": f"Kolom harus sesuai format: {expected_columns}"}, 400

            soal_list = df.to_dict(orient='records')

            jumlah_soal_sekarang = get_jumlah_soal_tersimpan(id_tryout)
            jumlah_upload = len(soal_list)
            jumlah_maks = get_jumlah_soal_by_tryout(id_tryout)
            
            if jumlah_soal_sekarang + jumlah_upload > jumlah_maks:
                return {"message": f"Jumlah soal melebihi batas maksimum yaitu {jumlah_maks}"}, 400

            # Normalisasi dan validasi jawaban
            for s in soal_list:
                s['jawaban_benar'] = str(s['jawaban_benar']).strip().upper()
                if s['jawaban_benar'] not in ['A', 'B', 'C', 'D', 'E']:
                    return {"message": f"Jawaban salah di soal nomor {s['no']}: hanya boleh A, B, C, D, E"}, 400

            # Cek jumlah soal maksimal dan sisa slot
            max_soal = get_jumlah_soal_by_tryout(id_tryout)
            if max_soal is None:
                return {"message": "Tryout tidak ditemukan"}, 404

            count_existing = get_jumlah_soal_tersimpan(id_tryout)
            sisa_slot = max_soal - count_existing
            if len(soal_list) > sisa_slot:
                return {"message": f"Jumlah soal melebihi sisa slot ({sisa_slot} soal lagi boleh ditambahkan)"}, 400

            # Insert soal (abaikan kolom 'no')
            for s in soal_list:
                s.pop('no', None)

            inserted = insert_bulk_soaltryout(id_tryout, soal_list)
            if inserted:
                return {"message": f"{len(soal_list)} soal berhasil ditambahkan ke tryout {id_tryout}"}, 201
            return {"message": "Gagal menambahkan soal"}, 400

        except Exception as e:
            print(f"[ERROR UPLOAD SOAL] {e}")
            return {"message": "Terjadi kesalahan saat mengunggah soal"}, 500

