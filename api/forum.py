from flask import logging, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError

from .query.q_forum import *
from .utils.decorator import role_required, session_required


forum_ns = Namespace('forum', description='Endpoint untuk forum diskusi mahasiswa dan mentor')

thread_create_model = forum_ns.model('ThreadCreate', {
    'judul': fields.String(required=True, description='Judul thread'),
    'isi': fields.String(required=True, description='Isi atau konten utama thread'),
    'id_materi': fields.Integer(required=False, description='ID materi (opsional)'),
    'id_paketkelas': fields.Integer(required=False, description='ID paket kelas (opsional)'),
    'id_batch': fields.Integer(required=False, description='ID batch (opsional)')
})

thread_update_model = forum_ns.model('ThreadUpdate', {
    'judul': fields.String(required=False, allow_none=True, description='Judul thread baru (boleh null)'),
    'isi': fields.String(required=False, allow_none=True, description='Isi thread baru (boleh null)'),
})

comment_model = forum_ns.model('CommentCreate', {
    'isi': fields.String(required=True, description='Isi komentar'),
    'parent_id': fields.Integer(required=False, description='ID komentar induk (jika reply)')
})

comment_update_model = forum_ns.model('CommentUpdate', {
    'isi': fields.String(required=False, description='Isi komentar yang diperbarui (opsional)')
})


""" #=== Endpoint Thread ===# """

@forum_ns.route('/thread')
class ForumThreadListResource(Resource):
    # @role_required(['mentor', 'peserta'])
    @jwt_required()
    def get(self):
        """
        Akses: (mahasiswa, mentor, admin)
        Mengambil daftar thread forum (filter berdasarkan batch, materi, atau search keyword)
        """
        try:
            result = get_all_forum_thread()
            if not result:
                return {'status': 'error', 'message': 'Belum ada thread yang ditemukan'}, 404
            return {'status': 'success', 'data': result}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        
    @forum_ns.expect(thread_create_model, validate=True)
    @jwt_required()
    def post(self):
        """
        Akses: (mahasiswa, mentor, admin)
        Membuat thread baru di forum
        """
        try:
            data = request.get_json()
            id_user = get_jwt_identity()  # dari JWT token login

            result = create_forum_thread(
                id_user=id_user,
                judul=data.get('judul'),
                isi=data.get('isi'),
                id_materi=data.get('id_materi'),
                id_paketkelas=data.get('id_paketkelas'),
                id_batch=data.get('id_batch')
            )

            if result:
                return {'status': 'success', 'message': 'Thread berhasil dibuat', 'data': result}, 201
            else:
                return {'status': 'error', 'message': 'Gagal membuat thread'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500


@forum_ns.route('/thread/<int:id_thread>')
class ForumThreadDetailResource(Resource):
    @jwt_required()
    def get(self, id_thread):
        """
        Akses: (mahasiswa, mentor, admin)
        Mengambil detail thread beserta komentar (nested)
        """
        try:
            result = get_forum_thread_detail(id_thread)
            if not result:
                return {'status': 'error', 'message': 'Thread tidak ditemukan'}, 404
            return {'status': 'success', 'data': result}, 200
        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500

    @forum_ns.doc(
        description="Edit thread forum (gunakan 'null' untuk mempertahankan data lama)"
    )
    @forum_ns.param('judul', 'Judul thread baru (opsional)', 'formData', type='string', required=False)
    @forum_ns.param('isi', 'Isi thread baru (opsional)', 'formData', type='string', required=False)
    @jwt_required()
    def put(self, id_thread):
        """
        Akses: (pemilik thread atau admin)
        Edit thread forum
        Params (query/form):
        - judul (opsional, boleh kosong/null)
        - isi (opsional, boleh kosong/null)
        Jika dikosongkan → data lama akan dipertahankan
        """
        try:
            id_user = get_jwt_identity()

            # Ambil parameter dari query atau form
            judul = request.args.get('judul') or request.form.get('judul')
            isi = request.args.get('isi') or request.form.get('isi')

            # Konversi 'null' string → None
            if judul == 'null':
                judul = None
            if isi == 'null':
                isi = None

            result = update_forum_thread(
                id_thread=id_thread,
                id_user=id_user,
                judul=judul,
                isi=isi
            )

            if result == 'not_found':
                return {'status': 'error', 'message': 'Thread tidak ditemukan'}, 404
            elif result == 'forbidden':
                return {'status': 'error', 'message': 'Anda tidak memiliki izin untuk mengedit thread ini'}, 403
            elif result == 'no_changes':
                return {'status': 'warning', 'message': 'Tidak ada perubahan pada thread'}, 200
            elif result:
                return {'status': 'success', 'message': 'Thread berhasil diperbarui', 'data': result}, 200
            else:
                return {'status': 'error', 'message': 'Gagal memperbarui thread'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        
    @forum_ns.doc(description="Hapus thread (soft delete) - hanya pemilik atau admin")
    @jwt_required()
    def delete(self, id_thread):
        """
        Akses: (pemilik thread atau admin)
        Menghapus thread (soft delete)
        """
        try:
            id_user = get_jwt_identity()

            result = delete_forum_thread(id_thread=id_thread, id_user=id_user)

            if result == 'not_found':
                return {'status': 'error', 'message': 'Thread tidak ditemukan'}, 404
            elif result == 'forbidden':
                return {'status': 'error', 'message': 'Anda tidak memiliki izin untuk menghapus thread ini'}, 403
            elif result:
                return {'status': 'success', 'message': 'Thread berhasil dihapus'}, 200
            else:
                return {'status': 'error', 'message': 'Gagal menghapus thread'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500



""" #=== Endpoint Comment ===# """

@forum_ns.route('/thread/<int:id_thread>/comment')
class ForumCommentResource(Resource):
    @forum_ns.doc(description="Tambah komentar baru atau reply pada thread")
    @forum_ns.expect(comment_model)
    @jwt_required()
    def post(self, id_thread):
        """
        Akses: (mahasiswa, mentor, admin)
        Tambah komentar baru atau reply ke thread
        Body:
        - isi (string)
        - parent_id (optional)
        """
        try:
            id_user = get_jwt_identity()
            data = request.get_json()

            isi = data.get('isi')
            parent_id = data.get('parent_id')

            if not isi:
                return {'status': 'error', 'message': 'Isi komentar wajib diisi'}, 400

            result = create_forum_comment( id_user, id_thread, isi, parent_id)

            if result == 'not_found':
                return {'status': 'error', 'message': 'Thread tidak ditemukan'}, 404
            elif result:
                return {'status': 'success', 'message': 'Komentar berhasil ditambahkan', 'data': result}, 201
            else:
                return {'status': 'error', 'message': 'Gagal menambahkan komentar'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        
    @forum_ns.doc(description="Ambil semua komentar (nested) dari sebuah thread")
    @jwt_required()
    def get(self, id_thread):
        """
        Akses: (mahasiswa, mentor, admin)
        Ambil semua komentar dari thread (nested / hierarki reply)
        """
        try:
            result = get_thread_comments(id_thread)

            if result == 'not_found':
                return {'status': 'error', 'message': 'Thread tidak ditemukan'}, 404
            elif result == []:
                return {'status': 'success', 'message': 'Belum ada komentar di thread ini', 'data': []}, 200
            else:
                return {'status': 'success', 'data': result}, 200

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        
        
@forum_ns.route('/comment/<int:id_comment>')
class ForumCommentUpdateResource(Resource):
    @forum_ns.expect(comment_update_model, validate=False)
    @jwt_required()
    def put(self, id_comment):
        """
        Akses: (pemilik komentar atau admin)
        Edit komentar forum
        Body:
        - isi (opsional, jika kosong maka tidak akan diubah)
        """
        try:
            id_user = get_jwt_identity()
            data = request.get_json() or {}

            isi = data.get('isi')

            result = update_forum_comment(
                id_comment=id_comment,
                id_user=id_user,
                isi=isi
            )

            if result == 'not_found':
                return {'status': 'error', 'message': 'Komentar tidak ditemukan'}, 404
            elif result == 'forbidden':
                return {'status': 'error', 'message': 'Anda tidak memiliki izin untuk mengedit komentar ini'}, 403
            elif result == 'empty_fields':
                return {'status': 'error', 'message': 'Tidak ada perubahan yang dilakukan'}, 400
            elif result:
                return {'status': 'success', 'message': 'Komentar berhasil diperbarui', 'data': result}, 200
            else:
                return {'status': 'error', 'message': 'Gagal memperbarui komentar'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        
    @jwt_required()
    def delete(self, id_comment):
        """
        Akses: (pemilik komentar, mentor materi terkait, atau admin)
        Soft delete komentar forum.
        - Jika dihapus oleh mentor → tandai deleted_by_mentor = TRUE
        - Jika oleh pemilik atau admin → hanya is_deleted = TRUE
        """
        try:
            id_user = get_jwt_identity()

            result = soft_delete_forum_comment(
                id_comment=id_comment,
                id_user=id_user
            )

            if result == 'not_found':
                return {'status': 'error', 'message': 'Komentar tidak ditemukan'}, 404
            elif result == 'forbidden':
                return {'status': 'error', 'message': 'Anda tidak memiliki izin untuk menghapus komentar ini'}, 403
            elif result:
                return {'status': 'success', 'message': 'Komentar berhasil dihapus (soft delete)'}, 200
            else:
                return {'status': 'error', 'message': 'Gagal menghapus komentar'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500


""" #=== Endpoint Vote ===# """

@forum_ns.route('/comment/<int:id_comment>/vote')
class ForumCommentVoteResource(Resource):
    @jwt_required()
    @forum_ns.param('vote_type', '1 untuk upvote, -1 untuk downvote', type=int, enum=[1, -1])
    def post(self, id_comment):
        """
        Tambah / ubah vote pada komentar.
        Jika user sudah vote sebelumnya:
        - Jika nilai sama → tidak ada perubahan
        - Jika nilai berbeda → update vote
        """
        try:
            id_user = get_jwt_identity()
            vote_type = request.args.get('vote_type', type=int)

            if vote_type not in [1, -1]:
                return {'status': 'error', 'message': 'vote_type harus 1 (upvote) atau -1 (downvote)'}, 400

            result = add_or_update_vote(id_comment, id_user, vote_type)

            if result == 'not_found':
                return {'status': 'error', 'message': 'Komentar tidak ditemukan atau sudah dihapus'}, 404
            elif result == 'no_change':
                return {'status': 'success', 'message': 'Vote tidak berubah (sudah sama sebelumnya)'}, 200
            elif result:
                return {'status': 'success', 'message': 'Vote berhasil disimpan'}, 200
            else:
                return {'status': 'error', 'message': 'Gagal menyimpan vote'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500

    @jwt_required()
    def delete(self, id_comment):
        """
        Hapus vote user pada komentar.
        """
        try:
            id_user = get_jwt_identity()
            result = delete_vote(id_comment, id_user)

            if result == 'not_found':
                return {'status': 'error', 'message': 'Vote tidak ditemukan'}, 404
            elif result:
                return {'status': 'success', 'message': 'Vote berhasil dihapus'}, 200
            else:
                return {'status': 'error', 'message': 'Gagal menghapus vote'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500



""" #=== Endpoint Solved ===# """

@forum_ns.route('/comment/<int:id_comment>/mark-solved')
class ForumMarkSolvedResource(Resource):
    @jwt_required()
    def post(self, id_comment):
        """
        Tandai komentar sebagai solusi.
        Akses: hanya pembuat thread.
        """
        try:
            id_user = get_jwt_identity()
            result = mark_comment_as_solved(id_comment, id_user)

            if result == 'not_found':
                return {'status': 'error', 'message': 'Komentar tidak ditemukan'}, 404
            elif result == 'forbidden':
                return {'status': 'error', 'message': 'Hanya pembuat thread yang dapat menandai solusi'}, 403
            elif result == 'already_solved':
                return {'status': 'error', 'message': 'Thread ini sudah memiliki komentar bertanda solusi'}, 400
            elif result:
                return {'status': 'success', 'message': 'Komentar berhasil ditandai sebagai solusi'}, 200
            else:
                return {'status': 'error', 'message': 'Gagal menandai komentar sebagai solusi'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500


    @jwt_required()
    def delete(self, id_comment):
        """
        Batalkan tanda solusi pada komentar.
        Akses: hanya pembuat thread.
        """
        try:
            id_user = get_jwt_identity()
            result = unmark_comment_as_solved(id_comment, id_user)

            if result == 'not_found':
                return {'status': 'error', 'message': 'Komentar tidak ditemukan'}, 404
            elif result == 'forbidden':
                return {'status': 'error', 'message': 'Hanya pembuat thread yang dapat membatalkan tanda solusi'}, 403
            elif result:
                return {'status': 'success', 'message': 'Tanda solusi berhasil dibatalkan'}, 200
            else:
                return {'status': 'error', 'message': 'Gagal membatalkan tanda solusi'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500


""" #=== Endpoint Notification ===# """

@forum_ns.route('/notifications')
class ForumNotificationsResource(Resource):
    @jwt_required()
    def get(self):
        """
        Ambil daftar notifikasi user.
        """
        try:
            id_user = get_jwt_identity()
            data = get_forum_notifications(id_user)

            return {'status': 'success', 'data': data}, 200

        except SQLAlchemyError as e:
            logging.error(f"Database error (notifications): {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error (notifications): {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500


@forum_ns.route('/notifications/<int:id_notification>/read')
class ForumNotificationReadResource(Resource):
    @jwt_required()
    def put(self, id_notification):
        """
        Tandai notifikasi sebagai dibaca.
        """
        try:
            id_user = get_jwt_identity()
            result = mark_forum_notification_as_read(id_notification, id_user)

            if result == 'not_found':
                return {'status': 'error', 'message': 'Notifikasi tidak ditemukan'}, 404
            elif result == 'forbidden':
                return {'status': 'error', 'message': 'Anda tidak memiliki akses ke notifikasi ini'}, 403
            elif result:
                return {'status': 'success', 'message': 'Notifikasi berhasil ditandai sebagai dibaca'}, 200
            else:
                return {'status': 'error', 'message': 'Gagal menandai notifikasi'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error (mark read): {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error (mark read): {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500


@forum_ns.route('/notifications/<int:id_notification>')
class ForumNotificationDeleteResource(Resource):
    @jwt_required()
    def delete(self, id_notification):
        """
        Hapus notifikasi user.
        """
        try:
            id_user = get_jwt_identity()
            result = delete_forum_notification(id_notification, id_user)

            if result == 'not_found':
                return {'status': 'error', 'message': 'Notifikasi tidak ditemukan'}, 404
            elif result == 'forbidden':
                return {'status': 'error', 'message': 'Anda tidak memiliki akses ke notifikasi ini'}, 403
            elif result:
                return {'status': 'success', 'message': 'Notifikasi berhasil dihapus'}, 200
            else:
                return {'status': 'error', 'message': 'Gagal menghapus notifikasi'}, 500

        except SQLAlchemyError as e:
            logging.error(f"Database error (delete notification): {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
        except Exception as e:
            logging.error(f"Unexpected error (delete notification): {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}, 500
