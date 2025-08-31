from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError


from .utils.decorator import role_required, session_required
from .utils.helper import is_valid_date
from .query.q_batch import get_batch_by_id
from .query.q_userbatch import *

userbatch_ns = Namespace("userbatch", description="Manajemen pendaftaran peserta ke batch")

userbatch_model = userbatch_ns.model("UserBatch", {
    "id_user": fields.Integer(required=True, description="ID peserta"),
    "id_batch": fields.Integer(required=True, description="ID batch"),
    "tanggal_join": fields.String(required=True, description="Tanggal join (YYYY-MM-DD HH:MM:SS)")
})

enroll_model = userbatch_ns.model("EnrollBatch", {
    "id_batch": fields.Integer(required=True, description="ID Batch yang akan dienroll")
})


@userbatch_ns.route('')
class UserBatchListResource(Resource):
    @userbatch_ns.param('status_enroll', 'Filter status enroll (pending, approved, rejected)', required=False)
    # @session_required
    @role_required('admin')
    def get(self):
        """Akses: (admin), Ambil semua pendaftaran peserta ke batch (dengan filter status_enroll opsional)"""
        status_enroll = request.args.get('status_enroll')  # bisa 'pending', 'approved', 'rejected'
        
        try:
            result = get_all_userbatch(status_enroll)
            if not result:
                return {"status": "error", "message": "Tidak ada data"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    # @session_required
    @role_required('admin')
    @userbatch_ns.expect(userbatch_model)
    def post(self):
        """Akses: (admin), Tambah peserta ke batch"""
        payload = request.get_json()

        if not is_valid_peserta(payload["id_user"]): # Validasi peserta
            return {"status": "error", "message": "Peserta tidak ditemukan"}, 400
        if not is_valid_batch(payload["id_batch"]): # Validasi batch
            return {"status": "error", "message": "Batch tidak ditemukan"}, 400
        if not is_valid_date(payload.get("tanggal_join", "")): # Validasi format tanggal
            return {"status": "error", "message": "Format tanggal_join tidak valid (YYYY-MM-DD)"}, 400

        try:
            created = insert_userbatch(payload)
            if not created:
                return {"status": "error", "message": "Gagal tambah user ke batch"}, 400
            return {"status": "Pendaftaran berhasil", "data": created}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

@userbatch_ns.route('/<int:id_userbatch>')
class UserBatchDetailResource(Resource):
    # @session_required
    @role_required('admin')
    def get(self, id_userbatch):
        """Akses: (admin), Ambil data pendaftaran berdasarkan ID"""
        try:
            result = get_userbatch_by_id(id_userbatch)
            if not result:
                return {"status": "error", "message": "Data tidak ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    # @session_required
    @role_required('admin')
    @userbatch_ns.expect(userbatch_model, validate=False)
    def put(self, id_userbatch):
        """Akses: (admin), Edit pendaftaran user ke batch"""
        data = request.get_json()
        old = get_userbatch_by_id(id_userbatch)
        if not old:
            return {"status": "error", "message": "Data tidak ditemukan"}, 404

        updated = {
            "id_user": data.get("id_user", old["id_user"]),
            "id_batch": data.get("id_batch", old["id_batch"]),
            "tanggal_join": data.get("tanggal_join", old["tanggal_join"])
        }

        if not is_valid_peserta(updated["id_user"]):
            return {"status": "error", "message": "Peserta tidak valid"}, 400
        if not is_valid_batch(updated["id_batch"]):
            return {"status": "error", "message": "Batch tidak ditemukan"}, 400

        try:
            result = update_userbatch(id_userbatch, updated)
            if not result:
                return {"status": "error", "message": "Gagal update"}, 400
            return {"status": "Pendaftaran berhasil diupdate"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500

    # @session_required
    @role_required('admin')
    def delete(self, id_userbatch):
        """Akses: (admin), Nonaktifkan pendaftaran"""
        try:
            deleted = delete_userbatch(id_userbatch)
            if not deleted:
                return {"status": "error", "message": "Data tidak ditemukan"}, 404
            return {"status": "Pendaftaran berhasil dihapus"}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500
        

"""#=== Peserta ===#"""
@userbatch_ns.route('/<int:id_batch>/peserta')
class PesertaByBatchResource(Resource):
    # @session_required
    @role_required("admin")
    def get(self, id_batch):
        """Akses: (admin) Melihat semua peserta dalam 1 batch"""
        try:
            batch = get_batch_by_id(id_batch)
            peserta = get_peserta_by_batch(id_batch)
            if not peserta:
                return {"status": "error", "peserta": [], "message": "Belum ada peserta di batch ini"}, 200
            return {"status": "success", "batch": batch, "peserta": peserta}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500


@userbatch_ns.route('/enroll')
class EnrollBatchResource(Resource):
    @session_required
    @role_required('peserta')
    @userbatch_ns.expect(enroll_model)
    def post(self):
        """Akses: (peserta), Mendaftar ke batch tertentu"""
        data = request.get_json()
        id_user = get_jwt_identity()
        id_batch = data.get("id_batch")

        try:
            result = insert_userbatch_enroll(id_user, id_batch)
            if "error" in result:
                return {"status": "error", "message": result["error"]}, 400
            return {"status": "success", "message": "Pendaftaran batch berhasil, menunggu persetujuan"}, 201
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500