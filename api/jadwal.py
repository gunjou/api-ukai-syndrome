from flask import request, send_file
from werkzeug.datastructures import FileStorage
from flask_jwt_extended import get_jwt_identity, get_jwt
from flask_restx import Namespace, Resource, fields, reqparse
from sqlalchemy.exc import SQLAlchemyError

from .utils.decorator import role_required
from .query.q_jadwal import *
from .query.q_jadwal_bulk import *


jadwal_ns = Namespace("jadwal", description="Manajemen Jadwal Kelas")


# ============================================================================ #
#                                #ANCHOR - MODEL                               #
# ============================================================================ #

jadwal_model = jadwal_ns.model("Jadwal", {
    "id_paketkelas": fields.Integer(required=True, description="ID paket kelas"),
    "id_mentor": fields.Integer(required=True, description="ID mentor"),
    "topik": fields.String(required=False, description="Topik pertemuan"),
    "catatan": fields.String(required=False, description="Catatan pertemuan"),
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


bulk_import_response_model = jadwal_ns.model("BulkImportResponse", {
    "import_id": fields.String(description="ID import untuk proses preview/commit"),
    "total_rows": fields.Integer(description="Jumlah total row"),
    "valid_rows": fields.Integer(description="Jumlah row valid"),
    "invalid_rows": fields.Integer(description="Jumlah row invalid"),
    "status": fields.String(description="Status import")
})



# ============================================================================ #
#                                #ANCHOR - PARSER                              #
# ============================================================================ #

jadwal_parser = jadwal_ns.parser()
jadwal_parser.add_argument("id_mentor", type=int, required=False, location="args", help="Filter berdasarkan ID mentor")
jadwal_parser.add_argument("id_paketkelas", type=int, required=False, location="args", help="Filter berdasarkan ID paket kelas")


mentor_dropdown_parser = jadwal_ns.parser()
mentor_dropdown_parser.add_argument("id_paketkelas", type=int, required=False, location="args", help="Filter mentor berdasarkan ID paket kelas")


bulk_jadwal_parser = reqparse.RequestParser()
bulk_jadwal_parser.add_argument("file", type=FileStorage, location="files", required=True, help="File jadwal dalam format CSV atau XLSX")



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
        topik = data.get("topik")
        catatan = data.get("catatan")
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
                "topik": topik,
                "catatan": catatan,
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
        topik = data.get("topik")
        catatan = data.get("catatan")
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
                "topik": topik,
                "catatan": catatan,
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



# ============================================================================ #
#                         BULK IMPORT JADWAL                                  #
# ============================================================================ #

bulk_import_response_model = jadwal_ns.model("BulkImportResponse", {
    "import_id": fields.String(
        description="ID import untuk proses preview/commit"
    ),
    "total_rows": fields.Integer(
        description="Jumlah total row"
    ),
    "valid_rows": fields.Integer(
        description="Jumlah row valid"
    ),
    "invalid_rows": fields.Integer(
        description="Jumlah row invalid"
    ),
    "status": fields.String(
        description="Status import"
    )
})


# ============================================================================ #
#                        BULK IMPORT - VALIDATE                                #
# ============================================================================ #

@jadwal_ns.route("/bulk/validate")
class JadwalBulkValidateResource(Resource):

    @role_required("admin")
    @jadwal_ns.expect(bulk_jadwal_parser)
    def post(self):
        """
        Akses: admin

        Upload CSV/XLSX untuk divalidasi.

        Endpoint ini TIDAK melakukan insert ke jadwal_kelas.
        """

        id_user = get_jwt_identity()
        file = request.files.get("file")

        # ------------------------------------------------------------------ #
        # VALIDASI FILE
        # ------------------------------------------------------------------ #

        if not file:
            return {
                "status": "error",
                "message": "File wajib diupload"
            }, 400

        if not file.filename:
            return {
                "status": "error",
                "message": "File tidak boleh kosong"
            }, 400

        # ------------------------------------------------------------------ #
        # VALIDASI EXTENSION
        # ------------------------------------------------------------------ #

        filename = file.filename.lower()

        allowed_extensions = {
            ".csv",
            ".xlsx"
        }

        if "." not in filename:
            return {
                "status": "error",
                "message": "Format file tidak didukung"
            }, 400

        extension = "." + filename.rsplit(".", 1)[1]

        if extension not in allowed_extensions:
            return {
                "status": "error",
                "message": (
                    "File harus berformat CSV atau XLSX"
                )
            }, 400

        try:
            result = validate_bulk_jadwal(
                file=file,
                filename=file.filename,
                id_user=id_user
            )

            if not result:
                return {
                    "status": "error",
                    "message": "Gagal melakukan validasi file"
                }, 400

            # ============================================================= #
            # INVALID
            # ============================================================= #

            if result.get("status") == "INVALID":
                return {
                    "status": "error",
                    "message": (
                        "File memiliki data yang tidak valid"
                    ),
                    "data": {
                        "import_id": result.get("import_id"),
                        "total_rows": result.get(
                            "total_rows",
                            0
                        ),
                        "valid_rows": result.get(
                            "valid_rows",
                            0
                        ),
                        "invalid_rows": result.get(
                            "invalid_rows",
                            0
                        ),
                        "errors": result.get(
                            "errors",
                            []
                        )
                    }
                }, 422

            # ============================================================= #
            # VALID
            # ============================================================= #

            return {
                "status": "success",
                "message": (
                    "File valid dan siap di-import"
                ),
                "data": {
                    "import_id": result.get(
                        "import_id"
                    ),
                    "total_rows": result.get(
                        "total_rows",
                        0
                    ),
                    "valid_rows": result.get(
                        "valid_rows",
                        0
                    ),
                    "invalid_rows": result.get(
                        "invalid_rows",
                        0
                    ),
                    "preview": result.get(
                        "preview",
                        []
                    )
                }
            }, 200

        except SQLAlchemyError as e:
            print(
                f"[POST /jadwal/bulk/validate] "
                f"Error: {e}"
            )

            return {
                "status": "error",
                "message": "Internal server error"
            }, 500

        except Exception as e:
            print(
                f"[POST /jadwal/bulk/validate] "
                f"Unexpected Error: {e}"
            )

            return {
                "status": "error",
                "message": "Gagal memproses file"
            }, 500


# ============================================================================ #
#                        BULK IMPORT - DETAIL                                  #
# ============================================================================ #

@jadwal_ns.route("/bulk/<string:import_id>")
class JadwalBulkDetailResource(Resource):

    @role_required("admin")
    def get(self, import_id):
        """
        Akses: admin

        Mengambil hasil validation berdasarkan import_id.

        Digunakan untuk:
        - melihat hasil import
        - melihat error per row
        - melihat preview data
        - mengecek apakah import sudah siap di-commit
        """

        try:
            result = get_bulk_jadwal_import(import_id)

            if not result:
                return {
                    "status": "error",
                    "message": "Data import tidak ditemukan"
                }, 404

            return {
                "status": "success",
                "data": result
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/bulk/{import_id}] Error: {e}")

            return {
                "status": "error",
                "message": "Internal server error"
            }, 500

        except Exception as e:
            print(f"[GET /jadwal/bulk/{import_id}] Unexpected Error: {e}")

            return {
                "status": "error",
                "message": "Gagal mengambil data import"
            }, 500


# ============================================================================ #
#                        BULK IMPORT - COMMIT                                  #
# ============================================================================ #

@jadwal_ns.route("/bulk/<string:import_id>/commit")
class JadwalBulkCommitResource(Resource):

    @role_required("admin")
    def post(self, import_id):
        """
        Akses: admin

        Melakukan commit terhadap hasil bulk import.

        HANYA import dengan status VALID yang boleh di-commit.

        Seluruh row akan dimasukkan dalam satu transaction.

        Jika satu row gagal:
        -> seluruh transaction di-rollback
        -> tidak ada jadwal yang masuk sebagian.
        """

        id_user = get_jwt_identity()

        try:
            # ============================================================= #
            # TODO:
            # Fungsi ini nanti akan dibuat di q_jadwal.py
            #
            # result = commit_bulk_jadwal(
            #     import_id=import_id,
            #     id_user=id_user
            # )
            # ============================================================= #

            result = commit_bulk_jadwal(
                import_id=import_id,
                id_user=id_user
            )

            if not result:
                return {
                    "status": "error",
                    "message": "Gagal melakukan import jadwal"
                }, 400

            if result.get("status") == "NOT_FOUND":
                return {
                    "status": "error",
                    "message": "Data import tidak ditemukan"
                }, 404

            if result.get("status") == "INVALID":
                return {
                    "status": "error",
                    "message": (
                        "Import tidak dapat dilakukan karena "
                        "data belum valid"
                    )
                }, 422

            if result.get("status") == "ALREADY_COMMITTED":
                return {
                    "status": "error",
                    "message": "Import ini sudah pernah di-commit"
                }, 409

            if result.get("status") == "EXPIRED":
                return {
                    "status": "error",
                    "message": "Data import sudah expired"
                }, 410

            return {
                "status": "success",
                "message": "Bulk jadwal berhasil di-import",
                "data": {
                    "import_id": import_id,
                    "total_rows": result.get("total_rows", 0),
                    "inserted_rows": result.get("inserted_rows", 0)
                }
            }, 201

        except SQLAlchemyError as e:
            print(f"[POST /jadwal/bulk/{import_id}/commit] Error: {e}")

            return {
                "status": "error",
                "message": "Internal server error"
            }, 500

        except Exception as e:
            print(
                f"[POST /jadwal/bulk/{import_id}/commit] "
                f"Unexpected Error: {e}"
            )

            return {
                "status": "error",
                "message": "Gagal melakukan import jadwal"
            }, 500


# ============================================================================ #
#                          BULK IMPORT - TEMPLATE                              #
# ============================================================================ #

@jadwal_ns.route("/bulk/template")
class JadwalBulkTemplateResource(Resource):

    @role_required("admin")
    def get(self):
        """
        Akses: admin

        Download template XLSX untuk bulk import jadwal.
        """

        try:
            template_path = get_bulk_jadwal_template()

            if not template_path:
                return {
                    "status": "error",
                    "message": "Template tidak ditemukan"
                }, 404

            return send_file(
                template_path,
                as_attachment=True,
                download_name="template_import_jadwal.xlsx",
                mimetype=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )

        except Exception as e:
            print(
                f"[GET /jadwal/bulk/template] "
                f"Unexpected Error: {e}"
            )

            return {
                "status": "error",
                "message": "Gagal mengambil template"
            }, 500



# ============================================================================ #
#                        BULK IMPORT - HISTORY                                #
# ============================================================================ #

@jadwal_ns.route("/bulk/history")
class JadwalBulkHistoryResource(Resource):

    @role_required("admin")
    def get(self):
        """
        Akses: admin

        Mengambil history bulk import jadwal
        yang sudah COMMITTED atau ROLLED_BACK.
        """

        try:

            result = get_bulk_jadwal_history()

            return {
                "status": "success",
                "data": result
            }, 200

        except SQLAlchemyError as e:

            print(
                f"[GET /jadwal/bulk/history] Error: {e}"
            )

            return {
                "status": "error",
                "message": "Internal server error"
            }, 500

        except Exception as e:

            print(
                f"[GET /jadwal/bulk/history] "
                f"Unexpected Error: {e}"
            )

            return {
                "status": "error",
                "message": "Gagal mengambil history import"
            }, 500



# ============================================================================ #
#                        BULK IMPORT - ROLLBACK                               #
# ============================================================================ #

@jadwal_ns.route("/bulk/<string:import_id>/rollback")
class JadwalBulkRollbackResource(Resource):

    @role_required("admin")
    def post(self, import_id):
        """
        Akses: admin

        Membatalkan hasil bulk import yang sudah COMMITTED.

        Semua jadwal_kelas yang dibuat oleh import tersebut
        akan dihapus dalam satu transaction.

        History import tetap dipertahankan dengan status
        ROLLED_BACK.
        """

        id_user = get_jwt_identity()

        try:

            result = rollback_bulk_jadwal(
                import_id=import_id,
                id_user=id_user
            )

            if not result:
                return {
                    "status": "error",
                    "message": "Gagal melakukan rollback"
                }, 400

            if result.get("status") == "NOT_FOUND":
                return {
                    "status": "error",
                    "message": "Data import tidak ditemukan"
                }, 404

            if result.get("status") == "NOT_COMMITTED":
                return {
                    "status": "error",
                    "message": (
                        "Import belum berstatus COMMITTED "
                        "sehingga tidak dapat di-rollback"
                    )
                }, 422

            if result.get("status") == "ALREADY_ROLLED_BACK":
                return {
                    "status": "error",
                    "message": "Import ini sudah pernah di-rollback"
                }, 409

            if result.get("status") == "NO_DATA":
                return {
                    "status": "error",
                    "message": (
                        "Tidak ditemukan jadwal "
                        "hasil import yang dapat di-rollback"
                    )
                }, 422

            return {
                "status": "success",
                "message": "Bulk import berhasil di-rollback",
                "data": {
                    "import_id": import_id,
                    "total_rows": result.get(
                        "total_rows",
                        0
                    ),
                    "deleted_rows": result.get(
                        "deleted_rows",
                        0
                    )
                }
            }, 200

        except SQLAlchemyError as e:

            print(
                f"[POST /jadwal/bulk/{import_id}/rollback] "
                f"Error: {e}"
            )

            return {
                "status": "error",
                "message": "Internal server error"
            }, 500

        except Exception as e:

            print(
                f"[POST /jadwal/bulk/{import_id}/rollback] "
                f"Unexpected Error: {e}"
            )

            return {
                "status": "error",
                "message": "Gagal melakukan rollback"
            }, 500