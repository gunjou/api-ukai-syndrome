
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields, reqparse
from .utils.decorator import role_required
from .query.q_kelasprivate import *


kelasprivate_ns = Namespace("kelasprivate", description="Kelas Private / Mentorship")

user_selection_parser = reqparse.RequestParser()
user_selection_parser.add_argument('role', type=str, required=True, choices=('mentor', 'peserta'))
user_selection_parser.add_argument('search', type=str, required=False)

kelasprivate_parser = reqparse.RequestParser()
kelasprivate_parser.add_argument('page', type=int, default=1)
kelasprivate_parser.add_argument('limit', type=int, default=20)
kelasprivate_parser.add_argument('search', type=str, required=False)

create_kelasprivate_parser = reqparse.RequestParser()
create_kelasprivate_parser.add_argument('id_mentor', type=int, required=True)
create_kelasprivate_parser.add_argument('id_peserta', type=int, required=True)
create_kelasprivate_parser.add_argument('nama_mentorship', type=str, required=False)

update_kelasprivate_parser = reqparse.RequestParser()
update_kelasprivate_parser.add_argument('nama_mentorship', type=str, required=False)

materi_private_parser = reqparse.RequestParser()
materi_private_parser.add_argument('tipe_materi', type=str, required=True)
materi_private_parser.add_argument('judul', type=str, required=True)
materi_private_parser.add_argument('url_file', type=str, required=False)
materi_private_parser.add_argument('visibility', type=str, required=False, default='hold')
materi_private_parser.add_argument('is_downloadable', type=int, required=False, default=0)
materi_private_parser.add_argument('viewer_only', type=bool, required=False, default=True)

update_materi_private_parser = reqparse.RequestParser()
update_materi_private_parser.add_argument('judul', type=str, required=False)
update_materi_private_parser.add_argument('tipe_materi', type=str, required=False)
update_materi_private_parser.add_argument('url_file', type=str, required=False)
update_materi_private_parser.add_argument('visibility', type=str, required=False)
update_materi_private_parser.add_argument('is_downloadable', type=int, required=False)
update_materi_private_parser.add_argument('viewer_only', type=bool, required=False)

materi_user_parser = reqparse.RequestParser()
materi_user_parser.add_argument('tipe', type=str, required=False, choices=('video', 'document'))



@kelasprivate_ns.route('/user-selection')
class UserSelectionResource(Resource):

    @kelasprivate_ns.expect(user_selection_parser)
    @jwt_required()
    @role_required('admin')
    def get(self):
        """(admin) Dropdown user (mentor/peserta)"""

        try:
            args = user_selection_parser.parse_args()

            role = args.get("role")
            search = args.get("search")

            data = get_user_selection(role, search)

            if not data:
                return {
                    "status": "success",
                    "data": [],
                    "message": "Tidak ada data ditemukan"
                }, 200

            return {
                "status": "success",
                "data": data,
                "meta": {
                    "total": len(data)
                }
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500



# ======================================================================
# ENDPOINT KELAS PRIVATE (ADMIN)
# ======================================================================
@kelasprivate_ns.route('')
class MentorshipListResource(Resource):

    @kelasprivate_ns.expect(kelasprivate_parser)
    @jwt_required()
    @role_required('admin')
    def get(self):
        """(admin) List semua mentorship (private class)"""

        try:
            args = kelasprivate_parser.parse_args()

            page = args.get("page")
            limit = args.get("limit")
            search = args.get("search")

            result = get_all_mentorship(page, limit, search)

            if not result or not result["data"]:
                return {
                    "status": "error",
                    "message": "Tidak ada mentorship ditemukan"
                }, 404

            return {
                "status": "success",
                "data": result["data"],
                "meta": {
                    "total": result["total"],
                    "page": result["page"],
                    "limit": result["limit"],
                    "total_page": (result["total"] + limit - 1) // limit
                }
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500
            
    
    @kelasprivate_ns.expect(create_kelasprivate_parser)
    @jwt_required()
    @role_required('admin')
    def post(self):
        """(admin) Membuat kelas private (mentorship)"""

        try:
            args = create_kelasprivate_parser.parse_args()

            id_mentor = args.get("id_mentor")
            id_peserta = args.get("id_peserta")
            nama_mentorship = args.get("nama_mentorship")

            result = create_mentorship(id_mentor, id_peserta, nama_mentorship)

            # 🔒 HANDLE ERROR DARI QUERY
            if result is None:
                return {
                    "status": "error",
                    "message": "Gagal membuat mentorship"
                }, 500

            if "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }, 400

            return {
                "status": "success",
                "message": "Mentorship berhasil dibuat",
                "data": result
            }, 201

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500



@kelasprivate_ns.route('/<int:id_mentorship>')
class MentorshipDetailResource(Resource):

    @jwt_required()
    @role_required('admin')
    def get(self, id_mentorship):
        """(admin) Detail mentorship"""

        try:
            result = get_mentorship_by_id(id_mentorship)

            if not result:
                return {
                    "status": "error",
                    "message": "Mentorship tidak ditemukan"
                }, 404

            return {
                "status": "success",
                "data": result
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500


    @kelasprivate_ns.expect(update_kelasprivate_parser)
    @jwt_required()
    @role_required('admin')
    def put(self, id_mentorship):
        """(admin) Update mentorship"""

        try:
            args = update_kelasprivate_parser.parse_args()
            nama_mentorship = args.get("nama_mentorship")

            result = update_mentorship(id_mentorship, nama_mentorship)

            if result is None:
                return {
                    "status": "error",
                    "message": "Gagal update mentorship"
                }, 500

            if "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }, 404

            return {
                "status": "success",
                "message": "Mentorship berhasil diupdate",
                "data": result
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500


    @jwt_required()
    @role_required('admin')
    def delete(self, id_mentorship):
        """(admin) Delete mentorship (soft delete)"""

        try:
            result = delete_mentorship(id_mentorship)

            if result is None:
                return {
                    "status": "error",
                    "message": "Gagal delete mentorship"
                }, 500

            if "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }, 404

            return {
                "status": "success",
                "message": "Mentorship berhasil dihapus",
                "data": result
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500



# ======================================================================
# ENDPOINT MATERI PRIVATE (ADMIN)
# ======================================================================
@kelasprivate_ns.route('/<int:id_mentorship>/materi')
class MateriPrivateResource(Resource):

    @kelasprivate_ns.expect(materi_private_parser)
    @jwt_required()
    @role_required(['admin', 'mentor'])
    def post(self, id_mentorship):
        """(admin/mentor) Tambah materi private"""

        try:
            args = materi_private_parser.parse_args()

            id_owner = int(get_jwt_identity())

            result = create_materi_private(
                id_mentorship=id_mentorship,
                tipe_materi=args.get("tipe_materi"),
                judul=args.get("judul"),
                url_file=args.get("url_file"),
                visibility=args.get("visibility"),
                is_downloadable=args.get("is_downloadable"),
                viewer_only=args.get("viewer_only"),
                id_owner=id_owner
            )

            if result is None:
                return {
                    "status": "error",
                    "message": "Gagal menambahkan materi"
                }, 500

            if "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }, 400

            return {
                "status": "success",
                "message": "Materi berhasil ditambahkan",
                "data": result
            }, 201

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500


    @jwt_required()
    @role_required(['admin', 'mentor', 'peserta'])
    def get(self, id_mentorship):
        """Ambil semua materi berdasarkan mentorship"""

        try:
            result = get_materi_by_mentorship(id_mentorship)

            if not result:
                return {
                    "status": "success",
                    "data": [],
                    "message": "Belum ada materi"
                }, 200

            return {
                "status": "success",
                "data": result
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500


@kelasprivate_ns.route('/materi/<int:id_materi_private>')
class MateriPrivateDetailResource(Resource):

    @jwt_required()
    @role_required(['admin', 'mentor', 'peserta'])
    def get(self, id_materi_private):
        """Ambil detail materi private"""

        try:
            result = get_materi_private_by_id(id_materi_private)

            if not result:
                return {
                    "status": "error",
                    "message": "Materi tidak ditemukan"
                }, 404

            return {
                "status": "success",
                "data": result
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500


    @kelasprivate_ns.expect(update_materi_private_parser)
    @jwt_required()
    @role_required(['admin', 'mentor'])
    def put(self, id_materi_private):
        """Update materi private"""

        try:
            args = update_materi_private_parser.parse_args()

            result = update_materi_private(
                id_materi_private=id_materi_private,
                judul=args.get("judul"),
                tipe_materi=args.get("tipe_materi"),
                url_file=args.get("url_file"),
                visibility=args.get("visibility"),
                is_downloadable=args.get("is_downloadable"),
                viewer_only=args.get("viewer_only")
            )

            if result is None:
                return {
                    "status": "error",
                    "message": "Gagal update materi"
                }, 500

            if "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }, 404

            return {
                "status": "success",
                "message": "Materi berhasil diupdate",
                "data": result
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500


    @jwt_required()
    @role_required(['admin', 'mentor'])
    def delete(self, id_materi_private):
        """Delete materi private (soft delete)"""

        try:
            result = delete_materi_private(id_materi_private)

            if result is None:
                return {
                    "status": "error",
                    "message": "Gagal delete materi"
                }, 500

            if "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }, 404

            return {
                "status": "success",
                "message": "Materi berhasil dihapus",
                "data": result
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500



# ======================================================================
# ENDPOINT MATERI PRIVATE (PESERTA)
# ======================================================================
@kelasprivate_ns.route('/materi-saya')
class MateriPrivateByUserResource(Resource):

    @kelasprivate_ns.expect(materi_user_parser)
    @jwt_required()
    @role_required(['peserta'])
    def get(self):
        """(peserta) Ambil semua materi private milik user"""

        try:
            args = materi_user_parser.parse_args()

            id_user = int(get_jwt_identity())
            tipe = args.get("tipe")

            result = get_materi_private_by_user(id_user, tipe)

            if not result:
                return {
                    "status": "success",
                    "data": [],
                    "message": "Belum ada materi private"
                }, 200

            return {
                "status": "success",
                "data": result,
                "meta": {
                    "total": len(result)
                }
            }, 200

        except Exception as e:
            print(str(e))
            return {
                "status": "error",
                "message": "Internal server error"
            }, 500

