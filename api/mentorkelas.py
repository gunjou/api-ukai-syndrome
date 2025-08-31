from flask import request
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError
from .utils.decorator import role_required, session_required
from .query.q_mentorkelas import *

mentorkelas_ns = Namespace("mentorkelas", description="Manajemen penugasan mentor ke kelas")

mentorkelas_model = mentorkelas_ns.model("MentorKelas", {
    "id_user": fields.Integer(required=True, description="ID mentor"),
    "id_paketkelas": fields.Integer(required=True, description="ID kelas")
})

@mentorkelas_ns.route('')
class MentorKelasListResource(Resource):
    @session_required
    @role_required('admin')
    def get(self):
        """Akses: (admin), Ambil semua penugasan mentor"""
        try:
            result = get_all_mentorkelas()
            if not result:
                return {"status": "error", "message": "Tidak ada data ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @session_required
    @role_required('admin')
    @mentorkelas_ns.expect(mentorkelas_model)
    def post(self):
        """Akses: (admin), Tambahkan penugasan mentor ke kelas"""
        payload = request.get_json()

        if not is_valid_mentor(payload["id_user"]):
            return {"status": "error", "message": "Mentor tidak valid"}, 400
        if not is_valid_kelas(payload["id_paketkelas"]):
            return {"status": "error", "message": "Kelas tidak ditemukan"}, 400

        try:
            created = insert_mentorkelas(payload)
            if not created:
                return {"status": "error", "message": "Gagal menambahkan penugasan"}, 400
            return {"status": f"Penugasan berhasil ditambahkan", "data": created}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

@mentorkelas_ns.route('/<int:id_mentorkelas>')
class MentorKelasDetailResource(Resource):
    @session_required
    @role_required('admin')
    def get(self, id_mentorkelas):
        """Akses: (admin), Ambil detail penugasan mentor"""
        try:
            data = get_mentorkelas_by_id(id_mentorkelas)
            if not data:
                return {"status": "error", "message": "Data tidak ditemukan"}, 404
            return {"data": data}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @session_required
    @role_required('admin')
    @mentorkelas_ns.expect(mentorkelas_model, validate=False)
    def put(self, id_mentorkelas):
        """Akses: (admin), Edit penugasan mentor"""
        data = request.get_json()
        old = get_mentorkelas_by_id(id_mentorkelas)
        if not old:
            return {"status": "error", "message": "Data tidak ditemukan"}, 404

        # Validasi jika diubah
        if "id_user" in data and not is_valid_mentor(data["id_user"]):
            return {"status": "error", "message": "Mentor tidak valid"}, 400
        if "id_paketkelas" in data and not is_valid_kelas(data["id_paketkelas"]):
            return {"status": "error", "message": "Kelas tidak valid"}, 400

        updated_payload = {
            "id_user": data.get("id_user", old["id_user"]),
            "id_paketkelas": data.get("id_paketkelas", old["id_paketkelas"])
        }

        try:
            updated = update_mentorkelas(id_mentorkelas, updated_payload)
            if not updated:
                return {"status": "error", "message": "Gagal update"}, 400
            return {"status": f"Penugasan berhasil diperbarui"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @session_required
    @role_required('admin')
    def delete(self, id_mentorkelas):
        """Akses: (admin), Nonaktifkan penugasan mentor"""
        try:
            deleted = delete_mentorkelas(id_mentorkelas)
            if not deleted:
                return {"status": "error", "message": "Data tidak ditemukan"}, 404
            return {"status": f"Penugasan mentor berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
