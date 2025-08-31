import random
import string
from flask import logging, request
from flask_restx import Namespace, Resource, fields
from email_validator import validate_email, EmailNotValidError
from sqlalchemy.exc import SQLAlchemyError

from .query.q_peserta import *
from .utils.decorator import role_required, session_required

peserta_ns = Namespace("peserta", description="Peserta related endpoints")

peserta_model = peserta_ns.model("Peserta", {
    "nama": fields.String(required=True, description="nama peserta"),
    "email": fields.String(required=True, description="email peserta"),
    "password": fields.String(required=True, description="password peserta")
})

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
        """Akses: (admin), Menambahkan peserta baru"""
        payload = request.get_json()

        try:
            valid = validate_email(payload.get("email", ""), check_deliverability=False)
            payload["email"] = valid.email
        except EmailNotValidError as e:
            return {"status": "error", "message": str(e)}, 400

        payload['kode_pemulihan'] = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

        try:
            new_peserta = insert_peserta(payload)
            if not new_peserta:
                return {"status": "Gagal menambahkan peserta"}, 400
            return {"data": new_peserta, "status": f"Peserta {new_peserta['nama']} berhasil ditambahkan"}, 201
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500


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

        updated_payload = {
            "nama": data.get("nama", old_data["nama"]),
            "email": data.get("email", old_data["email"]),
            "password": data.get("password", ""),
            "kode_pemulihan": data.get("kode_pemulihan", old_data["kode_pemulihan"])
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
