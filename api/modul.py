from flask import request
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError
from .utils.decorator import role_required
from .query.q_modul import *

modul_ns = Namespace("modul", description="Manajemen Modul dalam Paket Kelas")

modul_model = modul_ns.model("Modul", {
    "id_paketkelas": fields.Integer(required=True, description="ID Paket Kelas"),
    "judul": fields.String(required=True, description="Judul Modul"),
    "deskripsi": fields.String(required=False, description="Deskripsi Modul"),
    "urutan_modul": fields.Integer(required=True, description="Urutan Modul")
})

@modul_ns.route('')
class ModulListResource(Resource):
    @role_required('admin')
    def get(self):
        """Akses: (admin), Ambil semua modul"""
        try:
            result = get_all_modul()
            if not result:
                return {"status": "error", "message": "Tidak ada modul ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    @modul_ns.expect(modul_model)
    def post(self):
        """Akses: (admin), Tambah modul baru"""
        payload = request.get_json()

        if not is_valid_paketkelas(payload["id_paketkelas"]):
            return {"status": "error", "message": "Paket kelas tidak ditemukan"}, 400

        try:
            created = insert_modul(payload)
            if not created:
                return {"status": "error", "message": "Gagal menambahkan modul"}, 400
            return {"status": f"Modul '{created['judul']}' berhasil ditambahkan", "data": created}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

@modul_ns.route('/<int:id_modul>')
class ModulDetailResource(Resource):
    @role_required('admin')
    def get(self, id_modul):
        """Akses: (admin), Ambil data modul berdasarkan ID"""
        try:
            modul = get_modul_by_id(id_modul)
            if not modul:
                return {"status": "error", "message": "Modul tidak ditemukan"}, 404
            return {"data": modul}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    @modul_ns.expect(modul_model, validate=False)
    def put(self, id_modul):
        """Akses: (admin), Ubah data modul"""
        data = request.get_json()
        old = get_modul_by_id(id_modul)
        if not old:
            return {"status": "error", "message": "Modul tidak ditemukan"}, 404

        updated = {
            "id_paketkelas": data.get("id_paketkelas", old["id_paketkelas"]),
            "judul": data.get("judul", old["judul"]),
            "deskripsi": data.get("deskripsi", old["deskripsi"]),
            "urutan_modul": data.get("urutan_modul", old["urutan_modul"])
        }

        if not is_valid_paketkelas(updated["id_paketkelas"]):
            return {"status": "error", "message": "Paket kelas tidak valid"}, 400

        try:
            result = update_modul(id_modul, updated)
            if not result:
                return {"status": "error", "message": "Gagal update modul"}, 400
            return {"status": f"Modul '{result['judul']}' berhasil diupdate"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    def delete(self, id_modul):
        """Akses: (admin), Nonaktifkan modul"""
        try:
            deleted = delete_modul(id_modul)
            if not deleted:
                return {"status": "error", "message": "Modul tidak ditemukan"}, 404
            return {"status": f"Modul '{deleted['judul']}' berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
