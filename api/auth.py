import random
import string
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from email_validator import validate_email, EmailNotValidError
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import SQLAlchemyError

from .utils.decorator import session_required

from .query.q_auth import *
from .utils.blacklist_store import blacklist


auth_ns = Namespace('auth', description='Endpoint Autentikasi Admin, Mentor dan Peserta')

login_model = auth_ns.model('Login', {
    'email': fields.String(required=True, description="email"),
    'password': fields.String(required=True, description="password")
})

logout_model = auth_ns.model('Logout', {
    'jti': fields.String(required=True)
})

register_model = auth_ns.model("Register", {
    "nama": fields.String(required=True),
    "email": fields.String(required=True),
    "password": fields.String(required=True)
})

# Step 1: hanya email
register_email_model = auth_ns.model("RegisterEmail", {
    "email": fields.String(required=True, description="Email peserta")
})

# Step 2: email + kode pemulihan
register_verify_model = auth_ns.model("RegisterVerify", {
    "email": fields.String(required=True, description="Email peserta"),
    "kode_pemulihan": fields.String(required=True, description="Kode pemulihan 6 digit")
})

# Step 3: lengkapi data
register_complete_model = auth_ns.model("RegisterComplete", {
    "email": fields.String(required=True, description="Email peserta"),
    "nama": fields.String(required=True, description="Nama lengkap"),
    "no_hp": fields.String(required=True, description="Nomor HP"),
    "password": fields.String(required=True, description="Password untuk login")
})

@auth_ns.route('/me')
class MeResource(Resource):
    @session_required
    @jwt_required()
    def get(self):
        """Ambil data user dari JWT token"""
        user_id = get_jwt_identity()
        try:
            user = get_user_by_id(user_id)
            if not user:
                return {"status": "error", "message": "User tidak ditemukan"}, 404
            return {"data": user}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": "Server error"}, 500
        

@auth_ns.route('/protected')
class ProtectedResource(Resource):
    @session_required
    @jwt_required()
    def get(self):
        """Akses: (admin/mentor/peserta), Cek token masih valid"""
        return {'status': 'Token masih valid'}, 200
    

@auth_ns.route('/login')
class LoginAdminResource(Resource):
    @auth_ns.expect(login_model)
    def post(self):
        """Akses: (admin/mentor/peserta), login menggunakan email + password"""
        payload = request.get_json()

        if not payload['email'] or not payload['password']:
            return {'status': "Fields can't be blank"}, 400

        try:
            get_jwt_response = get_login(payload)
            if get_jwt_response is None:
                return {'status': "Invalid email or password"}, 401
            return get_jwt_response, 200
        except SQLAlchemyError as e:
            auth_ns.logger.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500
        

@auth_ns.route('/kelas-saya')
class GetUserResource(Resource):
    @session_required
    @jwt_required()
    def get(self):
        """Ambil data user yang sedang login berdasarkan id_user dari JWT"""
        try:
            id_user = get_jwt_identity()  # id_user disimpan saat login di access_token
            user_data = ambil_kelas_saya(id_user)

            if user_data is None:
                return {'status': "User not found"}, 404
            return user_data, 200
        except SQLAlchemyError as e:
            auth_ns.logger.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500
        

@auth_ns.route('/login/web')
class LoginWebResource(Resource):
    @auth_ns.expect(login_model)
    def post(self):
        """Login khusus untuk web (admin/mentor/peserta), email + password"""
        payload = request.get_json()

        if not payload.get('email') or not payload.get('password'):
            return {'status': "Fields can't be blank"}, 400

        try:
            get_jwt_response = get_login_web(payload)
            if get_jwt_response is None:
                return {'status': "Invalid email or password"}, 401
            return get_jwt_response, 200
        except SQLAlchemyError as e:
            auth_ns.logger.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500


@auth_ns.route('/login/mobile')
class LoginMobileResource(Resource):
    @auth_ns.expect(login_model)
    def post(self):
        """Login khusus untuk mobile (admin/mentor/peserta), email + password"""
        payload = request.get_json()

        if not payload.get('email') or not payload.get('password'):
            return {'status': "Fields can't be blank"}, 400

        try:
            get_jwt_response = get_login_mobile(payload)
            if get_jwt_response is None:
                return {'status': "Invalid email or password"}, 401
            return get_jwt_response, 200
        except SQLAlchemyError as e:
            auth_ns.logger.error(f"Database error: {str(e)}")
            return {'status': "Internal server error"}, 500

        
@auth_ns.route('/logout')
class LogoutKaryawanResource(Resource):
    @auth_ns.expect(logout_model)
    @session_required
    @jwt_required()
    def post(self):
        """Akses: (admin/mentor/peserta), Logout karyawan dengan JTI blacklist"""
        jti = request.json.get('jti')
        if jti:
            blacklist.add(jti)
            return {"msg": "Logout successful"}, 200
        return {"msg": "Missing JTI"}, 400
    

# @auth_ns.route('/register')
# class RegisterPesertaResource(Resource):
#     @auth_ns.expect(register_model)
#     def post(self):
#         """Register Peserta Baru (tanpa login)"""
#         payload = request.get_json()

#         try:
#             # Validasi email format
#             valid = validate_email(payload["email"], check_deliverability=False)
#             payload["email"] = valid.email
#         except EmailNotValidError as e:
#             return {"status": "error", "message": str(e)}, 400

#         # Generate kode pemulihan
#         payload['kode_pemulihan'] = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        
#         # Hash password
#         payload['password'] = generate_password_hash(payload['password'])

#         try:
#             success = register_peserta(payload)
#             if not success:
#                 return {"status": "error", "message": "Email sudah digunakan"}, 409
#             return {"status": "success", "message": "Pendaftaran berhasil. Silakan login."}, 201
#         except SQLAlchemyError as e:
#             return {"status": "error", "message": "Server error"}, 500


# auth.py
@auth_ns.route('/register/email')
class RegisterStep1Resource(Resource):
    @auth_ns.expect(register_email_model, validate=True)
    def post(self):
        """Step 1: Daftar dengan email (generate kode pemulihan)"""
        payload = request.get_json()
        email = payload.get("email")

        try:
            valid = validate_email(email, check_deliverability=False)
            email = valid.email
        except EmailNotValidError as e:
            return {"status": "error", "message": str(e)}, 400

        try:
            success = register_step1(email)
            if not success:
                return {"status": "error", "message": "Email sudah terdaftar"}, 409
            return {"status": "success", "message": "Kode pemulihan dibuat. Cek email Anda."}, 201
        except SQLAlchemyError:
            return {"status": "error", "message": "Server error"}, 500


@auth_ns.route('/register/verify')
class RegisterStep2Resource(Resource):
    @auth_ns.expect(register_verify_model, validate=True)
    def post(self):
        """Step 2: Verifikasi email + kode pemulihan"""
        payload = request.get_json()
        email = payload.get("email")
        kode = payload.get("kode_pemulihan")

        try:
            verified = register_step2(email, kode)
            if not verified:
                return {"status": "error", "message": "Kode salah atau email tidak ditemukan"}, 400
            return {"status": "success", "message": "Verifikasi berhasil. Silakan lengkapi data."}, 200
        except SQLAlchemyError:
            return {"status": "error", "message": "Server error"}, 500


@auth_ns.route('/register/complete')
class RegisterStep3Resource(Resource):
    @auth_ns.expect(register_complete_model, validate=True)
    def post(self):
        """Step 3: Lengkapi data setelah verifikasi"""
        payload = request.get_json()
        email = payload.get("email")
        nama = payload.get("nama")
        no_hp = payload.get("no_hp")
        password = payload.get("password")

        hashed_password = generate_password_hash(password)

        try:
            updated = register_step3(email, nama, no_hp, hashed_password)
            if not updated:
                return {"status": "error", "message": "User tidak ditemukan atau belum verifikasi"}, 400
            return {"status": "success", "message": "Registrasi selesai. Silakan login."}, 200
        except SQLAlchemyError:
            return {"status": "error", "message": "Server error"}, 500

