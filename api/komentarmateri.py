from datetime import timedelta
from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError

from .utils.decorator import role_required, session_required
from .query.q_materi import is_user_have_access_to_materi
from .query.q_komentarmateri import *


komentarmateri_ns = Namespace("komentar", description="Manajemen Komentar tiap materi")

komentar_post_parser = komentarmateri_ns.parser()
komentar_post_parser.add_argument("isi_komentar", type=str, required=True, help="Isi komentar")
komentar_post_parser.add_argument("parent_id", type=int, required=False, help="ID komentar induk jika reply")

edit_komentar_model = komentarmateri_ns.model('EditKomentarInput', {
    'isi_komentar': fields.String(required=True, description='Isi komentar yang diperbarui', help="Isi komentar baru"),
})

@komentarmateri_ns.route('/<int:id_materi>/komentar')
class KomentarMateriResource(Resource):
    @session_required
    @jwt_required()
    @role_required(['mentor', 'peserta'])
    def get(self, id_materi):
        """Akses: (mentor/peserta), Ambil komentar materi sesuai hak akses kelas"""
        current_user_id = get_jwt_identity()
        current_role = get_jwt()['role']

        if not is_user_have_access_to_materi(current_user_id, id_materi, current_role):
            return {"status": "error", "message": "Akses ditolak."}, 403

        komentar = get_komentar_by_materi(id_materi)
        return {"status": "success", "total": len(komentar), "data": komentar}, 200

    @komentarmateri_ns.expect(komentar_post_parser)
    @session_required
    @jwt_required()
    @role_required(['mentor', 'peserta'])
    def post(self, id_materi):
        """Akses: (mentor/peserta), Tambah komentar baru atau balasan komentar"""
        args = komentar_post_parser.parse_args()
        isi_komentar = args.get("isi_komentar")
        parent_id = args.get("parent_id")
        current_user_id = get_jwt_identity()
        current_role = get_jwt()['role']

        if not is_user_have_access_to_materi(current_user_id, id_materi, current_role):
            return {"status": "error", "message": "Akses ditolak."}, 403
        if parent_id and not is_valid_parent_komentar(id_materi, parent_id):
            return {"status": "error", "message": "Komentar induk tidak valid"}, 400

        id_komentar = insert_komentar_materi(id_materi, current_user_id, isi_komentar, parent_id)
        if id_komentar:
            return {"status": "success", "message": "Komentar berhasil ditambahkan", "id_komentarmateri": id_komentar}, 201
        else:
            return {"status": "error", "message": "Gagal menambahkan komentar"}, 500


@komentarmateri_ns.route('/<int:id_materi>/komentar/<int:id_komentarmateri>')
class EditKomentarMateriResource(Resource):
    @session_required
    @jwt_required()
    @role_required(['mentor', 'peserta'])
    @komentarmateri_ns.expect(edit_komentar_model)
    def put(self, id_materi, id_komentarmateri):
        """Akses: (mentor/peserta), Edit komentar milik sendiri (maks 5 menit setelah update)"""
        current_user_id = get_jwt_identity()
        print(current_user_id)
        current_role = get_jwt()['role']

        # Validasi akses ke materi
        if not is_user_have_access_to_materi(current_user_id, id_materi, current_role):
            return {"status": "error", "message": "Akses ditolak ke materi ini."}, 403

        # Ambil data komentar
        komentar = get_komentar_by_id(id_komentarmateri)
        if not komentar:
            return {"status": "error", "message": "Komentar tidak ditemukan."}, 404

        # Validasi hanya pemilik yang bisa edit
        if int(komentar['id_user']) != int(current_user_id):
            return {"status": "error", "message": "Anda tidak memiliki izin untuk mengedit komentar ini."}, 403

        # Validasi durasi maksimal edit 5 menit
        last_updated = komentar['updated_at']
        now = get_wita()
        if now - last_updated > timedelta(minutes=5):
            return {"status": "error", "message": "Komentar hanya bisa diedit dalam waktu 5 menit."}, 400

        # Ambil isi baru
        data = request.get_json()
        new_content = data.get('isi_komentar')
        if not new_content:
            return {"status": "error", "message": "Isi komentar tidak boleh kosong."}, 400

        # Update komentar
        success = update_komentar(id_komentarmateri, new_content)
        if not success:
            return {"status": "error", "message": "Gagal memperbarui komentar."}, 500

        return {"status": "success", "message": "Komentar berhasil diperbarui."}, 200
    
@komentarmateri_ns.route('/<int:id_komentarmateri>')
class HapusKomentarMateriResource(Resource):
    @jwt_required()
    def delete(self, id_komentarmateri):
        """Hapus komentar materi (soft-delete).
        - Peserta: hanya bisa hapus komentar sendiri.
        - Mentor: bisa hapus semua komentar.
        """
        current_user_id = get_jwt_identity()
        current_role = get_jwt().get('role')

        result = soft_delete_komentar_materi(
            id_komentarmateri=id_komentarmateri,
            id_user=current_user_id,
            role=current_role
        )

        if not result['status']:
            return {"message": result['msg']}, 403
        return {"message": result['msg']}, 200
