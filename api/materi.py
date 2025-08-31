from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError
from .utils.decorator import role_required, session_required
from .query.q_materi import *

materi_ns = Namespace("materi", description="Manajemen Materi Modul")

materi_model = materi_ns.model("Materi", {
    "id_modul": fields.Integer(required=True, description="ID Modul"),
    "tipe_materi": fields.String(required=True, description="Jenis materi: video/pdf/file"),
    "judul": fields.String(required=True, description="Judul materi"),
    "url_file": fields.String(required=True, description="URL atau file path"),
    "visibility": fields.String(required=False, description="Status visibility (default: hold)"),
    "viewer_only": fields.Boolean(required=True, description="Hanya bisa dilihat, tidak bisa diunduh")
})

visibility_model = materi_ns.model("ModulVisibility", {
    "visibility": fields.String(required=True, description="Nilai visibility (open/hold/close)")
})

@materi_ns.route('')
class MateriListResource(Resource):
    @session_required
    @role_required('admin')
    def get(self):
        """Akses: (admin), Ambil semua materi"""
        try:
            result = get_all_materi()
            if not result:
                return {"status": "error", "message": "Tidak ada materi ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @session_required
    @role_required('admin')
    @materi_ns.expect(materi_model)
    def post(self):
        """Akses: (admin), Tambah materi baru"""
        payload = request.get_json()

        if not is_valid_modul(payload["id_modul"]):
            return {"status": "error", "message": "Modul tidak ditemukan"}, 400

        try:
            created = insert_materi(payload)
            if not created:
                return {"status": "error", "message": "Gagal menambahkan materi"}, 400
            return {"status": f"Materi '{created['judul']}' berhasil ditambahkan", "data": created}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

@materi_ns.route('/<int:id_materi>')
class MateriDetailResource(Resource):
    @session_required
    @role_required('admin')
    def get(self, id_materi):
        """Akses: (admin), Ambil detail materi"""
        try:
            materi = get_materi_by_id(id_materi)
            if not materi:
                return {"status": "error", "message": "Materi tidak ditemukan"}, 404
            return {"data": materi}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @session_required
    @role_required('admin')
    @materi_ns.expect(materi_model, validate=False)
    def put(self, id_materi):
        """Akses: (admin), Ubah data materi"""
        data = request.get_json()
        old = get_materi_by_id(id_materi)
        if not old:
            return {"status": "error", "message": "Materi tidak ditemukan"}, 404

        updated = {
            "id_modul": data.get("id_modul", old["id_modul"]),
            "tipe_materi": data.get("tipe_materi", old["tipe_materi"]),
            "judul": data.get("judul", old["judul"]),
            "url_file": data.get("url_file", old["url_file"]),
            "viewer_only": data.get("viewer_only", old["viewer_only"])
        }

        if not is_valid_modul(updated["id_modul"]):
            return {"status": "error", "message": "Modul tidak valid"}, 400

        try:
            result = update_materi(id_materi, updated)
            if not result:
                return {"status": "error", "message": "Gagal update materi"}, 400
            return {"status": f"Materi '{result['judul']}' berhasil diupdate"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @session_required
    @role_required('admin')
    def delete(self, id_materi):
        """Akses: (admin), Nonaktifkan materi"""
        try:
            deleted = delete_materi(id_materi)
            if not deleted:
                return {"status": "error", "message": "Materi tidak ditemukan"}, 404
            return {"status": f"Materi '{deleted['judul']}' berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

"""#== Endpoints lanjutan ==#"""
@materi_ns.route('/peserta')
class MateriPesertaResource(Resource):
    @session_required
    @jwt_required()
    @role_required('peserta')
    def get(self):
        """Akses: (peserta) Melihat materi yang tersedia untuk peserta"""
        id_user = get_jwt_identity()
        try:
            result = get_materi_by_peserta(id_user)
            if not result:
                return {"status": "error", "data": [], "message": "Tidak ada materi yang tersedia"}, 200
            return {"status": "success", "data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        
@materi_ns.route('/mentor')
class MateriMentorResource(Resource):
    @session_required
    @jwt_required()
    @role_required('mentor')
    def get(self):
        """Akses: (mentor) Melihat materi yang tersedia untuk mentor"""
        id_user = get_jwt_identity()
        try:
            result = get_materi_by_mentor(id_user)
            if not result:
                return {"status": "error", "data": [], "message": "Tidak ada materi yang tersedia"}, 200
            return {"status": "success", "data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        
@materi_ns.route('/<int:id_materi>/visibility')
class MateriVisibilityResource(Resource):
    @session_required
    @role_required(['admin', 'mentor'])
    @materi_ns.expect(visibility_model)
    def put(self, id_materi):
        """Akses: (admin/mentor), Ubah visibility materi"""
        if not request.is_json:
            return {"status": "error", "message": "Content-Type harus application/json"}, 400
        
        data = request.get_json()
        visibility = data.get("visibility")

        if visibility not in ['open', 'hold', 'close']:
            return {"status": "error", "message": "Visibility tidak valid"}, 400

        # Cek apakah materi tersedia
        existing = get_materi_by_id(id_materi)
        if not existing:
            return {"status": "error", "message": "Materi tidak ditemukan"}, 404

        # Cek jika user adalah mentor, apakah dia punya akses ke materi
        current_user_id = get_jwt_identity()
        current_role = get_jwt()['role']
        if current_role == 'mentor':
            from .query.q_materi import is_mentor_of_materi
            if not is_mentor_of_materi(current_user_id, id_materi):
                return {"status": "error", "message": "Akses ditolak. Materi bukan milik Anda"}, 403

        try:
            result = update_materi_visibility(id_materi, visibility)
            if not result:
                return {"status": "error", "message": "Gagal mengubah visibility"}, 400
            return {
                "status": f"Visibility materi '{result['judul']}' berhasil diubah menjadi {visibility}"
            }, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

