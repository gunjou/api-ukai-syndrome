import random
import string
from flask import logging, request
from flask_restx import Namespace, Resource, fields
from email_validator import validate_email, EmailNotValidError
from sqlalchemy.exc import SQLAlchemyError

from .query.q_mentor import *
from .utils.decorator import role_required, session_required

mentor_ns = Namespace("mentor", description="Mentor related endpoints")

mentor_model = mentor_ns.model("Mentor", {
    "nama": fields.String(required=True, description="nama mentor"),
    "email": fields.String(required=True, description="email mentor"),
    "password": fields.String(required=True, description="password mentor")
})

@mentor_ns.route('')
class MentorListResource(Resource):
    # @session_required
    @role_required('admin')
    def get(self):
        """Akses: (admin), Mengambil list semua mentor"""
        try:
            result = get_all_mentor()
            if not result:
                return {'status': 'error', 'message': 'Tidak ada mentor yang ditemukan'}, 404
            return result, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500

    # @session_required
    @role_required('admin')
    @mentor_ns.expect(mentor_model)
    def post(self):
        """Akses: (admin), Menambahkan mentor baru"""
        payload = request.get_json()

        try:
            valid = validate_email(payload.get("email", ""), check_deliverability=False)
            payload["email"] = valid.email
        except EmailNotValidError as e:
            return {"status": "error", "message": str(e)}, 400

        payload['kode_pemulihan'] = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

        try:
            new_mentor = insert_mentor(payload)
            if not new_mentor:
                return {"status": "Gagal menambahkan mentor"}, 400
            return {"data": new_mentor, "status": f"Mentor {new_mentor['nama']} berhasil ditambahkan"}, 201
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500


@mentor_ns.route('/<int:id_mentor>')
class MentorDetailResource(Resource):
    # @session_required
    @role_required('admin')
    def get(self, id_mentor):
        """Akses: (admin), Mengambil data mentor berdasarkan ID"""
        try:
            mentor = get_mentor_by_id(id_mentor)
            if not mentor:
                return {'status': 'error', 'message': 'Mentor tidak ditemukan'}, 404
            return {'data': mentor}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500

    # @session_required
    @role_required('admin')
    @mentor_ns.expect(mentor_model, validate=False)
    def put(self, id_mentor):
        """Akses: (admin), Edit data mentor berdasarkan ID"""
        data = request.get_json()
        if not data:
            return {"status": "error", "message": "Payload tidak boleh kosong"}, 400

        old_mentor = get_mentor_by_id(id_mentor)
        if not old_mentor:
            return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

        updated_payload = {
            "nama": data.get("nama", old_mentor["nama"]),
            "email": data.get("email", old_mentor["email"]),
            "password": data.get("password", ""),
            "kode_pemulihan": data.get("kode_pemulihan", old_mentor["kode_pemulihan"])
        }

        try:
            updated = update_mentor(id_mentor, updated_payload)
            if not updated:
                return {'status': 'error', "message": "Gagal update mentor"}, 400
            return {"status": f"{updated['nama']} berhasil diperbarui"}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500

    # @session_required
    @role_required('admin')
    def delete(self, id_mentor):
        """Akses: (admin), Menghapus (nonaktifkan) mentor berdasarkan ID"""
        try:
            deleted = delete_mentor(id_mentor)
            if not deleted:
                return {'status': 'error', "message": "Mentor tidak ditemukan"}, 404
            return {"status": f"{deleted['nama']} berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500
