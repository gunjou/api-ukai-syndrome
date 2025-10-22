from flask import request
from flask_restx import Namespace, Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from .utils.decorator import role_required, session_required
from .query.q_tryout import *


tryout_ns = Namespace('tryout', description='Manajemen Tryout')

# parser untuk input tryout
create_tryout_parser = reqparse.RequestParser()
create_tryout_parser.add_argument('judul', type=str, required=True, help='Judul tryout')
create_tryout_parser.add_argument('jumlah_soal', type=int, required=True, help='Jumlah soal')
create_tryout_parser.add_argument('durasi', type=int, required=True, help='Durasi dalam menit')
create_tryout_parser.add_argument('max_attempt', type=int, required=True, help='Jumlah maksimal percobaan')

assign_class_parser = reqparse.RequestParser()
assign_class_parser.add_argument('id_tryout', type=int, required=True, help='ID tryout')
assign_class_parser.add_argument('id_batch', type=int, required=False, help='ID batch (opsional)')
assign_class_parser.add_argument('id_paketkelas', type=int, action='append', required=False, help='List ID paketkelas (opsional)')


@tryout_ns.route('/list')
class TryoutListResource(Resource):
    # @session_required
    @jwt_required()
    @role_required(['mentor', 'peserta'])
    def get(self):
        """Akses: (mentor/peserta) | Get daftar tryout yang tersedia untuk peserta atau mentor"""
        id_user = get_jwt_identity()
        role = get_jwt().get("role")

        if role not in ['peserta', 'mentor']:
            return {"message": "Role tidak diizinkan"}, 403

        tryouts = get_tryout_list_by_user(id_user, role)
        return {"data": tryouts}, 200
    
@tryout_ns.route('/all-tryout')
class AdminTryoutListResource(Resource):
    # @session_required
    @jwt_required()
    @role_required(['admin'])
    @tryout_ns.param('id_batch', 'ID Batch untuk filter', type='integer')
    @tryout_ns.param('id_paketkelas', 'ID Paket Kelas untuk filter', type='integer')
    def get(self):
        """Akses: (admin) | Get daftar tryout berdasarkan batch atau kelas"""
        id_batch = request.args.get('id_batch', type=int)
        id_paketkelas = request.args.get('id_paketkelas', type=int)

        # if not id_batch and not id_paketkelas:
        #     return {"message": "Minimal salah satu dari id_batch atau id_paketkelas harus diisi"}, 400

        # (Opsional) Validasi id_batch dan id_paketkelas benar-benar ada di DB
        if id_batch and not is_valid_batch(id_batch):
            return {"message": f"Batch dengan ID {id_batch} tidak ditemukan"}, 404

        if id_paketkelas and not is_valid_paketkelas(id_paketkelas):
            return {"message": f"Paket kelas dengan ID {id_paketkelas} tidak ditemukan"}, 404

        tryouts = get_tryout_list_admin(id_batch=id_batch, id_paketkelas=id_paketkelas)
        return {"data": tryouts}, 200
    

@tryout_ns.route('')
class TryoutCreateResource(Resource):
    @tryout_ns.expect(create_tryout_parser)
    # @session_required
    @jwt_required()
    @role_required('admin')
    def post(self):
        """Akses: (Admin) | Membuat tryout baru"""
        data = create_tryout_parser.parse_args()

        try:
            new_id = insert_new_tryout(data)
            if new_id:
                return {"message": "Tryout berhasil dibuat", "id_tryout": new_id}, 201
            return {"message": "Gagal membuat tryout"}, 400
        except Exception as e:
            print(f"[ERROR POST /tryout] {e}")
            return {"message": "Terjadi kesalahan saat membuat tryout"}, 500


@tryout_ns.route('/assign-to-class')
class TryoutAssignToClassResource(Resource):
    @tryout_ns.expect(assign_class_parser)
    # @session_required
    @jwt_required()
    @role_required('admin')
    def post(self):
        """Akses: Admin | Assign tryout ke semua kelas dalam batch atau ke kelas tertentu"""
        args = assign_class_parser.parse_args()
        id_tryout = args['id_tryout']
        id_batch = args.get('id_batch')
        id_paketkelas_list = args.get('id_paketkelas')  # Bisa None

        # VALIDASI: Minimal satu dari batch atau list kelas harus diisi
        if not id_batch and not id_paketkelas_list:
            return {
                "message": "Minimal salah satu dari id_batch atau id_paketkelas harus diisi."
            }, 400

        try:
            success = assign_tryout_to_classes(id_tryout, id_batch, id_paketkelas_list)
            if success:
                return {"message": "Tryout berhasil di-assign ke kelas"}, 201
            return {"message": "Tidak ada kelas yang berhasil di-assign"}, 400
        except Exception as e:
            print(f"[ERROR POST /assign-to-class] {e}")
            return {"message": "Terjadi kesalahan saat assign tryout ke kelas"}, 500


"""#=== Mulai pengerjaan tryout ===#"""
@tryout_ns.route('/<int:id_tryout>/attempts/start')
class StartAttemptResource(Resource):
    @session_required
    @jwt_required()
    @role_required(['peserta'])
    def post(self, id_tryout):
        """Akses: (peserta) | Mulai attempt tryout"""
        id_user = get_jwt_identity()

        attempt_data, error = start_tryout_attempt(id_tryout, id_user)

        if error:
            return {"message": error}, 400
        return {"data": attempt_data}, 201
    
@tryout_ns.route('/<int:id_tryout>/questions')
class TryoutQuestionsResource(Resource):
    @session_required
    @jwt_required()
    @role_required(['peserta'])
    def get(self, id_tryout):
        """Akses: (peserta) | Ambil daftar soal tryout"""
        id_user = get_jwt_identity()

        questions, error = get_tryout_questions(id_tryout, id_user)

        if error:
            return {"message": error}, 400
        return {"data": questions}, 200
    

@tryout_ns.route('/<int:id_tryout>/remaining-attempts')
class RemainingAttemptsResource(Resource):
    @session_required
    @jwt_required()
    @role_required(['peserta'])
    def get(self, id_tryout):
        """Akses: (peserta) | Ambil sisa attempt user pada tryout"""
        id_user = get_jwt_identity()

        attempts, error = get_remaining_attempts(id_tryout, id_user)

        if error:
            return {"message": error}, 400
        return {"data": attempts}, 200


@tryout_ns.route('/<int:id_tryout>/attempts/<string:attempt_token>')
class AttemptDetailResource(Resource):
    @session_required
    @jwt_required()
    @role_required(['peserta'])
    def get(self, id_tryout, attempt_token):
        """Akses: (peserta) | Ambil detail attempt user"""
        id_user = get_jwt_identity()

        attempt, error = get_attempt_detail(id_tryout, id_user, attempt_token)

        if error:
            return {"message": error}, 400
        return {"data": attempt}, 200
