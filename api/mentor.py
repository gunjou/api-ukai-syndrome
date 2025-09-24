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
    "nama": fields.String(required=True, description="Nama mentor"),
    "email": fields.String(required=True, description="Email mentor"),
    "password": fields.String(required=True, description="Password mentor"),
    "no_hp": fields.String(required=False, description="Nomor HP mentor"),
    "id_paketkelas": fields.Integer(required=False, description="ID kelas yang diampu (opsional)")
})

@mentor_ns.route('')
class MentorListResource(Resource):
    @role_required('admin')
    def get(self):
        """Akses: (admin), Mengambil list semua mentor + kelas"""
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

            # 🔍 Handle error dari insert_mentor
            if new_mentor.get("error"):
                return {
                    "status": "error",
                    "message": new_mentor["message"],
                    "data": new_mentor["data"]
                }, 400

            if new_mentor.get("id_paketkelas"):
                msg = f"Mentor {new_mentor['nama']} berhasil ditambahkan ke kelas {new_mentor['id_paketkelas']}"
            else:
                msg = f"Mentor {new_mentor['nama']} berhasil ditambahkan (belum ada kelas)"

            return {"data": new_mentor, "status": msg}, 201
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
        data = request.get_json()
        if not data:
            return {"status": "error", "message": "Payload tidak boleh kosong"}, 400

        old_mentor = get_mentor_by_id(id_mentor)
        if not old_mentor:
            return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

        updated_payload = {
            "nama": data.get("nama", old_mentor["nama"]),
            "nickname": data.get("nickname", old_mentor["nickname"]),
            "email": data.get("email", old_mentor["email"]),
            "password": data.get("password", ""),
            "no_hp": data.get("no_hp", old_mentor.get("no_hp")),
            "id_paketkelas": data.get("id_paketkelas"),  # opsional
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


@mentor_ns.route('/bio-mentor')
class MentorSimpleResource(Resource):
    @role_required('admin')
    def get(self):
        """Akses: (admin), Mengambil list biodata semua mentor"""
        try:
            result = get_bio_all_mentor()
            if not result:
                return {'status': 'error', 'message': 'Tidak ada mentor yang ditemukan'}, 404
            return {"respon": 200, "total_mentor":len (result), "data": result}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500