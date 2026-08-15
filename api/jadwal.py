from flask import request
from flask_jwt_extended import get_jwt_identity, get_jwt
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError

from .utils.decorator import role_required
from .query.q_jadwal import *


jadwal_ns = Namespace("jadwal", description="Manajemen Jadwal Kelas")


# ============================================================================ #
#                                #ANCHOR - MODEL                               #
# ============================================================================ #

jadwal_model = jadwal_ns.model("Jadwal", {
    "id_paketkelas": fields.Integer(required=True, description="ID paket kelas"),
    "id_mentor": fields.Integer(required=True, description="ID mentor"),
    "tanggal": fields.Date(required=True, description="Tanggal jadwal"),
    "waktu_mulai": fields.String(required=True, description="Waktu mulai, format HH:MM"),
    "waktu_selesai": fields.String(required=True, description="Waktu selesai, format HH:MM"),
    "type_pertemuan": fields.String(required=True, description="Tipe pertemuan (ONLINE/OFFLINE)")
})


reschedule_model = jadwal_ns.model("JadwalReschedule", {
    "tanggal_reschedule": fields.Date(required=True, description="Tanggal reschedule"),
    "waktu_mulai_reschedule": fields.String(required=True, description="Waktu mulai reschedule, format HH:MM"),
    "waktu_selesai_reschedule": fields.String(required=True, description="Waktu selesai reschedule, format HH:MM")
})



# ============================================================================ #
#                                #ANCHOR - PARSER                              #
# ============================================================================ #

jadwal_parser = jadwal_ns.parser()
jadwal_parser.add_argument("id_mentor", type=int, required=False, location="args", help="Filter berdasarkan ID mentor")
jadwal_parser.add_argument("id_paketkelas", type=int, required=False, location="args", help="Filter berdasarkan ID paket kelas")


mentor_dropdown_parser = jadwal_ns.parser()
mentor_dropdown_parser.add_argument("id_paketkelas", type=int, required=False, location="args", help="Filter mentor berdasarkan ID paket kelas")



# ============================================================================ #
#                       #ANCHOR - MANAJEMEN JADWAL BY ADMIN                    #
# ============================================================================ #

@jadwal_ns.route("")
class JadwalListResource(Resource):

    @role_required("admin")
    @jadwal_ns.expect(jadwal_model)
    def post(self):
        """Akses: admin, Membuat jadwal kelas"""

        id_user = get_jwt_identity()
        data = request.get_json()

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        required_fields = [
            "id_paketkelas", "id_mentor", "tanggal",
            "waktu_mulai", "waktu_selesai", "type_pertemuan"
        ]
        missing_fields = [field for field in required_fields if data.get(field) is None]

        if missing_fields:
            return {
                "status": "error",
                "message": f"Field wajib diisi: {', '.join(missing_fields)}"
            }, 400

        id_paketkelas = data["id_paketkelas"]
        id_mentor = data["id_mentor"]
        tanggal = data["tanggal"]
        waktu_mulai = data["waktu_mulai"]
        waktu_selesai = data["waktu_selesai"]
        type_pertemuan = data["type_pertemuan"].upper()

        if type_pertemuan not in ["ONLINE", "OFFLINE"]:
            return {
                "status": "error",
                "message": "type_pertemuan harus ONLINE atau OFFLINE"
            }, 400

        if waktu_mulai >= waktu_selesai:
            return {
                "status": "error",
                "message": "waktu_mulai harus lebih kecil dari waktu_selesai"
            }, 400

        try:
            if not is_valid_paketkelas(id_paketkelas):
                return {"status": "error", "message": "Paket kelas tidak ditemukan"}, 404

            if not is_valid_mentor(id_mentor):
                return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

            if not is_mentor_of_kelas(id_mentor, id_paketkelas):
                return {
                    "status": "error",
                    "message": "Mentor tidak terdaftar pada kelas tersebut"
                }, 400

            result = insert_jadwal({
                "id_paketkelas": id_paketkelas,
                "id_mentor": id_mentor,
                "tanggal": tanggal,
                "waktu_mulai": waktu_mulai,
                "waktu_selesai": waktu_selesai,
                "type_pertemuan": type_pertemuan,
                "created_by": id_user,
                "updated_by": id_user
            })

            if not result:
                return {"status": "error", "message": "Gagal membuat jadwal"}, 400

            return {
                "status": "success",
                "message": "Jadwal berhasil dibuat",
                "data": result
            }, 201

        except SQLAlchemyError as e:
            print(f"[POST /jadwal] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required(["admin", "mentor"])
    @jadwal_ns.expect(jadwal_parser)
    def get(self):
        """Akses: admin/mentor, Mengambil daftar jadwal"""

        id_user = get_jwt_identity()

        try:
            role = get_jwt()["role"]
            args = jadwal_parser.parse_args()

            if role == "admin":
                result = get_all_jadwal(
                    id_mentor=args.get("id_mentor"),
                    id_paketkelas=args.get("id_paketkelas")
                )
            else:
                result = get_all_jadwal_by_mentor(id_user)

            return {
                "status": "success",
                "data": result,
                "meta": {"total": len(result)}
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



# ============================================================================ #
#            #ANCHOR MANAJEMEN JADWAL BY DETAIL (ADD, UPDATE, DELETE)          #
# ============================================================================ #
@jadwal_ns.route("/<int:id_jadwal>")
class JadwalResource(Resource):

    @role_required(["admin", "mentor"])
    def get(self, id_jadwal):
        """Akses: admin/mentor, Mengambil detail jadwal"""

        id_user = get_jwt_identity()

        try:
            role = get_jwt()["role"]
            result = (
                get_jadwal_by_id(id_jadwal)
                if role == "admin"
                else get_jadwal_by_id_mentor(id_jadwal, id_user)
            )

            if not result:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            return {"status": "success", "data": result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required("admin")
    @jadwal_ns.expect(jadwal_model)
    def put(self, id_jadwal):
        """Akses: admin, Mengubah jadwal"""

        id_user = get_jwt_identity()
        data = request.get_json()

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        required_fields = [
            "id_paketkelas", "id_mentor", "tanggal",
            "waktu_mulai", "waktu_selesai", "type_pertemuan"
        ]
        missing_fields = [field for field in required_fields if data.get(field) is None]

        if missing_fields:
            return {
                "status": "error",
                "message": f"Field wajib diisi: {', '.join(missing_fields)}"
            }, 400

        id_paketkelas = data["id_paketkelas"]
        id_mentor = data["id_mentor"]
        tanggal = data["tanggal"]
        waktu_mulai = data["waktu_mulai"]
        waktu_selesai = data["waktu_selesai"]
        type_pertemuan = data["type_pertemuan"].upper()

        if type_pertemuan not in ["ONLINE", "OFFLINE"]:
            return {
                "status": "error",
                "message": "type_pertemuan harus ONLINE atau OFFLINE"
            }, 400

        if waktu_mulai >= waktu_selesai:
            return {
                "status": "error",
                "message": "waktu_mulai harus lebih kecil dari waktu_selesai"
            }, 400

        try:
            existing = get_jadwal_by_id(id_jadwal)

            if not existing:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            if not is_valid_paketkelas(id_paketkelas):
                return {"status": "error", "message": "Paket kelas tidak ditemukan"}, 404

            if not is_valid_mentor(id_mentor):
                return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

            if not is_mentor_of_kelas(id_mentor, id_paketkelas):
                return {
                    "status": "error",
                    "message": "Mentor tidak terdaftar pada kelas tersebut"
                }, 400

            result = update_jadwal({
                "id_jadwal": id_jadwal,
                "id_paketkelas": id_paketkelas,
                "id_mentor": id_mentor,
                "tanggal": tanggal,
                "waktu_mulai": waktu_mulai,
                "waktu_selesai": waktu_selesai,
                "type_pertemuan": type_pertemuan,
                "updated_by": id_user
            })

            if not result:
                return {"status": "error", "message": "Gagal mengubah jadwal"}, 400

            return {
                "status": "success",
                "message": "Jadwal berhasil diubah",
                "data": result
            }, 200

        except SQLAlchemyError as e:
            print(f"[PUT /jadwal/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required(["admin", "mentor"])
    @jadwal_ns.expect(reschedule_model)
    def patch(self, id_jadwal):
        """Akses: admin/mentor, Melakukan reschedule jadwal"""

        id_user = get_jwt_identity()
        data = request.get_json()

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        required_fields = [
            "tanggal_reschedule",
            "waktu_mulai_reschedule",
            "waktu_selesai_reschedule"
        ]
        missing_fields = [field for field in required_fields if data.get(field) is None]

        if missing_fields:
            return {
                "status": "error",
                "message": f"Field wajib diisi: {', '.join(missing_fields)}"
            }, 400

        tanggal_reschedule = data["tanggal_reschedule"]
        waktu_mulai_reschedule = data["waktu_mulai_reschedule"]
        waktu_selesai_reschedule = data["waktu_selesai_reschedule"]

        if waktu_mulai_reschedule >= waktu_selesai_reschedule:
            return {
                "status": "error",
                "message": (
                    "waktu_mulai_reschedule harus lebih kecil "
                    "dari waktu_selesai_reschedule"
                )
            }, 400

        try:
            role = get_jwt()["role"]
            existing = (
                get_jadwal_by_id(id_jadwal)
                if role == "admin"
                else get_jadwal_by_id_mentor(id_jadwal, id_user)
            )

            if not existing:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            result = reschedule_jadwal({
                "id_jadwal": id_jadwal,
                "tanggal_reschedule": tanggal_reschedule,
                "waktu_mulai_reschedule": waktu_mulai_reschedule,
                "waktu_selesai_reschedule": waktu_selesai_reschedule,
                "updated_by": id_user
            })

            if not result:
                return {"status": "error", "message": "Gagal melakukan reschedule"}, 400

            return {
                "status": "success",
                "message": "Jadwal berhasil di-reschedule",
                "data": result
            }, 200

        except SQLAlchemyError as e:
            print(f"[PATCH /jadwal/{id_jadwal}/reschedule] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required("admin")
    def delete(self, id_jadwal):
        """Akses: admin, Soft delete jadwal"""

        id_user = get_jwt_identity()

        try:
            existing = get_jadwal_by_id(id_jadwal)

            if not existing:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            result = delete_jadwal(id_jadwal, id_user)

            if not result:
                return {"status": "error", "message": "Gagal menghapus jadwal"}, 400

            return {"status": "success", "message": "Jadwal berhasil dihapus"}, 200

        except SQLAlchemyError as e:
            print(f"[DELETE /jadwal/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



# ============================================================================ #
#                       #ANCHOR - GET MENTOR FOR DROPDOWN                      #
# ============================================================================ #
@jadwal_ns.route("/mentor-dropdown")
class MentorDropdownResource(Resource):

    @role_required("admin")
    @jadwal_ns.expect(mentor_dropdown_parser)
    def get(self):
        """Akses: admin, Mengambil mentor untuk dropdown"""

        try:
            id_paketkelas = mentor_dropdown_parser.parse_args().get("id_paketkelas")

            if id_paketkelas is not None and not is_valid_paketkelas(id_paketkelas):
                return {"status": "error", "message": "Paket kelas tidak ditemukan"}, 404

            result = get_mentor_dropdown(id_paketkelas)

            return {
                "status": "success",
                "data": result,
                "meta": {"total": len(result)}
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/mentor-dropdown] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500