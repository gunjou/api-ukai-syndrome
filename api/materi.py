from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError

from .utils.helper import generate_judul
from .utils.decorator import role_required, session_required
from .query.q_materi import *

materi_ns = Namespace("materi", description="Manajemen Materi Modul")

materi_model = materi_ns.model("Materi", {
    "id_modul": fields.Integer(required=True, description="ID Modul"),
    "tipe_materi": fields.String(required=True, description="Jenis materi: video/document"),
    "judul": fields.String(required=True, description="Judul materi"),
    "url_file": fields.String(required=True, description="URL atau file path"),
    "visibility": fields.String(required=False, description="Status visibility (default: hold)"),
})

materi_autogenerate_model = materi_ns.model("MateriAuto", {
    "tanggal": fields.Date(required=True, description="Tanggal materi (format: YYYY-MM-DD)"),
    "id_modul": fields.Integer(required=True, description="ID Modul"),
    "id_owner": fields.Integer(required=True, description="ID Mentor yang memiliki materi ini"),
    "nama_modul": fields.String(required=True, description="Nama Modul"),
    "nickname_mentor": fields.String(required=True, description="Nama Panggilan Mentor"),
    "tipe_materi": fields.String(required=True, description="Jenis materi: video/document"),
    "tipe_video": fields.String(required=False, description="Tipe video: full/part/terjeda"),
    "time": fields.String(required=False, description="Jam untuk tipe_video=terjeda (format HH:MM)"),
    "url_file": fields.String(required=True, description="URL atau file path"),
    "visibility": fields.String(required=False, description="Status visibility (default: hold)"),
})

visibility_model = materi_ns.model("ModulVisibility", {
    "visibility": fields.String(required=True, description="Nilai visibility (open/hold/close)")
})

@materi_ns.route('')
class MateriListResource(Resource):
    # @session_required
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

    # @session_required
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


@materi_ns.route('/autogenerate-title')
class MateriGenerateTitleResource(Resource):
    @role_required('admin')
    @materi_ns.expect(materi_autogenerate_model)
    def post(self):
        """Akses: (admin), Tambah materi baru"""
        payload = request.get_json()

        if not is_valid_modul(payload["id_modul"]):
            return {"status": "error", "message": "Modul tidak ditemukan"}, 400

        try:
            judul = generate_judul(payload)
            data_db = {
                "id_modul": payload["id_modul"],
                "id_owner": payload["id_owner"] if "id_owner" in payload else None,
                "tipe_materi": payload["tipe_materi"],
                "judul": judul,
                "url_file": payload["url_file"],
                "visibility": payload.get("visibility", "hold"),
            }

            created = insert_materi(data_db)

            if not created:
                return {"status": "error", "message": "Gagal menambahkan materi"}, 400
            return {"status": "success", "message": f"Materi '{created['judul']}' berhasil ditambahkan", "data": created}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        

@materi_ns.route('/autogenerate-title/<int:id_materi>')
class MateriGenerateTitleResource(Resource):
    @role_required('admin')
    # @materi_ns.expect(materi_model, validate=False)
    def put(self, id_materi):
        """Akses: (admin), Ubah data materi"""
        data = request.get_json()
        old = get_materi_by_id(id_materi)
        if not old:
            return {"status": "error", "message": "Materi tidak ditemukan"}, 404
        
        updated = {
            "id_modul": data.get("id_modul", old["id_modul"]),
            "id_owner": data.get("id_owner", old["id_owner"]),
            "tipe_materi": data.get("tipe_materi", old["tipe_materi"]),
            "judul": data.get("judul", old["judul"]),
            "url_file": data.get("url_file", old["url_file"]),
            "visibility": data.get("visibility", old["visibility"])
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
        

@materi_ns.route('/<int:id_materi>')
class MateriDetailResource(Resource):
    # @session_required
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

    # @session_required
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
            "visibility": data.get("visibility", old["visibility"])
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

    # @session_required
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
class MateriWebPesertaResource(Resource):
    @session_required
    @jwt_required()
    @role_required('peserta')
    def get(self):
        """Akses: (peserta) Melihat materi yang tersedia untuk peserta"""
        id_user = get_jwt_identity()
        try:
            result = get_materi_by_peserta_web(id_user)
            if not result:
                return {"status": "error", "data": [], "message": "Tidak ada materi yang tersedia"}, 200
            return {"status": "success", "data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        
@materi_ns.route('/web/peserta')
class MateriWebPesertaResource(Resource):
    @session_required
    @jwt_required()
    @role_required('peserta')
    def get(self):
        """Akses: (peserta) endpoint web Melihat materi yang tersedia untuk peserta"""
        id_user = get_jwt_identity()
        try:
            result = get_materi_by_peserta_web(id_user)
            if not result:
                return {"status": "error", "data": [], "message": "Tidak ada materi yang tersedia"}, 200
            return {"status": "success", "data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        
        
@materi_ns.route('/mobile/peserta')
class MateriMobilePesertaResource(Resource):
    @session_required
    @jwt_required()
    @role_required('peserta')
    def get(self):
        """Akses: (peserta) endpoint mobile Melihat materi yang tersedia untuk peserta"""
        id_user = get_jwt_identity()
        try:
            result = get_materi_by_peserta_mobile(id_user)
            if not result:
                return {"status": "error", "data": [], "message": "Tidak ada materi yang tersedia"}, 200
            return {"status": "success", "data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        
@materi_ns.route('/mentor')
class MateriMentorResource(Resource):
    # @session_required
    @jwt_required()
    @role_required('mentor')
    def get(self):
        """Akses: (mentor) Melihat materi yang tersedia untuk mentor"""
        id_user = get_jwt_identity()
        try:
            result = get_materi_by_mentor(id_user)
            if not result:
                return {"status": "error", "data": [], "message": "Tidak ada materi yang tersedia"}, 200
            return {"status": "success", "total": len(result), "data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        
    @role_required('mentor')
    def post(self):
        """Akses: (mentor), Tambah materi ke modul yang diampu"""
        payload = request.get_json()
        id_user = get_jwt_identity()
        payload["id_owner"] = id_user

        # 🔎 Validasi: apakah modul ini milik kelas yang diampu mentor?
        if not is_mentor_of_modul(id_user, payload["id_modul"]):
            return {"status": "error", "message": "Akses ditolak. Modul bukan milik kelas yang Anda ampu."}, 403

        try:
            created = insert_materi(payload)
            if not created:
                return {"status": "error", "message": "Gagal menambahkan materi"}, 400
            return {"status": f"Materi '{created['judul']}' berhasil ditambahkan", "data": created}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        

@materi_ns.route('/mentor/<int:id_paketdata>')
class MateriMentorInKelasResource(Resource):
    # @session_required
    @jwt_required()
    @role_required('mentor')
    def get(self, id_paketdata):
        """Akses: (mentor) Melihat materi yang tersedia untuk mentor"""
        id_user = get_jwt_identity()
        try:
            result = get_materi_by_mentor_and_kelas(id_user, id_paketdata)
            if not result:
                return {"status": "error", "data": [], "message": "Tidak ada materi yang tersedia"}, 200
            return {"status": "success", "total": len(result), "data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        
        
@materi_ns.route('/<int:id_materi>/visibility')
class MateriVisibilityResource(Resource):
    @role_required(['admin', 'mentor'])
    @materi_ns.expect(visibility_model)
    def put(self, id_materi):
        """Akses: (admin/mentor), Ubah visibility materi"""
        data = request.get_json()
        visibility = data.get("visibility")

        # Validasi nilai visibility
        if visibility not in ['open', 'hold', 'close']:
            return {"status": "error", "message": "Visibility tidak valid"}, 400

        # Cek apakah materi tersedia
        existing = get_materi_by_id(id_materi)
        if not existing:
            return {"status": "error", "message": "Materi tidak ditemukan"}, 404

        try:
            result = update_materi_visibility(id_materi, visibility)
            if not result:
                return {"status": "error", "message": "Gagal update visibility"}, 400
            return {
                "status": f"Visibility materi '{result['judul']}' berhasil diubah menjadi {visibility}"
            }, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

