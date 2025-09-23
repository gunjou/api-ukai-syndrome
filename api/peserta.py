import io
import os
import random
import string
import pandas as pd
from flask import Response, logging, request, send_file
from flask_restx import Namespace, Resource, fields, reqparse
from flask_restx.reqparse import FileStorage
from email_validator import validate_email, EmailNotValidError
from sqlalchemy.exc import SQLAlchemyError


from .query.q_peserta import *
from .utils.helper import get_sample_file
from .utils.decorator import role_required, session_required

peserta_ns = Namespace("peserta", description="Peserta related endpoints")

peserta_model = peserta_ns.model("Peserta", {
    "nama": fields.String(required=True, description="Nama peserta"),
    "email": fields.String(required=True, description="Email peserta"),
    "password": fields.String(required=False, description="Password peserta (kosongkan jika tidak diubah)"),
    "no_hp": fields.String(required=False, description="Nomor HP peserta"),
    "id_kelas": fields.Integer(required=False, description="ID Kelas yang diikuti"),
    "id_batch": fields.Integer(required=False, description="ID Batch yang diikuti")
})

upload_peserta_parser = reqparse.RequestParser()
upload_peserta_parser.add_argument(
    "file", type=FileStorage, location="files", required=True, help="File peserta (CSV/XLSX) harus diunggah"
)

@peserta_ns.route('')
class PesertaListResource(Resource):
    # @session_required
    @role_required('admin')
    def get(self):
        """Akses: (admin), Mengambil list semua peserta"""
        try:
            result = get_all_peserta()
            if not result:
                return {'status': 'error', 'message': 'Tidak ada peserta ditemukan'}, 404
            return result, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500

    # @session_required
    @role_required('admin')
    @peserta_ns.expect(peserta_model)
    def post(self):
        """Akses: (admin), Menambahkan peserta baru sekaligus batch & kelas"""
        payload = request.get_json()

        # Validasi email
        try:
            valid = validate_email(payload.get("email", ""), check_deliverability=False)
            payload["email"] = valid.email
        except EmailNotValidError as e:
            return {"status": "error", "message": str(e)}, 400

        try:
            new_peserta = insert_peserta_with_batch_kelas(payload)

            # Cek apakah error dari fungsi
            if new_peserta and new_peserta.get("error"):
                return {
                    "status": "error",
                    "message": new_peserta["message"],
                    "data": new_peserta["data"]
                }, 400

            if not new_peserta:
                return {"status": "Gagal menambahkan peserta"}, 400

            return {
                "data": new_peserta, 
                "status": f"Peserta {new_peserta['nama']} berhasil ditambahkan"
            }, 201
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500


@peserta_ns.route('/template')
class DownloadPesertaTemplateResource(Resource):
    @peserta_ns.produces(["text/csv"])
    @peserta_ns.response(200, "CSV file")
    # @role_required('admin')
    def get(self):
        """Akses: (Admin) | Download template CSV peserta"""
        file_path = get_sample_file('template_peserta.csv')
        print(file_path)

        if not os.path.exists(file_path):
            return {"message": "File template tidak ditemukan"}, 404

        return send_file(
            file_path,
            mimetype="text/csv",
            as_attachment=True,
            download_name="template_peserta.csv"
        )

@peserta_ns.route('/upload')
class UploadPesertaResource(Resource):
    @peserta_ns.expect(upload_peserta_parser)
    @role_required('admin')
    def post(self):
        """Akses: (Admin) | Upload peserta via file CSV/XLSX"""
        args = upload_peserta_parser.parse_args()
        file = args['file']

        try:
            # Load file
            if file.filename.endswith(".csv"):
                df = pd.read_csv(file, sep=';')
            elif file.filename.endswith(".xlsx"):
                df = pd.read_excel(file)
            else:
                return {"message": "Format file harus .csv atau .xlsx"}, 400

            # Validasi kolom
            expected_columns = ["no", "nama", "email", "no_hp", "kelas"]
            if list(df.columns) != expected_columns:
                return {"message": f"Kolom harus sesuai format: {expected_columns}"}, 400

            peserta_list = df.to_dict(orient='records')

            # Hapus kolom 'no'
            for p in peserta_list:
                p.pop("no", None)

            # Validasi email
            for p in peserta_list:
                try:
                    valid = validate_email(p["email"], check_deliverability=False)
                    p["email"] = valid.email
                except EmailNotValidError as e:
                    return {"message": f"Email tidak valid ({p['email']}): {str(e)}"}, 400

            # Insert bulk
            inserted = insert_bulk_peserta(peserta_list)
            if inserted is None:
                return {"message": "Gagal menambahkan peserta"}, 400

            if inserted["invalid_kelas"]:
                return {
                    "status": "error",
                    "message": "Terdapat kelas yang tidak tersedia",
                    "invalid_kelas": inserted["invalid_kelas"]
                }, 400

            jumlah_sukses = len(inserted["inserted"])
            jumlah_duplikat = len(inserted["duplicates"])
            jumlah_invalid = len(inserted["invalid_kelas"])

            return {
                "status": "success",
                "message": f"{jumlah_sukses} peserta berhasil ditambahkan. {jumlah_duplikat} duplikat, {jumlah_invalid} gagal karena kelas tidak ditemukan.",
                "duplicates": inserted["duplicates"],
                "invalid_kelas": inserted["invalid_kelas"]
            }, 201


        except Exception as e:
            print(f"[ERROR UPLOAD PESERTA] {e}")
            return {"message": "Terjadi kesalahan saat mengunggah peserta"}, 500
        
@peserta_ns.route('/<int:id_peserta>')
class PesertaDetailResource(Resource):
    # @session_required
    @role_required('admin')
    def get(self, id_peserta):
        """Akses: (admin), Mengambil data peserta berdasarkan ID"""
        try:
            peserta = get_peserta_by_id(id_peserta)
            if not peserta:
                return {'status': 'error', 'message': 'Peserta tidak ditemukan'}, 404
            return {'data': peserta}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500

    # @session_required
    @role_required('admin')
    @peserta_ns.expect(peserta_model, validate=False)
    def put(self, id_peserta):
        """Akses: (admin), Edit data peserta berdasarkan ID"""
        data = request.get_json()
        if not data:
            return {"status": "error", "message": "Payload tidak boleh kosong"}, 400

        old_data = get_peserta_by_id(id_peserta)
        if not old_data:
            return {"status": "error", "message": "Peserta tidak ditemukan"}, 404

        # 🔹 Validasi email duplikat (kalau email diganti)
        if "email" in data and data["email"] != old_data["email"]:
            from query.q_peserta import check_email_exists
            if check_email_exists(data["email"], exclude_id=id_peserta):
                return {"status": "error", "message": f"Email {data['email']} sudah digunakan"}, 400

        updated_payload = {
            "nama": data.get("nama", old_data["nama"]),
            "email": data.get("email", old_data["email"]),
            "password": data.get("password", ""),
            "kode_pemulihan": data.get("kode_pemulihan", old_data["kode_pemulihan"]),
            "no_hp": data.get("no_hp", old_data.get("no_hp")),
            "id_kelas": data.get("id_kelas", old_data.get("id_kelas")),
            "id_batch": data.get("id_batch", old_data.get("id_batch")),
        }

        try:
            updated = update_peserta(id_peserta, updated_payload)
            if not updated:
                return {'status': 'error', "message": "Gagal update peserta"}, 400
            return {"status": f"{updated['nama']} berhasil diperbarui"}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500


    # @session_required
    @role_required('admin')
    def delete(self, id_peserta):
        """Akses: (admin), Menghapus (nonaktifkan) peserta berdasarkan ID"""
        try:
            deleted = delete_peserta(id_peserta)
            if not deleted:
                return {'status': 'error', "message": "Peserta tidak ditemukan"}, 404
            return {"status": f"{deleted['nama']} berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500


@peserta_ns.route('/reset-password/<int:id_peserta>')
class PesertaResetPasswordResource(Resource):
    # @session_required
    @role_required('admin')
    def put(self, id_peserta):
        """Akses: (admin), Reset password peserta ke default berdasarkan ID"""
        try:
            success = reset_password_peserta(id_peserta)
            if not success:
                return {"status": "error", "message": "Gagal reset password peserta"}, 400
            return {"status": "success", "message": "Password peserta telah di-reset"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500