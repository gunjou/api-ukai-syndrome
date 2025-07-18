from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError
from .query.q_paketkelas import *
from .utils.decorator import role_required

kelas_ns = Namespace("kelas", description="Manajemen paket kelas")

kelas_model = kelas_ns.model("Kelas", {
    "id_batch": fields.Integer(required=True, description="ID batch"),
    "nama_kelas": fields.String(required=True, description="Nama kelas"),
    "deskripsi": fields.String(required=True, description="Deskripsi kelas")
})

@kelas_ns.route('')
class KelasListResource(Resource):
    @jwt_required()
    @role_required(['admin', 'mentor'])
    def get(self):
        """Akses: (admin, mentor), Ambil semua kelas aktif untuk admin, dan yang diampu oleh mentor"""
        try:
            current_user_id = get_jwt_identity()
            role = get_jwt().get('role')

            result = get_kelas_by_role(current_user_id, role)

            if not result:
                return {"status": "error", "message": "Tidak ada kelas ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    @kelas_ns.expect(kelas_model)
    def post(self):
        """Akses: (admin), Tambah kelas baru"""
        payload = request.get_json()

        # Validasi batch
        if not is_batch_exist(payload['id_batch']):
            return {"status": "error", "message": "Batch tidak ditemukan"}, 404

        try:
            created = insert_kelas(payload)
            if not created:
                return {"status": "error", "message": "Gagal menambahkan kelas"}, 400
            return {"status": f"Kelas '{created['nama_kelas']}' berhasil ditambahkan"}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500


@kelas_ns.route('/<int:id_kelas>')
class KelasDetailResource(Resource):
    @role_required('admin')
    def get(self, id_kelas):
        """Akses: (admin), Ambil detail kelas berdasarkan ID"""
        try:
            kelas = get_kelas_by_id(id_kelas)
            if not kelas:
                return {"status": "error", "message": "Kelas tidak ditemukan"}, 404
            return {"data": kelas}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    @kelas_ns.expect(kelas_model, validate=False)
    def put(self, id_kelas):
        """Akses: (admin), Edit data kelas"""
        data = request.get_json()
        old = get_kelas_by_id(id_kelas)
        if not old:
            return {"status": "error", "message": "Kelas tidak ditemukan"}, 404

        # Jika batch diganti, cek juga validitasnya
        if "id_batch" in data and not is_batch_exist(data["id_batch"]):
            return {"status": "error", "message": "Batch tidak valid"}, 404

        updated_payload = {
            "id_batch": data.get("id_batch", old["id_batch"]),
            "nama_kelas": data.get("nama_kelas", old["nama_kelas"]),
            "deskripsi": data.get("deskripsi", old["deskripsi"])
        }

        try:
            updated = update_kelas(id_kelas, updated_payload)
            if not updated:
                return {"status": "error", "message": "Gagal update kelas"}, 400
            return {"status": f"Kelas '{updated['nama_kelas']}' berhasil diperbarui"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    def delete(self, id_kelas):
        """Akses: (admin), Hapus kelas (nonaktifkan)"""
        try:
            deleted = delete_kelas(id_kelas)
            if not deleted:
                return {"status": "error", "message": "Kelas tidak ditemukan"}, 404
            return {"status": f"Kelas '{deleted['nama_kelas']}' berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
