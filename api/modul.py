from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError
from .utils.decorator import role_required, session_required
from .query.q_modul import *

modul_ns = Namespace("modul", description="Manajemen Modul dalam Paket Kelas")

modul_model = modul_ns.model("Modul", {
    "id_paketkelas": fields.Integer(required=True, description="ID Paket Kelas"),
    "judul": fields.String(required=True, description="Judul Modul"),
    "deskripsi": fields.String(required=False, description="Deskripsi Modul"),
    "urutan_modul": fields.Integer(required=True, description="Urutan Modul")
})

visibility_model = modul_ns.model("ModulVisibility", {
    "visibility": fields.String(required=True, description="Nilai visibility (open/hold/close)")
})

@modul_ns.route('')
class ModulListResource(Resource):
    @session_required
    @role_required(['admin', 'mentor'])
    def get(self):
        """Akses: (admin/mentor), Ambil semua modul"""
        id_user = get_jwt_identity()
        role = get_jwt()['role']
        try:
            if role == 'admin':
                result = get_all_modul_admin()
            else:
                result = get_all_modul_by_mentor(id_user)
            if not result:
                return {"status": "error", "message": "Tidak ada modul ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @session_required
    @role_required(['admin', 'mentor'])
    @modul_ns.expect(modul_model)
    def post(self):
        """Akses: (admin/mentor), Tambah modul (mentor hanya boleh untuk kelas yang diampu)"""
        data = request.get_json()
        id_user = get_jwt_identity()
        role = get_jwt()['role']

        # Validasi paket kelas
        if not is_valid_paketkelas(data.get("id_paketkelas")):
            return {"status": "error", "message": "Paket kelas tidak valid"}, 400

        # Validasi hak akses mentor
        if role == 'mentor' and not is_mentor_of_kelas(id_user, data["id_paketkelas"]):
            return {"status": "error", "message": "Akses ditolak. Anda bukan mentor di kelas ini."}, 403

        payload = {
            "id_paketkelas": data['id_paketkelas'],
            "judul": data['judul'],
            "deskripsi": data['deskripsi'],
            "urutan_modul": data['urutan_modul'],
            "visibility": data.get("visibility", "hold")
        }

        try:
            result = insert_modul(payload)
            if not result:
                return {"status": "error", "message": "Gagal menambahkan modul"}, 400
            return {"status": f"Modul '{result['judul']}' berhasil ditambahkan", "data": result}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

@modul_ns.route('/<int:id_modul>')
class ModulDetailResource(Resource):
    @session_required
    @role_required(['admin', 'mentor'])
    def get(self, id_modul):
        """Akses: (admin/mentor), Ambil data modul berdasarkan ID"""
        try:
            modul = get_modul_by_id(id_modul)
            if not modul:
                return {"status": "error", "message": "Modul tidak ditemukan"}, 404
            return {"data": modul}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @session_required
    @role_required(['admin', 'mentor'])
    @modul_ns.expect(modul_model, validate=False)
    def put(self, id_modul):
        """Akses: (admin/mentor), Edit modul (mentor hanya modul dari kelasnya)"""
        id_user = get_jwt_identity()
        role = get_jwt()['role']
        data = request.get_json()

        old = get_modul_by_id(id_modul)
        if not old:
            return {"status": "error", "message": "Modul tidak ditemukan"}, 404

        # Validasi akses mentor
        if role == 'mentor' and not is_mentor_of_kelas(id_user, old["id_paketkelas"]):
            return {"status": "error", "message": "Anda tidak punya akses ke modul ini"}, 403

        updated = {
            "id_paketkelas": data.get("id_paketkelas", old["id_paketkelas"]),
            "judul": data.get("judul", old["judul"]),
            "deskripsi": data.get("deskripsi", old["deskripsi"]),
            "urutan_modul": data.get("urutan_modul", old["urutan_modul"]),
        }

        # Validasi id_paketkelas
        if not is_valid_paketkelas(updated["id_paketkelas"]):
            return {"status": "error", "message": "Paket kelas tidak valid"}, 400

        try:
            result = update_modul(id_modul, updated)
            if not result:
                return {"status": "error", "message": "Gagal update modul"}, 400
            return {"status": f"Modul '{result['judul']}' berhasil diupdate"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @session_required
    @role_required(['admin', 'mentor'])
    def delete(self, id_modul):
        """Akses: (admin/mentor), Hapus modul (mentor hanya kelasnya sendiri)"""
        id_user = get_jwt_identity()
        role = get_jwt()['role']

        modul = get_modul_by_id(id_modul)
        if not modul:
            return {"status": "error", "message": "Modul tidak ditemukan"}, 404

        if role == 'mentor' and not is_mentor_of_kelas(id_user, modul["id_paketkelas"]):
            return {"status": "error", "message": "Anda tidak punya akses menghapus modul ini"}, 403

        try:
            result = delete_modul(id_modul)
            if not result:
                return {"status": "error", "message": "Gagal menghapus modul"}, 400
            return {"status": f"Modul '{result['judul']}' berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500


"""#=== Endpoint tambahan ===#"""
@modul_ns.route('/user')
class ModulByUserResource(Resource):
    # @jwt_required()
    @session_required
    @role_required('peserta')
    def get(self):
        """Akses: (peserta), Melihat list modul dari kelas yang diikuti/diampu"""
        id_user = get_jwt_identity()
        role = get_jwt().get("role")

        try:
            result = get_modul_by_user(id_user, role)
            return {"status": "success", "data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        

@modul_ns.route('/<int:id_modul>/visibility')
class ModulVisibilityResource(Resource):
    @session_required
    @role_required(['admin', 'mentor'])
    @modul_ns.expect(visibility_model)
    def put(self, id_modul):
        """Akses: (admin/mentor), Ubah visibility modul"""
        data = request.get_json()
        visibility = data.get("visibility")

        if visibility not in ['open', 'hold', 'close']:
            return {"status": "error", "message": "Visibility tidak valid"}, 400

        if not get_modul_by_id(id_modul):
            return {"status": "error", "message": "Modul tidak ditemukan"}, 404

        try:
            result = update_modul_visibility(id_modul, visibility)
            if not result:
                return {"status": "error", "message": "Gagal update visibility"}, 400
            return {"status": f"Visibility modul '{result['judul']}' berhasil diubah menjadi {visibility}"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

