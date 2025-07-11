from flask import request
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError
from .utils.decorator import role_required
from .query.q_materi import *

materi_ns = Namespace("materi", description="Manajemen Materi Modul")

materi_model = materi_ns.model("Materi", {
    "id_modul": fields.Integer(required=True, description="ID Modul"),
    "tipe_materi": fields.String(required=True, description="Jenis materi: video/pdf/file"),
    "judul": fields.String(required=True, description="Judul materi"),
    "url_file": fields.String(required=True, description="URL atau file path"),
    "viewer_only": fields.Boolean(required=True, description="Hanya bisa dilihat, tidak bisa diunduh")
})

@materi_ns.route('')
class MateriListResource(Resource):
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
