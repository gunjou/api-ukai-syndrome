from flask import request
from flask_restx import Namespace, Resource, reqparse, fields
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

edit_tryout_parser = reqparse.RequestParser()
edit_tryout_parser.add_argument('judul', type=str, required=False, help='Judul tryout')
edit_tryout_parser.add_argument('jumlah_soal', type=int, required=False, help='Jumlah soal maksimal')
edit_tryout_parser.add_argument('durasi', type=int, required=False, help='Durasi tryout dalam menit')
edit_tryout_parser.add_argument('max_attempt', type=int, required=False, help='Jumlah maksimal attempt')
edit_tryout_parser.add_argument('visibility', type=str, required=False, choices=('hold', 'open'), help='Status visibility tryout')

visibility_parser = reqparse.RequestParser()
visibility_parser.add_argument('visibility', type=str, required=True, choices=('hold', 'open'), help="Status visibility tryout ('hold' atau 'open')")

attempt_answer_model = tryout_ns.model("AttemptAnswer", {
    "attempt_token": fields.String(required=True, description="UUID token attempt"),
    "nomor": fields.Integer(required=True, description="Nomor soal (1-based)"),
    "jawaban": fields.String(required=False, description="Jawaban peserta (mis. A/B/C/D)"),
    "ragu": fields.Integer(required=False, description="Flag ragu (0 atau 1)", example=0),
})

attempt_submit_model = tryout_ns.model("AttemptSubmit", {
    "attempt_token": fields.String(required=True, description="UUID token attempt")
})


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
        
        
@tryout_ns.route('/<int:id_tryout>/edit')
class TryoutEditResource(Resource):
    @jwt_required()
    @role_required('admin')
    @tryout_ns.expect(edit_tryout_parser)  # supaya muncul di Swagger
    def put(self, id_tryout):
        """Akses: (Admin) | Edit data tryout"""
        args = edit_tryout_parser.parse_args()
        try:
            result = update_tryout(id_tryout, args)
            if result["success"]:
                return {"message": result["message"]}, 200
            return {"message": result["message"]}, 400
        except Exception as e:
            print(f"[ERROR PUT /tryout/{id_tryout}/edit] {e}")
            return {"message": "Terjadi kesalahan saat memperbarui tryout"}, 500
        
        
@tryout_ns.route('/delete/<int:id_tryout>')
class TryoutDeleteResource(Resource):
    @jwt_required()
    @role_required(['admin'])
    def delete(self, id_tryout):
        """Akses: (admin) | Soft delete tryout (ubah status menjadi 0)"""
        
        try:
            # Cek apakah tryout dengan ID tersebut ada
            tryout = get_tryout_by_id(id_tryout)
            if not tryout:
                return {"message": f"Tryout dengan ID {id_tryout} tidak ditemukan"}, 404

            # Lakukan soft delete dengan mengubah status menjadi 0
            if soft_delete_tryout(id_tryout):
                return {"message": "Tryout berhasil dihapus (soft delete)"}, 200
            else:
                return {"message": "Terjadi kesalahan saat menghapus tryout"}, 500
        except Exception as e:
            return {"message": f"Error: {str(e)}"}, 500


@tryout_ns.route('/<int:id_tryout>/visibility')
class TryoutVisibilityResource(Resource):
    @jwt_required()
    @role_required('admin')
    @tryout_ns.expect(visibility_parser)
    def put(self, id_tryout):
        """Akses: (Admin) | Update visibility tryout (hold/open)"""
        args = visibility_parser.parse_args()
        visibility = args['visibility']
        try:
            result = update_tryout_visibility(id_tryout, visibility)
            if result["success"]:
                return {"message": result["message"]}, 200
            return {"message": result["message"]}, 400
        except Exception as e:
            print(f"[ERROR PUT /tryout/{id_tryout}/visibility] {e}")
            return {"message": "Terjadi kesalahan saat memperbarui visibility"}, 500


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


@tryout_ns.route('/attempts/answer')
class SaveAttemptAnswerResource(Resource):
    @session_required
    @jwt_required()
    @role_required(['peserta'])
    @tryout_ns.expect(attempt_answer_model, validate=True)
    @tryout_ns.response(200, "Jawaban tersimpan")
    @tryout_ns.response(400, "Input tidak valid / error")
    def put(self):
        """
        Simpan jawaban sementara untuk sebuah attempt.
        Body JSON:
        {
          "attempt_token": "<token>",
          "nomor": <int>,
          "jawaban": "<jawaban>",  // optional
          "ragu": 0|1              // optional
        }
        """
        id_user = get_jwt_identity()
        data = request.get_json()

        attempt_token = data.get("attempt_token")
        nomor = data.get("nomor")
        jawaban = data.get("jawaban", None)
        ragu = data.get("ragu", 0)

        if not attempt_token or not nomor:
            return {"message": "attempt_token dan nomor wajib diisi"}, 400

        try:
            updated_jawaban, err = save_tryout_answer(
                attempt_token, id_user, int(nomor), jawaban, int(ragu), None
            )
            if err:
                return {"message": err}, 400
            # return {"status": "success", "jawaban_user": updated_jawaban}, 200
            return {"status": "success", "message": f"Jawaban nomor {nomor} telah ditambahkan"}, 200
        except SQLAlchemyError as e:
            print(f"[ENDPOINT save answer] {e}")
            return {"message": "Internal server error"}, 500
        
        
@tryout_ns.route('/attempts/submit')
class SubmitAttemptResource(Resource):
    @session_required
    @jwt_required()
    @role_required(['peserta'])
    @tryout_ns.expect(attempt_submit_model, validate=True)
    @tryout_ns.response(200, "Submit berhasil")
    @tryout_ns.response(400, "Error")
    def post(self):
        """
        Submit attempt (final). Body:
        { "attempt_token": "<token>" }
        """
        id_user = get_jwt_identity()
        data = request.get_json()
        attempt_token = data.get("attempt_token")

        if not attempt_token:
            return {"message": "attempt_token wajib diisi"}, 400

        try:
            result, err = submit_tryout_attempt(attempt_token, id_user)
            if err:
                return {"message": err}, 400
            return {"status": "success", "result": result}, 200
        except SQLAlchemyError as e:
            print(f"[ENDPOINT submit attempt] {e}")
            return {"message": "Internal server error"}, 500