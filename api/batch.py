from flask import request
from flask_restx import Namespace, Resource, fields

from api.query.q_batch import *
from .utils.helper import is_valid_date
from .utils.decorator import role_required


batch_ns = Namespace("batch", description="Manajemen batch")

batch_model = batch_ns.model("Batch", {
    "nama_batch": fields.String(required=True, description="Nama batch"),
    "tanggal_mulai": fields.String(required=True, description="Tanggal mulai (YYYY-MM-DD)"),
    "tanggal_selesai": fields.String(required=True, description="Tanggal selesai (YYYY-MM-DD)")
})

@batch_ns.route("")
class BatchListResource(Resource):
    @role_required('admin')
    def get(self):
        """Akses: (admin), Ambil semua batch aktif"""
        try:
            result = get_all_batch()
            if not result:
                return {"status": "error", "message": "Tidak ada batch ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    @batch_ns.expect(batch_model)
    def post(self):
        """Akses: (admin), Tambah batch baru"""
        payload = request.get_json()
        # Validasi format tanggal
        if not is_valid_date(payload.get("tanggal_mulai", "")):
            return {"status": "error", "message": "Format tanggal_mulai tidak valid (YYYY-MM-DD)"}, 400

        if not is_valid_date(payload.get("tanggal_selesai", "")):
            return {"status": "error", "message": "Format tanggal_selesai tidak valid (YYYY-MM-DD)"}, 400

        try:
            created = insert_batch(payload)
            if not created:
                return {"status": "error", "message": "Gagal menambahkan batch"}, 400
            return {"status": f"Batch '{created['nama_batch']}' berhasil ditambahkan"}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500


@batch_ns.route("/<int:id_batch>")
class BatchDetailResource(Resource):
    @role_required('admin')
    def get(self, id_batch):
        """Akses: (admin), Ambil detail batch berdasarkan ID"""
        try:
            batch = get_batch_by_id(id_batch)
            if not batch:
                return {"status": "error", "message": "Batch tidak ditemukan"}, 404
            return {"data": batch}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    @batch_ns.expect(batch_model, validate=False)
    def put(self, id_batch):
        """Akses: (admin), Update data batch"""
        data = request.get_json()
        old = get_batch_by_id(id_batch)
        if not old:
            return {"status": "error", "message": "Batch tidak ditemukan"}, 404

        updated_payload = {
            "nama_batch": data.get("nama_batch", old["nama_batch"]),
            "tanggal_mulai": data.get("tanggal_mulai", old["tanggal_mulai"]),
            "tanggal_selesai": data.get("tanggal_selesai", old["tanggal_selesai"])
        }

        try:
            updated = update_batch(id_batch, updated_payload)
            if not updated:
                return {"status": "error", "message": "Gagal update batch"}, 400
            return {"status": f"Batch '{updated['nama_batch']}' berhasil diperbarui"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    @role_required('admin')
    def delete(self, id_batch):
        """Akses: (admin), Hapus (nonaktifkan) batch"""
        try:
            deleted = delete_batch(id_batch)
            if not deleted:
                return {"status": "error", "message": "Batch tidak ditemukan"}, 404
            return {"status": f"Batch '{deleted['nama_batch']}' berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500