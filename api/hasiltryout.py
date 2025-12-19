from flask import request, send_file
from flask_restx import Namespace, Resource, reqparse, fields
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from .utils.helper import generate_excel_hasiltryout, generate_pdf_hasiltryout
from .utils.decorator import role_required, session_required
from .query.q_hasiltryout import *


hasiltryout_ns = Namespace('hasiltryout', description='Manajemen hasil tryout')

@hasiltryout_ns.route('/statistik')
class HasilTryoutStatistikResource(Resource):
    @jwt_required()
    @role_required(['admin', 'mentor'])
    @hasiltryout_ns.param('id_tryout', 'ID tryout yang ingin diambil statistiknya', type='integer', required=True)
    def get(self):
        """Akses: (admin) | Statistik untuk satu tryout"""
        id_tryout = request.args.get('id_tryout', type=int)

        if not id_tryout:
            return {"message": "Parameter id_tryout wajib diisi"}, 400

        try:
            data = get_statistik_by_tryout(id_tryout)
            if not data:
                return {"message": f"Statistik untuk tryout {id_tryout} tidak ditemukan"}, 404

            return {"status": "success", "total": len(data), "data": data}, 200

        except Exception as e:
            print(f"[ERROR GET /hasiltryout/statistik] {e}")
            return {"message": "Terjadi kesalahan"}, 500
        
        
@hasiltryout_ns.route('')
class HasilTryoutListResource(Resource):
    @jwt_required()
    @role_required(['admin'])
    @hasiltryout_ns.param('id_tryout', 'Filter berdasarkan ID Tryout')
    @hasiltryout_ns.param('id_user', 'Filter berdasarkan ID User')
    @hasiltryout_ns.param('tanggal_mulai', 'Filter tanggal dari yyyy-mm-dd')
    @hasiltryout_ns.param('tanggal_akhir', 'Filter tanggal sampai yyyy-mm-dd')
    @hasiltryout_ns.param('attempt_ke', 'Filter attempt ke berapa')
    @hasiltryout_ns.param('nilai_min', 'Nilai minimum')
    @hasiltryout_ns.param('nilai_max', 'Nilai maksimum')
    @hasiltryout_ns.param('status_pengerjaan', 'Status pengerjaan (selesai/belum)')
    def get(self):
        """
        Akses: (admin, mentor)
        Mendapatkan daftar hasil tryout dengan filter dinamis.
        """
        filters = {
            "id_tryout": request.args.get("id_tryout", type=int),
            "id_user": request.args.get("id_user", type=int),
            "tanggal_mulai": request.args.get("tanggal_mulai"),
            "tanggal_akhir": request.args.get("tanggal_akhir"),
            "attempt_ke": request.args.get("attempt_ke", type=int),
            "nilai_min": request.args.get("nilai_min", type=float),
            "nilai_max": request.args.get("nilai_max", type=float),
            "status_pengerjaan": request.args.get("status_pengerjaan"),
        }

        try:
            data = get_hasiltryout_list(filters)
            return {"status": "success", "total": len(data), "data": data}, 200

        except Exception as e:
            print(f"[ERROR GET /hasiltryout] {e}")
            return {"message": "Terjadi kesalahan saat mengambil daftar hasil tryout"}, 500
        
        
@hasiltryout_ns.route('/<int:id_hasiltryout>')
class HasilTryoutDetailResource(Resource):
    @jwt_required()
    @role_required(['admin', 'mentor'])
    def get(self, id_hasiltryout):
        """Akses: admin, mentor | Detail hasil 1 attempt berdasarkan id_hasiltryout"""

        try:
            data = get_detail_hasiltryout(id_hasiltryout)

            if not data:
                return {
                    "message": f"Hasil tryout dengan ID {id_hasiltryout} tidak ditemukan"
                }, 404

            return {"status": "success", "total": len(data), "data": data}, 200

        except Exception as e:
            print(f"[ERROR GET /hasiltryout/{id_hasiltryout}] {e}")
            return {"message": "Terjadi kesalahan"}, 500


@hasiltryout_ns.route('/<int:id_tryout>/leaderboard')
@hasiltryout_ns.param('limit', 'Jumlah ranking yang ingin ditampilkan (contoh: 5, 10). Kosongkan untuk semua.', type=int)
class TryoutLeaderboardResource(Resource):
    @jwt_required()
    @role_required(['admin', 'mentor'])
    def get(self, id_tryout):
        """Akses: admin, mentor | Leaderboard global 1 tryout"""

        try:
            limit = request.args.get("limit", default=None, type=int)

            data = get_leaderboard_tryout(id_tryout, limit)

            if data is None:
                return {"message": f"Tryout {id_tryout} tidak ditemukan atau belum ada peserta"}, 404

            return {"status": "success", "total": len(data), "data": data}, 200

        except Exception as e:
            print(f"[ERROR GET /tryout/{id_tryout}/leaderboard] {e}")
            return {"message": "Terjadi kesalahan"}, 500


@hasiltryout_ns.route('/<int:id_user>/rekap-tryout')
class RekapTryoutUserResource(Resource):
    @jwt_required()
    @role_required(['admin', 'mentor'])
    @hasiltryout_ns.param('id_tryout', 'Filter opsional berdasarkan ID Tryout')
    def get(self, id_user):
        """
        Akses: (admin, mentor)
        Mendapatkan rekap semua tryout yang pernah dikerjakan user.
        """
        id_tryout = request.args.get("id_tryout", type=int)

        try:
            data = get_rekap_tryout_user(id_user, id_tryout)

            if data is None or len(data) == 0:
                return {
                    "message": "Rekap tryout tidak ditemukan untuk user tersebut"
                }, 404

            return {"status": "success", "total": len(data), "data": data}, 200

        except Exception as e:
            print(f"[ERROR GET /users/{id_user}/rekap-tryout] {e}")
            return {"message": "Terjadi kesalahan"}, 500


@hasiltryout_ns.route('/<int:id_tryout>/export')
class HasilTryoutExportResource(Resource):
    @jwt_required()
    @role_required(['admin', 'mentor'])
    @hasiltryout_ns.param('format', 'Format export: excel/pdf (default: excel)')
    def get(self, id_tryout):
        """Akses: (admin, mentor) | Export hasil tryout dalam bentuk Excel atau PDF"""
        export_format = request.args.get("format", "excel")

        try:
            data = get_hasiltryout_by_tryout(id_tryout)

            if not data:
                return {"message": "Data hasil tryout tidak ditemukan"}, 404

            # === EXPORT EXCEL ===
            if export_format == "excel":
                export_path = generate_excel_hasiltryout(id_tryout, data)
                return send_file(export_path, as_attachment=True)

            # === EXPORT PDF ===
            elif export_format == "pdf":
                export_path = generate_pdf_hasiltryout(id_tryout, data)
                return send_file(export_path, as_attachment=True)

            else:
                return {"message": "Format tidak valid, gunakan excel atau pdf"}, 400

        except Exception as e:
            print(f"[ERROR GET /tryout/{id_tryout}/export] {e}")
            return {"message": "Terjadi kesalahan"}, 500
        
        
@hasiltryout_ns.route('/<int:id_hasiltryout>')
class DeleteHasilTryoutAttemptResource(Resource):
    @jwt_required()
    @role_required(['admin', 'mentor'])
    def delete(self, id_hasiltryout):
        """
        Hapus 1 attempt hasil tryout.
        Akses: admin, mentor
        """
        try:
            result = delete_hasil_tryout(id_hasiltryout)
            if result is None:
                return {
                    "status": False,
                    "message": "Terjadi kesalahan saat menghapus data"
                }, 500
            if result == 0:
                return {
                    "status": False,
                    "message": "Hasil tryout tidak ditemukan"
                }, 404
            return {
                "status": True,
                "message": "Hasil tryout berhasil dihapus"
            }, 200
        except Exception as e:
            print(f"[ERROR DELETE /hasiltryout/{id_hasiltryout}] {e}")
            return {
                "status": False,
                "message": "Terjadi kesalahan"
            }, 500
            
            
# ====== Tryout Mentor ====== #
@hasiltryout_ns.route('/mentor')
class HasilTryoutMentorResource(Resource):
    @jwt_required()
    @role_required(['mentor'])
    @hasiltryout_ns.param('id_tryout', 'Filter tryout tertentu (opsional)')
    def get(self):
        """
        Akses: (mentor)
        Mendapatkan hasil tryout hanya untuk tryout yang berada di paket kelas mentor.
        """
        id_mentor = get_jwt_identity()
        id_tryout = request.args.get("id_tryout", type=int)

        try:
            data = get_hasiltryout_list_for_mentor(id_mentor, id_tryout)
            return {"status": "success", "total": len(data), "data": data}, 200

        except Exception as e:
            print(f"[ERROR GET /hasiltryout/mentor] {e}")
            return {"status": "error", "message": "Gagal mengambil hasil tryout"}, 500


# ====== Tryout Peserta ====== #
@hasiltryout_ns.route('/peserta')
class HasilTryoutUserResource(Resource):
    @jwt_required()
    @role_required(['peserta', 'user'])  # atau role apapun untuk siswa
    @hasiltryout_ns.param('id_tryout', 'Filter berdasarkan ID Tryout')
    def get(self):
        """
        Akses: (peserta)
        Mendapatkan daftar hasil tryout milik user (peserta) yang sedang login.
        """
        user_id = get_jwt_identity()   # ambil id_user dari JWT

        filters = {
            "id_user": user_id,  # dipaksa dari JWT, tidak bisa override
            "id_tryout": request.args.get("id_tryout", type=int)
        }

        try:
            data = get_hasiltryout_list_peserta(filters)
            return {"status": "success", "total": len(data), "data": data}, 200

        except Exception as e:
            print(f"[ERROR GET /hasiltryout/peserta] {e}")
            return {"message": "Terjadi kesalahan saat mengambil hasil tryout user"}, 500


@hasiltryout_ns.route('/peserta/<int:id_hasiltryout>')
class HasilTryoutDetailPesertaResource(Resource):
    @jwt_required()
    @role_required(['peserta', 'user'])
    def get(self, id_hasiltryout):
        """
        Akses: (peserta)
        Melihat detail hasil tryout milik sendiri (review jawaban).
        """
        id_user = get_jwt_identity()

        try:
            data = get_hasiltryout_detail_peserta(id_hasiltryout, id_user)

            if not data:
                return {
                    "status": "error",
                    "message": "Hasil tryout tidak ditemukan atau bukan milik Anda"
                }, 404

            return {
                "status": "success",
                "data": data
            }, 200

        except Exception as e:
            print(f"[ERROR GET /hasiltryout/peserta/{id_hasiltryout}] {e}")
            return {
                "status": "error",
                "message": "Terjadi kesalahan saat mengambil detail hasil tryout"
            }, 500
