from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError
from .utils.decorator import role_required, session_required
from .query.q_modul import *

modul_ns = Namespace("modul", description="Manajemen Modul dalam Paket Kelas")

modul_model = modul_ns.model("Modul", {
    "judul": fields.String(required=True, description="Judul Modul"),
    "deskripsi": fields.String(required=False, description="Deskripsi Modul"),
    "visibility": fields.String(required=False, description="Nilai visibility (open/hold/close)")
})

mentor_modul_model = modul_ns.model("MentorModul", {
    "judul": fields.String(required=True, description="Judul Modul"),
    "deskripsi": fields.String(required=False, description="Deskripsi Modul"),
    "visibility": fields.String(required=False, description="Nilai visibility (open/hold/close)")
})


visibility_model = modul_ns.model("ModulVisibility", {
    "visibility": fields.String(required=True, description="Nilai visibility (open/hold/close)")
})

@modul_ns.route('')
class ModulListResource(Resource):
    # @session_required
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


    # @session_required
    @role_required('admin')
    @modul_ns.expect(modul_model)
    def post(self):
        """Akses: (admin), Tambah modul untuk admin"""
        data = request.get_json()
        role = get_jwt()['role']

        payload = {
            "judul": data['judul'],
            "deskripsi": data.get('deskripsi'),
            "owner": 'admin' if role == 'admin' else 'mentor',
            "visibility": data.get("visibility", "hold")
        }

        try:
            result = insert_modul(payload)
            if not result:
                return {"status": "error", "message": "Gagal menambahkan modul"}, 400
            return {
                "status": f"Modul '{result['judul']}' berhasil ditambahkan",
                "data": result
            }, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

        

@modul_ns.route('/mentor')
class MentorModulResource(Resource):
    @role_required(['mentor'])
    @modul_ns.expect(mentor_modul_model)
    def post(self):
        """Akses: mentor, Tambah modul (otomatis assign ke semua kelas yang diampu)"""
        data = request.get_json()
        id_user = get_jwt_identity()

        payload = {
            "judul": data['judul'],
            "deskripsi": data.get('deskripsi'),
            "owner": 'mentor',
            "visibility": data.get("visibility", "hold")
        }

        try:
            result = insert_modul_for_mentor(payload, id_user)
            if not result:
                return {"status": "error", "message": "Gagal menambahkan modul"}, 400
            return {
                "status": f"Modul '{result['judul']}' berhasil ditambahkan dan di-assign ke semua kelas mentor",
                "data": result
            }, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500


@modul_ns.route('/kelas-tersedia/<int:id_modul>')
class ModulListAllKelasResource(Resource):
    # @session_required
    @jwt_required()
    @role_required('admin')
    def get(self, id_modul):
        """Akses: (admin), Ambil semua kelas yang terdaftar di modul"""
        try:
            # current_user_id = get_jwt_identity()

            result = get_all_kelas_by_modul(id_modul)

            if not result:
                return {"status": "error", "message": "Tidak ada kelas ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        

@modul_ns.route('/list-kelas/<int:id_modul>')
class ModulListKelasResource(Resource):
    # @session_required
    @jwt_required()
    @role_required('admin')
    def get(self, id_modul):
        """Akses: (admin), Ambil semua kelas yang terdaftar di modul"""
        try:
            # current_user_id = get_jwt_identity()

            result = get_kelas_by_modul(id_modul)

            if not result:
                return {"status": "error", "message": "Tidak ada kelas ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        

@modul_ns.route('/kelas/<int:id_modulkelas>')
class DeleteKelasResource(Resource):
    @jwt_required()
    @role_required('admin')
    def delete(self, id_modulkelas):
        """Akses: (admin), Delete kelas yang terdaftar di modul"""
        try:
            success = delete_kelas_in_modul(id_modulkelas)
            if not success:
                return {"status": "error", "message": "Gagal menghapus kelas"}, 400
            return {"status": "Kelas untuk modul ini berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500


@modul_ns.route('/assign-kelas/<int:id_modul>')
class AssignKelasResource(Resource):
    @jwt_required()
    @role_required('admin')  # bisa kamu ubah sesuai kebutuhan
    def post(self, id_modul):
        """
        Akses: admin, Assign satu atau banyak kelas ke modul.
        Body: { "id_paketkelas": [11,12,15,...] }
        """
        data = request.get_json()
        id_paketkelas_list = data.get("id_paketkelas", [])

        if not isinstance(id_paketkelas_list, list) or not id_paketkelas_list:
            return {"status": "error", "message": "id_paketkelas harus berupa array dan tidak boleh kosong"}, 400

        try:
            inserted_count = assign_kelas_to_modul(id_modul, id_paketkelas_list)
            if inserted_count == 0:
                return {"status": "error", "message": "Tidak ada kelas yang berhasil diassign"}, 400

            return {
                "status": f"{inserted_count} kelas berhasil diassign ke modul {id_modul}"
            }, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500


@modul_ns.route('/<int:id_modul>')
class ModulDetailResource(Resource):
    # @session_required
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

    # @session_required
    @role_required(['admin', 'mentor'])
    @modul_ns.expect(modul_model, validate=False)
    def put(self, id_modul):
        """Akses: (admin/mentor), Edit modul"""
        id_user = get_jwt_identity()
        role = get_jwt()['role']
        data = request.get_json()

        old = get_old_modul_by_id(id_modul)
        if not old:
            return {"status": "error", "message": "Modul tidak ditemukan"}, 404

        # ⚠️ Validasi akses mentor
        if role == 'mentor' and not is_mentor_of_modul(id_user, id_modul):
            return {"status": "error", "message": "Anda tidak punya akses ke modul ini"}, 403

        updated = {
            "judul": data.get("judul", old["judul"]),
            "deskripsi": data.get("deskripsi", old["deskripsi"]),
            "visibility": data.get("visibility", old["visibility"])
        }

        try:
            result = update_modul(id_modul, updated)
            if not result:
                return {"status": "error", "message": "Gagal update modul"}, 400
            return {
                "status": f"Modul '{result['judul']}' berhasil diupdate",
                "data": result
            }, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    # @session_required
    @role_required(['admin', 'mentor'])
    def delete(self, id_modul):
        """Akses: (admin/mentor), Hapus modul (mentor hanya kelasnya sendiri)"""
        id_user = get_jwt_identity()
        role = get_jwt()['role']

        try:
            if role == 'mentor':
                modul = get_modul_by_id(id_modul)
                if not modul:
                    return {"status": "error", "message": "Modul tidak ditemukan"}, 404

                if not is_mentor_of_kelas(id_user, modul["id_paketkelas"]):
                    return {"status": "error", "message": "Anda tidak punya akses menghapus modul ini"}, 403

                result = delete_modul(id_modul)
                if not result:
                    return {"status": "error", "message": "Gagal menghapus modul"}, 400
                return {"status": f"Modul '{result['judul']}' berhasil dihapus"}, 200
            else:
                result = delete_modul(id_modul)
                if not result:
                    return {"status": "error", "message": "Gagal menghapus modul"}, 400
                return {"status": f"Modul '{result['judul']}' berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500


"""#=== Endpoint tambahan ===#"""
@modul_ns.route('/user')
class ModulByUserResource(Resource):
    @session_required
    @role_required(['mentor', 'peserta'])
    def get(self):
        """Akses: (mentor/peserta), Melihat list modul dari kelas yang diampu/diikuti"""
        id_user = get_jwt_identity()
        role = get_jwt().get("role")

        try:
            result = get_all_modul_by_user(id_user, role)
            return {"status": "success", "data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        

@modul_ns.route('/<int:id_modul>/visibility')
class ModulVisibilityResource(Resource):
    # @session_required
    @role_required(['admin', 'mentor'])
    @modul_ns.expect(visibility_model)
    def put(self, id_modul):
        """Akses: (admin/mentor), Ubah visibility modul"""
        data = request.get_json()
        visibility = data.get("visibility")

        if visibility not in ['open', 'hold', 'close']:
            return {"status": "error", "message": "Visibility tidak valid"}, 400

        if not get_old_modul_by_id(id_modul):
            return {"status": "error", "message": "Modul tidak ditemukan"}, 404

        try:
            result = update_modul_visibility(id_modul, visibility)
            if not result:
                return {"status": "error", "message": "Gagal update visibility"}, 400
            return {"status": f"Visibility modul '{result['judul']}' berhasil diubah menjadi {visibility}"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

