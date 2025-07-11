import random
import string
from flask import logging, request
from flask_restx import Namespace, Resource, fields
from email_validator import validate_email, EmailNotValidError
from sqlalchemy.exc import SQLAlchemyError

from .query.q_admin import *
from .utils.decorator import role_required


admin_ns = Namespace("admin", description="Admin related endpoints")

admin_model = admin_ns.model("Admin", {
    "nama": fields.String(required=True, description="nama admin"),
    "email": fields.String(required=True, description="email admin"),
    "password": fields.String(required=True, description="password admin")
})

@admin_ns.route('')
class AdminListResource(Resource):
    @role_required('admin')
    def get(self):
        """Akses: (admin), Mengambil list semua admin"""
        try:
            result = get_all_admin()
            if not result:
                return {'status': 'error', 'message': 'Tidak ada admin yang ditemukan'}, 401
            return result, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500
    
    @role_required('admin')
    @admin_ns.expect(admin_model)
    def post(self):
        """Akses: (admin), Menambahkan admin baru"""
        payload = request.get_json()

        # Validasi format email
        try:
            valid = validate_email(payload.get("email", ""), check_deliverability=False)
            payload["email"] = valid.email
        except EmailNotValidError as e:
            return {"status": "error", "message": str(e)}, 400

        # Generate kode pemulihan
        payload['kode_pemulihan'] = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        
        try:
            new_admin = insert_admin(payload)
            if not new_admin:
                return {"status": "Gagal menambahkan admin"}, 401
            return {"data": new_admin, "status": f"Admin {new_admin['nama']} berhasil ditambahkan"}, 201
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500
        

@admin_ns.route('/<int:id_admin>')
class AdminDetailResource(Resource):
    @role_required('admin')
    def get(self, id_admin):
        """Akses: (admin), Mengambil data admin berdasarkan ID"""
        try:
            admin = get_admin_by_id(id_admin)
            if not admin:
                return {'status': 'error', 'message': 'Admin tidak ditemukan'}, 404
            return {'data': admin}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500

    @role_required('admin')
    @admin_ns.expect(admin_model, validate=False)
    def put(self, id_admin):
        """Akses: (admin), Edit data admin berdasarkan ID"""
        data = request.get_json()
        if not data:
            return {"status": "error", "message": "Payload tidak boleh kosong"}, 400

        # Ambil data admin lama
        old_admin = get_admin_by_id(id_admin)
        if not old_admin:
            return {"status": "error", "message": "Admin tidak ditemukan"}, 404

        # Update hanya field yang dikirim
        updated_payload = {
            "nama": data.get("nama", old_admin["nama"]),
            "email": data.get("email", old_admin["email"]),
            "password": data.get("password", ""),  # hanya hash jika dikirim
            "kode_pemulihan": data.get("kode_pemulihan", old_admin["kode_pemulihan"])
        }

        try:
            updated = update_admin(id_admin, updated_payload)
            if not updated:
                return {'status': 'error', "message": "Gagal update"}, 400
            return {"status": f"{updated['nama']} berhasil diperbarui"}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500


    @role_required('admin')
    def delete(self, id_admin):
        """Akses: (admin), Menghapus (nonaktifkan) admin berdasarkan ID"""
        try:
            deleted_admin = delete_admin(id_admin)
            if not deleted_admin:
                return {'status': 'error', "message": "Admin tidak ditemukan"}, 404
            return {"status": f"{deleted_admin['nama']} berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500
