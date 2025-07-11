from flask import request
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError

from .query.q_pesertakelas import *
from .utils.decorator import role_required

pesertakelas_ns = Namespace("pesertakelas", description="Relasi peserta dengan kelas")

pesertakelas_model = pesertakelas_ns.model("PesertaKelas", {
    "id_user": fields.Integer(required=True, description="ID user peserta"),
    "id_paketkelas": fields.Integer(required=True, description="ID paket kelas")
})

@pesertakelas_ns.route('')
class PesertaKelasListResource(Resource):
    @role_required('admin')
    def get(self):
        """Akses: (admin), Mendapatkan semua data peserta-kelas"""
        try:
            result = get_all_pesertakelas()
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    @pesertakelas_ns.expect(pesertakelas_model)
    def post(self):
        """Akses: (admin), Menambahkan peserta ke kelas"""
        data = request.get_json()
        try:
            new_data = insert_pesertakelas(data)
            if not new_data:
                return {"status": "error", "message": "Gagal menambahkan peserta ke kelas"}, 400
            return {"status": "success", "data": new_data}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500


@pesertakelas_ns.route('/<int:id_pesertakelas>')
class PesertaKelasDetailResource(Resource):
    @role_required('admin')
    def get(self, id_pesertakelas):
        """Akses: (admin), Mendapatkan detail peserta-kelas berdasarkan ID"""
        try:
            result = get_pesertakelas_by_id(id_pesertakelas)
            if not result:
                return {"status": "error", "message": "Data tidak ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    @pesertakelas_ns.expect(pesertakelas_model, validate=False)
    def put(self, id_pesertakelas):
        """Akses: (admin), Update data peserta-kelas"""
        data = request.get_json()
        try:
            updated = update_pesertakelas(id_pesertakelas, data)
            if not updated:
                return {"status": "error", "message": "Gagal update"}, 400
            return {"status": f"{updated['id_user']} berhasil diperbarui"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    def delete(self, id_pesertakelas):
        """Akses: (admin), Nonaktifkan peserta-kelas"""
        try:
            deleted = delete_pesertakelas(id_pesertakelas)
            if not deleted:
                return {"status": "error", "message": "Data tidak ditemukan"}, 404
            return {"status": f"{deleted['id_user']} berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
