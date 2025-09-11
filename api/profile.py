from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError

from .utils.decorator import session_required
from .query.q_profile import *

profile_ns = Namespace('profile', description='Manajement profil pengguna')

update_profile_model = profile_ns.model("UpdateProfile", {
    "nama": fields.String(required=False, description="Nama baru pengguna"),
    "no_hp": fields.String(required=False, description="Nomor HP baru pengguna")
})

change_password_model = profile_ns.model("ChangePassword", {
    "password_lama": fields.String(required=True, description="Password lama pengguna"),
    "password_baru": fields.String(required=True, description="Password baru"),
    "konfirmasi_password_baru": fields.String(required=True, description="Konfirmasi password baru")
})

@profile_ns.route('')
class UpdateProfileResource(Resource):
    @jwt_required()
    def get(self):
        """Akses: (admin/mentor/peserta), Ambil data user dari JWT token"""
        user_id = get_jwt_identity()
        try:
            user = get_user_by_id(user_id)
            if not user:
                return {"status": "error", "message": "User tidak ditemukan"}, 404
            return {"data": user}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": "Server error"}, 500
        
    @jwt_required()
    @profile_ns.expect(update_profile_model)
    def put(self):
        """Akses: (mentor/peserta), Edit profile akun sendiri (nama atau no_hp, keduanya opsional)"""
        id_user = get_jwt_identity()
        payload = request.get_json()

        nama = payload.get("nama")
        no_hp = payload.get("no_hp")

        # Validasi minimal ada 1 field
        if not nama and not no_hp:
            return {"status": "error", "message": "Minimal salah satu field harus diisi"}, 400

        result, status_code = update_profile(id_user, nama, no_hp)
        return result, status_code
    

@profile_ns.route('/password')
class ChangePasswordResource(Resource):
    @jwt_required()
    @profile_ns.expect(change_password_model)
    def put(self):
        """Akses: (admin/mentor/peserta), Ubah password akun sendiri (hanya untuk user yang login)"""
        id_user = get_jwt_identity()
        payload = request.get_json()

        password_lama = payload.get("password_lama")
        password_baru = payload.get("password_baru")
        konfirmasi_password_baru = payload.get("konfirmasi_password_baru")

        # Validasi input
        if not password_lama or not password_baru or not konfirmasi_password_baru:
            return {"status": "error", "message": "Semua field wajib diisi"}, 400

        result, status_code = change_password(
            id_user, password_lama, password_baru, konfirmasi_password_baru
        )
        return result, status_code
    
@profile_ns.route('/kelas-saya')
class GetUserResource(Resource):
    @jwt_required()
    def get(self):
        """Akses: (mentor, peserta), Ambil data user yang sedang login berdasarkan id_user dari JWT"""
        try:
            id_user = get_jwt_identity()   # id_user dari JWT
            current_role = get_jwt()["role"]  # role dari JWT

            user_data = ambil_kelas_saya(id_user, current_role)

            if user_data is None:
                return {"status": "User not found"}, 404
            return user_data, 200

        except SQLAlchemyError as e:
            profile_ns.logger.error(f"Database error: {str(e)}")
            return {"status": "Internal server error"}, 500