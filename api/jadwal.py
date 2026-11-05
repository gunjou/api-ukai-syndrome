import calendar
from datetime import date, datetime, timedelta

from flask import request, send_file
from werkzeug.datastructures import FileStorage
from flask_jwt_extended import get_jwt_identity, get_jwt
from flask_restx import Namespace, Resource, fields, reqparse
from sqlalchemy.exc import SQLAlchemyError

from .utils.config import get_wib
from .utils.decorator import role_required
from .query.q_jadwal import *
from .query.q_jadwal_bulk import *


jadwal_ns = Namespace("jadwal", description="Manajemen Jadwal Kelas")


# ============================================================================ #
#                                #ANCHOR - MODEL                               #
# ============================================================================ #

jadwal_model = jadwal_ns.model("Jadwal", {
    "id_paketkelas": fields.Integer(required=False, description="ID paket kelas (wajib untuk ONLINE, isi salah satu dengan id_kelompok)"),
    "id_kelompok": fields.Integer(required=False, description="ID kelompok belajar (khusus OFFLINE, isi salah satu dengan id_paketkelas)"),
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


jadwal_v2_model = jadwal_ns.model("JadwalV2", {
    "id_paketkelas": fields.Integer(required=False, description="ID kelas (ONLINE/OFFLINE). Isi tepat satu dari id_paketkelas / id_kelompok / id_mentorship"),
    "id_kelompok": fields.Integer(required=False, description="ID kelompok belajar (khusus OFFLINE)"),
    "id_mentorship": fields.Integer(required=False, description="ID kelas private / mentorship (ONLINE/OFFLINE)"),
    "id_mentor": fields.Integer(required=True, description="ID mentor"),
    "topik": fields.String(required=False, description="Topik pertemuan"),
    "catatan": fields.String(required=False, description="Catatan pertemuan"),
    "tanggal": fields.Date(required=True, description="Tanggal jadwal"),
    "waktu_mulai": fields.String(required=True, description="Waktu mulai, format HH:MM"),
    "waktu_selesai": fields.String(required=True, description="Waktu selesai, format HH:MM"),
    "type_pertemuan": fields.String(required=True, description="Tipe pertemuan (ONLINE/OFFLINE)")
})


jadwal_group_edit_model = jadwal_ns.model("JadwalGroupEditV2", {
    "id_mentor": fields.Integer(required=True, description="ID mentor (diterapkan ke semua jadwal dalam group)"),
    "topik": fields.String(required=False, description="Topik pertemuan"),
    "catatan": fields.String(required=False, description="Catatan pertemuan"),
    "tanggal": fields.Date(required=True, description="Tanggal jadwal"),
    "waktu_mulai": fields.String(required=True, description="Waktu mulai, format HH:MM"),
    "waktu_selesai": fields.String(required=True, description="Waktu selesai, format HH:MM")
})


switch_mentor_model = jadwal_ns.model("SwitchMentor", {
    "id_jadwal_1": fields.Integer(required=True, description="ID jadwal pertama"),
    "id_jadwal_2": fields.Integer(required=True, description="ID jadwal kedua")
})



# ============================================================================ #
#                                #ANCHOR - PARSER                              #
# ============================================================================ #

jadwal_parser = jadwal_ns.parser()
jadwal_parser.add_argument("id_mentor", type=int, required=False, location="args", help="Filter berdasarkan ID mentor")
jadwal_parser.add_argument("id_paketkelas", type=int, required=False, location="args", help="Filter berdasarkan ID paket kelas")
jadwal_parser.add_argument("id_kelompok", type=int, required=False, location="args", help="Filter berdasarkan ID kelompok belajar")
jadwal_parser.add_argument("type_pertemuan", type=str, required=False, location="args", help="Filter tipe pertemuan: ONLINE / OFFLINE")
jadwal_parser.add_argument("search", type=str, required=False, location="args", help="Pencarian berdasarkan nama mentor, nama kelas, topik, atau catatan")
jadwal_parser.add_argument("start_date", type=str, required=False, location="args", help="Tanggal awal periode (YYYY-MM-DD)")
jadwal_parser.add_argument("end_date", type=str, required=False, location="args", help="Tanggal akhir periode (YYYY-MM-DD)")
jadwal_parser.add_argument("page", type=int, required=False, default=1, location="args", help="Halaman")
jadwal_parser.add_argument("per_page", type=int, required=False, default=50, location="args", help="Jumlah data per halaman, maksimum 100")

# Khusus /v2/group: urutan default "mulai dari sekarang" (tidak mempengaruhi endpoint lama)
jadwal_group_v2_parser = jadwal_parser.copy()
jadwal_group_v2_parser.add_argument("upcoming", type=int, required=False, default=0, location="args", help="1 = jadwal yang belum selesai tampil lebih dulu (terdekat), lalu yang sudah selesai (terbaru). 0 = kronologis")


mentor_dropdown_parser = jadwal_ns.parser()
mentor_dropdown_parser.add_argument("id_paketkelas", type=int, required=False, location="args", help="Filter mentor berdasarkan ID paket kelas")


bulk_jadwal_parser = reqparse.RequestParser()
bulk_jadwal_parser.add_argument("file", type=FileStorage, location="files", required=True, help="File jadwal dalam format CSV atau XLSX")


jadwal_peserta_parser = jadwal_ns.parser()
jadwal_peserta_parser.add_argument("start_date", type=str, required=False, location="args", help="Tanggal awal periode (YYYY-MM-DD), default awal bulan ini")
jadwal_peserta_parser.add_argument("end_date", type=str, required=False, location="args", help="Tanggal akhir periode (YYYY-MM-DD), default akhir bulan ini")


jadwal_wali_kelas_parser = jadwal_ns.parser()
jadwal_wali_kelas_parser.add_argument("bulan", type=str, required=False, location="args", help="Filter bulanan (YYYY-MM), default bulan berjalan")
jadwal_wali_kelas_parser.add_argument("start_date", type=str, required=False, location="args", help="Tanggal awal range (YYYY-MM-DD), wajib berpasangan dengan end_date. Jika diisi, filter bulan diabaikan")
jadwal_wali_kelas_parser.add_argument("end_date", type=str, required=False, location="args", help="Tanggal akhir range (YYYY-MM-DD), wajib berpasangan dengan start_date")
jadwal_wali_kelas_parser.add_argument("id_paketkelas", type=int, required=False, location="args", help="Filter kelas (harus kelas yang Anda walikan)")
jadwal_wali_kelas_parser.add_argument("search", type=str, required=False, location="args", help="Pencarian nama mentor, nama kelas, topik, atau catatan")


# ============================================================================ #
#                           #ANCHOR - HELPER VALIDASI                          #
# ============================================================================ #

def validate_target_jadwal(type_pertemuan, id_paketkelas, id_kelompok, id_mentor):
    """
    Aturan target jadwal:
    - Wajib tepat satu: id_paketkelas ATAU id_kelompok
    - ONLINE  -> wajib id_paketkelas
    - OFFLINE -> id_kelompok (lintas kelas) atau id_paketkelas (satu kelas utuh)
    Return None jika valid, atau (response, status_code) jika tidak valid.
    """

    if id_paketkelas is None and id_kelompok is None:
        return {
            "status": "error",
            "message": "Isi salah satu: id_paketkelas atau id_kelompok"
        }, 400

    if id_paketkelas is not None and id_kelompok is not None:
        return {
            "status": "error",
            "message": "id_paketkelas dan id_kelompok tidak boleh diisi bersamaan"
        }, 400

    if type_pertemuan == "ONLINE" and id_paketkelas is None:
        return {
            "status": "error",
            "message": "Pertemuan ONLINE wajib menggunakan id_paketkelas"
        }, 400

    if id_paketkelas is not None:
        if not is_valid_paketkelas(id_paketkelas):
            return {"status": "error", "message": "Paket kelas tidak ditemukan"}, 404

        if not is_valid_mentor(id_mentor):
            return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

        if not is_mentor_of_kelas(id_mentor, id_paketkelas):
            return {
                "status": "error",
                "message": "Mentor tidak terdaftar pada kelas tersebut"
            }, 400

        return None

    # ==========================================
    # Target kelompok: mentor cukup aktif,
    # tidak perlu terdaftar di mentorkelas
    # ==========================================

    if not is_valid_kelompok(id_kelompok):
        return {"status": "error", "message": "Kelompok tidak ditemukan"}, 404

    if not is_valid_mentor(id_mentor):
        return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

    return None


def validate_target_jadwal_v2(type_pertemuan, id_paketkelas, id_kelompok, id_mentorship, id_mentor):
    """
    Aturan target jadwal v2 (mendukung kelas private):
    - Wajib tepat satu: id_paketkelas / id_kelompok / id_mentorship
    - ONLINE  -> kelas atau kelas private
    - OFFLINE -> kelompok, kelas, atau kelas private
    Return None jika valid, atau (response, status_code) jika tidak valid.
    """

    targets = [t for t in (id_paketkelas, id_kelompok, id_mentorship) if t is not None]

    if len(targets) != 1:
        return {
            "status": "error",
            "message": "Isi tepat satu: kelas, kelompok, atau kelas private"
        }, 400

    if type_pertemuan == "ONLINE" and id_kelompok is not None:
        return {
            "status": "error",
            "message": "Pertemuan ONLINE hanya bisa untuk kelas atau kelas private"
        }, 400

    if not is_valid_mentor(id_mentor):
        return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

    if id_paketkelas is not None:
        if not is_valid_paketkelas(id_paketkelas):
            return {"status": "error", "message": "Paket kelas tidak ditemukan"}, 404

        if not is_mentor_of_kelas(id_mentor, id_paketkelas):
            return {"status": "error", "message": "Mentor tidak terdaftar pada kelas tersebut"}, 400

        return None

    if id_kelompok is not None:
        if not is_valid_kelompok(id_kelompok):
            return {"status": "error", "message": "Kelompok tidak ditemukan"}, 404

        return None

    if not get_mentorship_v2(id_mentorship):
        return {"status": "error", "message": "Kelas private tidak ditemukan"}, 404

    return None


def parse_type_pertemuan(value):
    """Return (type_pertemuan, error). Kosong = tanpa filter."""
    if not value or not value.strip():
        return None, None
    value = value.strip().upper()
    if value not in ("ONLINE", "OFFLINE"):
        return None, ({"status": "error", "message": "Parameter type_pertemuan harus ONLINE atau OFFLINE"}, 400)
    return value, None


def resolve_periode(start_date, end_date):
    """Default periode = bulan berjalan. Return (start_date, end_date, error)."""

    if not start_date or not end_date:
        today = datetime.now().date()
        start_date = today.replace(day=1)

        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    try:
        start_date = datetime.strptime(str(start_date), "%Y-%m-%d").date()
        end_date = datetime.strptime(str(end_date), "%Y-%m-%d").date()

    except ValueError:
        return None, None, ({
            "status": "error",
            "message": "Format tanggal harus YYYY-MM-DD"
        }, 400)

    if start_date > end_date:
        return None, None, ({
            "status": "error",
            "message": "start_date tidak boleh lebih besar dari end_date"
        }, 400)

    return start_date, end_date, None


def resolve_periode_wali_kelas(bulan, start_date, end_date):
    """
    Prioritas filter:
    1. start_date + end_date (range tanggal)
    2. bulan (YYYY-MM) -> tanggal 1 s/d akhir bulan
    3. default bulan berjalan
    Return (periode, error).
    """

    if start_date or end_date:
        if not start_date or not end_date:
            return None, ({
                "status": "error",
                "message": "start_date dan end_date wajib diisi bersamaan"
            }, 400)

        try:
            start_date = datetime.strptime(str(start_date).strip(), "%Y-%m-%d").date()
            end_date = datetime.strptime(str(end_date).strip(), "%Y-%m-%d").date()

        except ValueError:
            return None, ({
                "status": "error",
                "message": "Format tanggal harus YYYY-MM-DD"
            }, 400)

        if start_date > end_date:
            return None, ({
                "status": "error",
                "message": "start_date tidak boleh lebih besar dari end_date"
            }, 400)

        return {
            "filter": "RANGE",
            "bulan": None,
            "start_date": start_date,
            "end_date": end_date
        }, None

    if bulan and str(bulan).strip():
        try:
            parsed = datetime.strptime(str(bulan).strip(), "%Y-%m")
        except ValueError:
            return None, ({
                "status": "error",
                "message": "Format bulan harus YYYY-MM, contoh 2026-10"
            }, 400)

        tahun, nomor_bulan = parsed.year, parsed.month

    else:
        today = get_wib().date()
        tahun, nomor_bulan = today.year, today.month

    last_day = calendar.monthrange(tahun, nomor_bulan)[1]

    return {
        "filter": "BULAN",
        "bulan": f"{tahun:04d}-{nomor_bulan:02d}",
        "start_date": date(tahun, nomor_bulan, 1),
        "end_date": date(tahun, nomor_bulan, last_day)
    }, None



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
            "id_mentor", "tanggal",
            "waktu_mulai", "waktu_selesai", "type_pertemuan"
        ]
        missing_fields = [field for field in required_fields if data.get(field) is None]

        if missing_fields:
            return {
                "status": "error",
                "message": f"Field wajib diisi: {', '.join(missing_fields)}"
            }, 400

        id_paketkelas = data.get("id_paketkelas")
        id_kelompok = data.get("id_kelompok")
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
            error = validate_target_jadwal(
                type_pertemuan,
                id_paketkelas,
                id_kelompok,
                id_mentor
            )

            if error:
                return error

            result = insert_jadwal({
                "id_paketkelas": id_paketkelas,
                "id_kelompok": id_kelompok,
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
        """Akses: admin/mentor, Mengambil daftar jadwal."""

        id_user = get_jwt_identity()

        try:
            role = get_jwt()["role"]
            args = jadwal_parser.parse_args()
            search = args.get("search")

            type_pertemuan, err = parse_type_pertemuan(args.get("type_pertemuan"))
            if err:
                return err

            if role == "admin":
                id_mentor = args.get("id_mentor")
                id_paketkelas = args.get("id_paketkelas")
                start_date = args.get("start_date")
                end_date = args.get("end_date")
                page = args.get("page") or 1
                per_page = args.get("per_page") or 50

                if page < 1:
                    return {
                        "status": "error",
                        "message": "Parameter page harus lebih besar dari 0"
                    }, 400

                if not 1 <= per_page <= 100:
                    return {
                        "status": "error",
                        "message": "Parameter per_page harus berada antara 1 dan 100"
                    }, 400

                if not start_date or not end_date:
                    today = datetime.now().date()
                    start_date = today.replace(day=1)

                    if today.month == 12:
                        end_date = today.replace(
                            year=today.year + 1,
                            month=1,
                            day=1
                        ) - timedelta(days=1)
                    else:
                        end_date = today.replace(
                            month=today.month + 1,
                            day=1
                        ) - timedelta(days=1)

                try:
                    start_date = datetime.strptime(
                        str(start_date),
                        "%Y-%m-%d"
                    ).date()

                    end_date = datetime.strptime(
                        str(end_date),
                        "%Y-%m-%d"
                    ).date()

                except ValueError:
                    return {
                        "status": "error",
                        "message": "Format tanggal harus YYYY-MM-DD"
                    }, 400

                if start_date > end_date:
                    return {
                        "status": "error",
                        "message": "start_date tidak boleh lebih besar dari end_date"
                    }, 400

                result = get_all_jadwal(
                    type_pertemuan=type_pertemuan,
                    id_mentor=id_mentor,
                    id_paketkelas=id_paketkelas,
                    id_kelompok=args.get("id_kelompok"),
                    search=search,
                    start_date=start_date,
                    end_date=end_date,
                    page=page,
                    per_page=per_page
                )

                return {
                    "status": "success",
                    "data": result["data"],
                    "meta": {
                        "page": result["page"],
                        "per_page": result["per_page"],
                        "total": result["total"],
                        "total_pages": result["total_pages"],
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    }
                }, 200

            # ==========================================
            # MENTOR
            # ==========================================

            result = get_all_jadwal_by_mentor(
                type_pertemuan=type_pertemuan,
                id_mentor=id_user,
                search=search
            )

            return {
                "status": "success",
                "data": result,
                "meta": {
                    "total": len(result)
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal] Error: {e}")

            return {
                "status": "error",
                "message": "Internal server error"
            }, 500
    
    
@jadwal_ns.route("/group")
class JadwalGroupListResource(Resource):
    @role_required(["admin", "mentor"])
    @jadwal_ns.expect(jadwal_parser)
    def get(self):
        """Akses: admin/mentor, Mengambil daftar jadwal."""

        id_user = get_jwt_identity()

        try:
            role = get_jwt()["role"]
            args = jadwal_parser.parse_args()
            search = args.get("search")

            type_pertemuan, err = parse_type_pertemuan(args.get("type_pertemuan"))
            if err:
                return err

            if role == "admin":
                id_mentor = args.get("id_mentor")
                id_paketkelas = args.get("id_paketkelas")
                start_date = args.get("start_date")
                end_date = args.get("end_date")
                page = args.get("page") or 1
                per_page = args.get("per_page") or 50

                if page < 1:
                    return {
                        "status": "error",
                        "message": "Parameter page harus lebih besar dari 0"
                    }, 400

                if not 1 <= per_page <= 100:
                    return {
                        "status": "error",
                        "message": "Parameter per_page harus berada antara 1 dan 100"
                    }, 400

                if not start_date or not end_date:
                    today = datetime.now().date()
                    start_date = today.replace(day=1)

                    if today.month == 12:
                        end_date = today.replace(
                            year=today.year + 1,
                            month=1,
                            day=1
                        ) - timedelta(days=1)
                    else:
                        end_date = today.replace(
                            month=today.month + 1,
                            day=1
                        ) - timedelta(days=1)

                try:
                    start_date = datetime.strptime(
                        str(start_date),
                        "%Y-%m-%d"
                    ).date()

                    end_date = datetime.strptime(
                        str(end_date),
                        "%Y-%m-%d"
                    ).date()

                except ValueError:
                    return {
                        "status": "error",
                        "message": "Format tanggal harus YYYY-MM-DD"
                    }, 400

                if start_date > end_date:
                    return {
                        "status": "error",
                        "message": "start_date tidak boleh lebih besar dari end_date"
                    }, 400

                result = get_all_jadwal(
                    type_pertemuan=type_pertemuan,
                    id_mentor=id_mentor,
                    id_paketkelas=id_paketkelas,
                    id_kelompok=args.get("id_kelompok"),
                    search=search,
                    start_date=start_date,
                    end_date=end_date,
                    page=page,
                    per_page=per_page
                )

                return {
                    "status": "success",
                    "data": result["data"],
                    "meta": {
                        "page": result["page"],
                        "per_page": result["per_page"],
                        "total": result["total"],
                        "total_pages": result["total_pages"],
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    }
                }, 200

            # ==========================================
            # MENTOR
            # ==========================================

            result = get_group_all_jadwal_by_mentor(
                type_pertemuan=type_pertemuan,
                id_mentor=id_user,
                search=search
            )

            return {
                "status": "success",
                "data": result,
                "meta": {
                    "total": len(result)
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal] Error: {e}")

            return {
                "status": "error",
                "message": "Internal server error"
            }, 500



# ============================================================================ #
#            #ANCHOR MANAJEMEN JADWAL BY DETAIL (ADD, UPDATE, DELETE)          #
# ============================================================================ #
@jadwal_ns.route("/<int:id_jadwal>/group")
class JadwalGroupResource(Resource):

    @role_required(["admin", "mentor"])
    def get(self, id_jadwal):
        """Akses: admin/mentor, Mengambil detail jadwal"""

        id_user = get_jwt_identity()

        try:
            role = get_jwt()["role"]
            result = (
                get_jadwal_by_id(id_jadwal)
                if role == "admin"
                else get_group_jadwal_by_id_mentor(id_jadwal, id_user)
            )

            if not result:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            return {"status": "success", "data": result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


# ============================================================================ #
#              #ANCHOR - JADWAL GROUP V2 (ADMIN & MENTOR, PER SLOT)            #
# ============================================================================ #
# 1 group = 1 mentor + type_pertemuan + tanggal + jam mulai + jam selesai efektif (setelah reschedule).
# Satu group selalu hanya 1 type_pertemuan (ONLINE atau OFFLINE), tidak pernah campuran.
# Endpoint ini terpisah dan tidak mempengaruhi /group maupun /<id>/group yang lama.

@jadwal_ns.route("/v2/group")
class JadwalGroupListV2Resource(Resource):

    @role_required(["admin", "mentor"])
    @jadwal_ns.expect(jadwal_group_v2_parser)
    def get(self):
        """Akses: admin/mentor, [V2] Daftar jadwal yang di-group per mentor + tanggal + jam (1 slot = 1 jadwal)"""

        id_user = get_jwt_identity()

        try:
            role = get_jwt()["role"]
            args = jadwal_group_v2_parser.parse_args()
            upcoming_first = args.get("upcoming") == 1
            search = args.get("search")

            type_pertemuan, err = parse_type_pertemuan(args.get("type_pertemuan"))
            if err:
                return err

            if role != "admin":
                result = get_group_all_jadwal_v2(
                    id_mentor=id_user,
                    type_pertemuan=type_pertemuan,
                    search=search,
                    upcoming_first=upcoming_first
                )
                return {
                    "status": "success",
                    "data": result,
                    "meta": {"total": len(result)}
                }, 200

            page = args.get("page") or 1
            per_page = args.get("per_page") or 50

            if page < 1:
                return {"status": "error", "message": "Parameter page harus lebih besar dari 0"}, 400

            if not 1 <= per_page <= 100:
                return {"status": "error", "message": "Parameter per_page harus berada antara 1 dan 100"}, 400

            start_date = args.get("start_date")
            end_date = args.get("end_date")

            if not start_date or not end_date:
                today = datetime.now().date()
                start_date = today.replace(day=1)
                end_date = today.replace(day=calendar.monthrange(today.year, today.month)[1])
            else:
                try:
                    start_date = datetime.strptime(str(start_date), "%Y-%m-%d").date()
                    end_date = datetime.strptime(str(end_date), "%Y-%m-%d").date()
                except ValueError:
                    return {"status": "error", "message": "Format tanggal harus YYYY-MM-DD"}, 400

            if start_date > end_date:
                return {"status": "error", "message": "start_date tidak boleh lebih besar dari end_date"}, 400

            result = get_group_all_jadwal_v2(
                type_pertemuan=type_pertemuan,
                id_mentor=args.get("id_mentor"),
                id_paketkelas=args.get("id_paketkelas"),
                id_kelompok=args.get("id_kelompok"),
                search=search,
                start_date=start_date,
                end_date=end_date,
                page=page,
                per_page=per_page,
                upcoming_first=upcoming_first
            )

            return {
                "status": "success",
                "data": result["data"],
                "meta": {
                    "page": result["page"],
                    "per_page": result["per_page"],
                    "total": result["total"],
                    "total_pages": result["total_pages"],
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/v2/group] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@jadwal_ns.route("/v2/group/<int:id_jadwal>")
class JadwalGroupDetailV2Resource(Resource):

    @role_required(["admin", "mentor"])
    def get(self, id_jadwal):
        """Akses: admin/mentor, [V2] Detail 1 group jadwal beserta semua kelas/kelompok di slot tersebut"""

        id_user = get_jwt_identity()

        try:
            role = get_jwt()["role"]
            result = get_group_jadwal_by_id_v2(
                id_jadwal,
                id_mentor=None if role == "admin" else id_user
            )

            if not result:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            return {"status": "success", "data": result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/v2/group/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required("admin")
    @jadwal_ns.expect(jadwal_group_edit_model)
    def put(self, id_jadwal):
        """Akses: admin, [V2] Ubah mentor/topik/catatan/tanggal/jam untuk SEMUA jadwal dalam group"""

        id_user = get_jwt_identity()
        data = request.get_json(silent=True)

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        required_fields = ["id_mentor", "tanggal", "waktu_mulai", "waktu_selesai"]
        missing_fields = [field for field in required_fields if data.get(field) in (None, "")]

        if missing_fields:
            return {"status": "error", "message": f"Field wajib diisi: {', '.join(missing_fields)}"}, 400

        id_mentor = data["id_mentor"]
        waktu_mulai = data["waktu_mulai"]
        waktu_selesai = data["waktu_selesai"]

        if waktu_mulai >= waktu_selesai:
            return {"status": "error", "message": "waktu_mulai harus lebih kecil dari waktu_selesai"}, 400

        try:
            members = get_group_members_v2(id_jadwal)

            if not members:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            if not is_valid_mentor(id_mentor):
                return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

            # Jadwal berbasis kelas: mentor baru wajib terdaftar di setiap kelas
            if any(row["id_mentor"] != id_mentor for row in members):
                for row in members:
                    if row["id_paketkelas"] is not None and not is_mentor_of_kelas(id_mentor, row["id_paketkelas"]):
                        return {
                            "status": "error",
                            "message": "Mentor tidak terdaftar pada salah satu kelas dalam group ini"
                        }, 400

            ids = update_group_jadwal_v2(id_jadwal, {
                "id_mentor": id_mentor,
                "topik": data.get("topik"),
                "catatan": data.get("catatan"),
                "tanggal": data["tanggal"],
                "waktu_mulai": waktu_mulai,
                "waktu_selesai": waktu_selesai,
                "updated_by": id_user
            })

            if not ids:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            return {
                "status": "success",
                "message": f"{len(ids)} jadwal berhasil diubah",
                "data": {"id_jadwal": ids}
            }, 200

        except SQLAlchemyError as e:
            print(f"[PUT /jadwal/v2/group/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required("admin")
    def delete(self, id_jadwal):
        """Akses: admin, [V2] Soft delete SEMUA jadwal dalam group"""

        id_user = get_jwt_identity()

        try:
            ids = delete_group_jadwal_v2(id_jadwal, id_user)

            if not ids:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            return {
                "status": "success",
                "message": f"{len(ids)} jadwal berhasil dihapus",
                "data": {"id_jadwal": ids}
            }, 200

        except SQLAlchemyError as e:
            print(f"[DELETE /jadwal/v2/group/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@jadwal_ns.route("/v2/group/<int:id_jadwal>/reschedule")
class JadwalGroupRescheduleV2Resource(Resource):

    @role_required("admin")
    @jadwal_ns.expect(reschedule_model)
    def patch(self, id_jadwal):
        """Akses: admin, [V2] Reschedule SEMUA jadwal dalam group"""

        id_user = get_jwt_identity()
        data = request.get_json(silent=True)

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        required_fields = ["tanggal_reschedule", "waktu_mulai_reschedule", "waktu_selesai_reschedule"]
        missing_fields = [field for field in required_fields if data.get(field) in (None, "")]

        if missing_fields:
            return {"status": "error", "message": f"Field wajib diisi: {', '.join(missing_fields)}"}, 400

        if data["waktu_mulai_reschedule"] >= data["waktu_selesai_reschedule"]:
            return {
                "status": "error",
                "message": "waktu_mulai_reschedule harus lebih kecil dari waktu_selesai_reschedule"
            }, 400

        try:
            ids = reschedule_group_jadwal_v2(id_jadwal, {
                "tanggal_reschedule": data["tanggal_reschedule"],
                "waktu_mulai_reschedule": data["waktu_mulai_reschedule"],
                "waktu_selesai_reschedule": data["waktu_selesai_reschedule"],
                "updated_by": id_user
            })

            if not ids:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            return {
                "status": "success",
                "message": f"{len(ids)} jadwal berhasil di-reschedule",
                "data": {"id_jadwal": ids}
            }, 200

        except SQLAlchemyError as e:
            print(f"[PATCH /jadwal/v2/group/{id_jadwal}/reschedule] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@jadwal_ns.route("/v2/group/switch-mentor")
class JadwalGroupSwitchMentorV2Resource(Resource):

    @role_required("admin")
    @jadwal_ns.expect(switch_mentor_model)
    def patch(self):
        """Akses: admin, [V2] Tukar mentor antar 2 group (berlaku untuk semua jadwal di kedua group)"""

        id_user = get_jwt_identity()
        data = request.get_json(silent=True)

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        id_jadwal_1 = data.get("id_jadwal_1")
        id_jadwal_2 = data.get("id_jadwal_2")

        if id_jadwal_1 is None or id_jadwal_2 is None:
            return {"status": "error", "message": "id_jadwal_1 dan id_jadwal_2 wajib diisi"}, 400

        if id_jadwal_1 == id_jadwal_2:
            return {"status": "error", "message": "id_jadwal_1 dan id_jadwal_2 tidak boleh sama"}, 400

        try:
            result = switch_mentor_group_jadwal_v2(id_jadwal_1, id_jadwal_2, id_user)

            if result is None:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            if result == "SAME_GROUP":
                return {"status": "error", "message": "Kedua jadwal berada di group yang sama"}, 400

            return {
                "status": "success",
                "message": "Mentor berhasil ditukar",
                "data": result
            }, 200

        except SQLAlchemyError as e:
            print(f"[PATCH /jadwal/v2/group/switch-mentor] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


# ============================================================================ #
#          #ANCHOR - JADWAL SATUAN V2 (KELAS / KELOMPOK / KELAS PRIVATE)       #
# ============================================================================ #

private_dropdown_v2_parser = jadwal_ns.parser()
private_dropdown_v2_parser.add_argument("search", type=str, required=False, location="args", help="Cari nama kelas private, mentor, atau peserta")
private_dropdown_v2_parser.add_argument("id_mentor", type=int, required=False, location="args", help="Filter kelas private milik mentor tertentu")


def _parse_jadwal_v2_body(data):
    """Validasi field umum body jadwal v2. Return (payload, error)."""
    if not data:
        return None, ({"status": "error", "message": "Request body tidak boleh kosong"}, 400)

    required_fields = ["id_mentor", "tanggal", "waktu_mulai", "waktu_selesai", "type_pertemuan"]
    missing_fields = [field for field in required_fields if data.get(field) in (None, "")]

    if missing_fields:
        return None, ({"status": "error", "message": f"Field wajib diisi: {', '.join(missing_fields)}"}, 400)

    type_pertemuan = str(data["type_pertemuan"]).upper()

    if type_pertemuan not in ("ONLINE", "OFFLINE"):
        return None, ({"status": "error", "message": "type_pertemuan harus ONLINE atau OFFLINE"}, 400)

    if data["waktu_mulai"] >= data["waktu_selesai"]:
        return None, ({"status": "error", "message": "waktu_mulai harus lebih kecil dari waktu_selesai"}, 400)

    payload = {
        key: (data.get(key) if data.get(key) not in ("", None) else None)
        for key in ("id_paketkelas", "id_kelompok", "id_mentorship")
    }
    payload.update({
        "id_mentor": data["id_mentor"],
        "topik": data.get("topik"),
        "catatan": data.get("catatan"),
        "tanggal": data["tanggal"],
        "waktu_mulai": data["waktu_mulai"],
        "waktu_selesai": data["waktu_selesai"],
        "type_pertemuan": type_pertemuan,
    })

    error = validate_target_jadwal_v2(
        type_pertemuan,
        payload["id_paketkelas"],
        payload["id_kelompok"],
        payload["id_mentorship"],
        payload["id_mentor"]
    )

    return (None, error) if error else (payload, None)


@jadwal_ns.route("/v2/private-dropdown")
class JadwalPrivateDropdownV2Resource(Resource):

    @role_required("admin")
    @jadwal_ns.expect(private_dropdown_v2_parser)
    def get(self):
        """Akses: admin, [V2] Dropdown kelas private (mentorship) aktif untuk form jadwal"""

        args = private_dropdown_v2_parser.parse_args()

        try:
            result = get_mentorship_dropdown_v2(
                search=args.get("search"),
                id_mentor=args.get("id_mentor")
            )

            return {"status": "success", "data": result, "meta": {"total": len(result)}}, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/v2/private-dropdown] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@jadwal_ns.route("/v2")
class JadwalCreateV2Resource(Resource):

    @role_required("admin")
    @jadwal_ns.expect(jadwal_v2_model)
    def post(self):
        """Akses: admin, [V2] Buat 1 jadwal untuk kelas / kelompok / kelas private"""

        id_user = get_jwt_identity()

        try:
            payload, error = _parse_jadwal_v2_body(request.get_json(silent=True))

            if error:
                return error

            result = insert_jadwal_v2({
                **payload,
                "created_by": id_user,
                "updated_by": id_user
            })

            if not result:
                return {"status": "error", "message": "Gagal membuat jadwal"}, 400

            return {"status": "success", "message": "Jadwal berhasil dibuat", "data": result}, 201

        except SQLAlchemyError as e:
            print(f"[POST /jadwal/v2] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@jadwal_ns.route("/v2/<int:id_jadwal>")
class JadwalV2Resource(Resource):

    @role_required("admin")
    def get(self, id_jadwal):
        """Akses: admin, [V2] Detail 1 jadwal (termasuk kelas private)"""

        try:
            result = get_jadwal_by_id_v2(id_jadwal)

            if not result:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            return {"status": "success", "data": result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/v2/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required("admin")
    @jadwal_ns.expect(jadwal_v2_model)
    def put(self, id_jadwal):
        """Akses: admin, [V2] Ubah 1 jadwal, bisa ganti tipe & target (kelas / kelompok / kelas private)"""

        id_user = get_jwt_identity()
        data = request.get_json(silent=True)

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        required_fields = ["id_mentor", "tanggal", "waktu_mulai", "waktu_selesai", "type_pertemuan"]
        missing_fields = [field for field in required_fields if data.get(field) in (None, "")]

        if missing_fields:
            return {"status": "error", "message": f"Field wajib diisi: {', '.join(missing_fields)}"}, 400

        type_pertemuan = str(data["type_pertemuan"]).upper()

        if type_pertemuan not in ("ONLINE", "OFFLINE"):
            return {"status": "error", "message": "type_pertemuan harus ONLINE atau OFFLINE"}, 400

        if data["waktu_mulai"] >= data["waktu_selesai"]:
            return {"status": "error", "message": "waktu_mulai harus lebih kecil dari waktu_selesai"}, 400

        target = {
            key: (data.get(key) if data.get(key) not in ("", None) else None)
            for key in ("id_paketkelas", "id_kelompok", "id_mentorship")
        }

        try:
            existing = get_jadwal_by_id_v2(id_jadwal)

            if not existing:
                return {"status": "error", "message": "Jadwal tidak ditemukan"}, 404

            error = validate_target_jadwal_v2(
                type_pertemuan,
                target["id_paketkelas"],
                target["id_kelompok"],
                target["id_mentorship"],
                data["id_mentor"]
            )

            if error:
                return error

            # Target tidak boleh diganti jika jadwal sudah memiliki data absensi
            target_berubah = any(existing.get(key) != value for key, value in target.items())

            if target_berubah and is_jadwal_has_absensi(id_jadwal):
                return {
                    "status": "error",
                    "message": "Kelas/kelompok tidak dapat diubah karena jadwal sudah memiliki data absensi"
                }, 400

            result = update_jadwal_v2({
                "id_jadwal": id_jadwal,
                **target,
                "id_mentor": data["id_mentor"],
                "topik": data.get("topik"),
                "catatan": data.get("catatan"),
                "tanggal": data["tanggal"],
                "waktu_mulai": data["waktu_mulai"],
                "waktu_selesai": data["waktu_selesai"],
                "type_pertemuan": type_pertemuan,
                "updated_by": id_user
            })

            if not result:
                return {"status": "error", "message": "Gagal mengubah jadwal"}, 400

            return {"status": "success", "message": "Jadwal berhasil diubah", "data": result}, 200

        except SQLAlchemyError as e:
            print(f"[PUT /jadwal/v2/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


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
            "id_mentor", "tanggal",
            "waktu_mulai", "waktu_selesai", "type_pertemuan"
        ]
        missing_fields = [field for field in required_fields if data.get(field) is None]

        if missing_fields:
            return {
                "status": "error",
                "message": f"Field wajib diisi: {', '.join(missing_fields)}"
            }, 400

        id_paketkelas = data.get("id_paketkelas")
        id_kelompok = data.get("id_kelompok")
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

            error = validate_target_jadwal(
                type_pertemuan,
                id_paketkelas,
                id_kelompok,
                id_mentor
            )

            if error:
                return error

            # ==========================================
            # Target (kelas/kelompok) tidak boleh diganti
            # jika jadwal sudah memiliki data absensi
            # ==========================================

            target_berubah = (
                existing.get("id_paketkelas") != id_paketkelas
                or existing.get("id_kelompok") != id_kelompok
            )

            if target_berubah and is_jadwal_has_absensi(id_jadwal):
                return {
                    "status": "error",
                    "message": (
                        "Kelas/kelompok tidak dapat diubah karena "
                        "jadwal sudah memiliki data absensi"
                    )
                }, 400

            result = update_jadwal({
                "id_jadwal": id_jadwal,
                "id_paketkelas": id_paketkelas,
                "id_kelompok": id_kelompok,
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



@jadwal_ns.route("/switch-mentor")
class JadwalSwitchMentorResource(Resource):

    @role_required(["admin", "mentor"])
    @jadwal_ns.expect(switch_mentor_model)
    def patch(self):
        """Akses: admin/mentor, Menukar mentor antar jadwal"""

        id_user = get_jwt_identity()
        role = get_jwt()["role"]
        data = request.get_json()

        if not data:
            return {
                "status": "error",
                "message": "Request body tidak boleh kosong"
            }, 400

        id_jadwal_1 = data.get("id_jadwal_1")
        id_jadwal_2 = data.get("id_jadwal_2")

        if id_jadwal_1 is None or id_jadwal_2 is None:
            return {
                "status": "error",
                "message": (
                    "id_jadwal_1 dan id_jadwal_2 wajib diisi"
                )
            }, 400

        if id_jadwal_1 == id_jadwal_2:
            return {
                "status": "error",
                "message": (
                    "id_jadwal_1 dan id_jadwal_2 "
                    "tidak boleh sama"
                )
            }, 400

        try:
            result = switch_mentor_jadwal(
                id_jadwal_1,
                id_jadwal_2,
                id_user,
                role
            )

            if not result:
                if role == "mentor":
                    return {
                        "status": "error",
                        "message": (
                            "Jadwal tidak ditemukan atau "
                            "bukan jadwal mentor"
                        )
                    }, 404

                return {
                    "status": "error",
                    "message": "Jadwal tidak ditemukan"
                }, 404

            return {
                "status": "success",
                "message": "Mentor berhasil ditukar",
                "data": result
            }, 200

        except SQLAlchemyError as e:
            print(
                f"[PATCH /jadwal/switch-mentor] Error: {e}"
            )

            return {
                "status": "error",
                "message": "Internal server error"
            }, 500



# ============================================================================ #
#                        #ANCHOR - JADWAL MILIK PESERTA                        #
# ============================================================================ #

@jadwal_ns.route("/peserta")
class JadwalPesertaResource(Resource):

    @role_required("peserta")
    @jadwal_ns.expect(jadwal_peserta_parser)
    def get(self):
        """
        Akses: peserta

        Mengambil jadwal milik peserta yang sedang login:
        - jadwal dari kelas yang diikuti
        - jadwal dari kelompok belajar yang diikuti (offline)

        Response menyertakan status_absensi_mentor dan status_absensi_saya
        untuk menentukan kapan tombol check-in ditampilkan.
        """

        id_user = get_jwt_identity()

        try:
            args = jadwal_peserta_parser.parse_args()

            start_date, end_date, error = resolve_periode(
                args.get("start_date"),
                args.get("end_date")
            )

            if error:
                return error

            result = get_all_jadwal_by_peserta(
                id_peserta=id_user,
                start_date=start_date,
                end_date=end_date
            )

            return {
                "status": "success",
                "data": result,
                "meta": {
                    "total": len(result),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/peserta] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@jadwal_ns.route("/wali-kelas")
class JadwalWaliKelasResource(Resource):

    @role_required("mentor")
    @jadwal_ns.expect(jadwal_wali_kelas_parser)
    def get(self):
        """
        Akses: mentor (wali kelas)

        Mengambil jadwal seluruh kelas yang diwalikan oleh mentor yang sedang login.

        Filter:
        - default: bulan berjalan (tanggal 1 s/d akhir bulan)
        - bulan=YYYY-MM
        - start_date & end_date (YYYY-MM-DD), mengabaikan filter bulan
        - id_paketkelas: hanya kelas yang diwalikan
        """

        id_user = get_jwt_identity()

        try:
            args = jadwal_wali_kelas_parser.parse_args()
            id_paketkelas = args.get("id_paketkelas")

            periode, error = resolve_periode_wali_kelas(
                args.get("bulan"),
                args.get("start_date"),
                args.get("end_date")
            )

            if error:
                return error

            if id_paketkelas is not None and not is_wali_kelas(id_user, id_paketkelas):
                return {
                    "status": "error",
                    "message": "Kelas tidak ditemukan atau Anda bukan wali kelas tersebut"
                }, 404

            result = get_all_jadwal_by_wali_kelas(
                id_wali_kelas=id_user,
                start_date=periode["start_date"],
                end_date=periode["end_date"],
                id_paketkelas=id_paketkelas,
                search=args.get("search")
            )

            return {
                "status": "success",
                "data": result["data"],
                "meta": {
                    "filter": periode["filter"],
                    "bulan": periode["bulan"],
                    "start_date": periode["start_date"].isoformat(),
                    "end_date": periode["end_date"].isoformat(),
                    "id_paketkelas": id_paketkelas,
                    "total": len(result["data"]),
                    "total_kelas": result["total_kelas"],
                    "per_tanggal": result["per_tanggal"]
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/wali-kelas] Error: {e}")
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

        except ValueError as e:
            return {
                "status": "error",
                "message": str(e)
            }, 400

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
    def delete(self, import_id):
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


# ============================================================================ #
#                     #ANCHOR - TUKAR JADWAL ANTAR MENTOR                      #
# ============================================================================ #

from .query import q_jadwal_tukar as qt


tukar_request_model = jadwal_ns.model("TukarJadwalRequest", {
    "id_jadwal_asal": fields.Integer(required=True, description="Salah satu ID jadwal dari grup milik Anda"),
    "id_jadwal_tujuan": fields.Integer(required=True, description="Salah satu ID jadwal dari grup milik mentor tujuan"),
    "alasan": fields.String(required=False, description="Alasan pengajuan (maks. 500 karakter)")
})

tukar_respon_model = jadwal_ns.model("TukarJadwalRespon", {
    "catatan_respon": fields.String(required=False, description="Catatan untuk pengaju (maks. 500 karakter)")
})


tukar_kandidat_parser = jadwal_ns.parser()
tukar_kandidat_parser.add_argument("id_jadwal", type=int, required=True, location="args", help="Salah satu ID jadwal dari grup milik Anda")
tukar_kandidat_parser.add_argument("tanggal", type=str, required=False, location="args", help="Filter tanggal grup kandidat (YYYY-MM-DD). Default: hari ini s.d. 14 hari ke depan")
tukar_kandidat_parser.add_argument("id_mentor", type=int, required=False, location="args", help="Filter kandidat milik mentor tertentu")
tukar_kandidat_parser.add_argument("search", type=str, required=False, location="args", help="Cari nama mentor, kelas, atau kelompok")

tukar_list_parser = jadwal_ns.parser()
tukar_list_parser.add_argument("tipe", type=str, required=False, default="semua", location="args", help="masuk / keluar / semua (khusus mentor)")
tukar_list_parser.add_argument("status", type=str, required=False, location="args", help="PENDING / DITERIMA / DITOLAK / DIBATALKAN / KADALUARSA")
tukar_list_parser.add_argument("id_mentor", type=int, required=False, location="args", help="Khusus admin: filter mentor pengaju/tujuan")
tukar_list_parser.add_argument("page", type=int, required=False, default=1, location="args", help="Halaman")
tukar_list_parser.add_argument("per_page", type=int, required=False, default=20, location="args", help="Jumlah data per halaman, maksimum 100")

tukar_log_parser = jadwal_ns.parser()
tukar_log_parser.add_argument("id_request", type=int, required=False, location="args", help="Log untuk satu request")
tukar_log_parser.add_argument("id_mentor", type=int, required=False, location="args", help="Request yang melibatkan mentor ini")
tukar_log_parser.add_argument("aksi", type=str, required=False, location="args", help="DIAJUKAN / DITERIMA / DITOLAK / DIBATALKAN / KADALUARSA")
tukar_log_parser.add_argument("start_date", type=str, required=False, location="args", help="Tanggal awal (YYYY-MM-DD)")
tukar_log_parser.add_argument("end_date", type=str, required=False, location="args", help="Tanggal akhir (YYYY-MM-DD)")
tukar_log_parser.add_argument("page", type=int, required=False, default=1, location="args", help="Halaman")
tukar_log_parser.add_argument("per_page", type=int, required=False, default=20, location="args", help="Jumlah data per halaman, maksimum 100")


TUKAR_AKSI = ("DIAJUKAN",) + qt.STATUS_TUKAR[1:]


def _tukar_error(message, code):
    return {"status": "error", "message": message}, code


def _validate_paging(page, per_page):
    if page is None or page < 1:
        return _tukar_error("Parameter page harus lebih besar dari 0", 400)
    if per_page is None or not 1 <= per_page <= 100:
        return _tukar_error("Parameter per_page harus berada antara 1 dan 100", 400)
    return None


def _parse_date(value, field):
    if not value:
        return None, None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except ValueError:
        return None, _tukar_error(f"Format {field} harus YYYY-MM-DD", 400)


def _clean_text(value, field, max_len=500):
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, _tukar_error(f"{field} harus berupa teks", 400)
    value = value.strip()
    if len(value) > max_len:
        return None, _tukar_error(f"{field} maksimal {max_len} karakter", 400)
    return value or None, None


@jadwal_ns.route("/tukar/kandidat")
class JadwalTukarKandidatResource(Resource):

    @role_required("mentor")
    @jadwal_ns.expect(tukar_kandidat_parser)
    def get(self):
        """Akses: mentor, Daftar grup jadwal mentor lain yang bisa ditukar dengan grup milik Anda"""

        id_user = int(get_jwt_identity())
        args = tukar_kandidat_parser.parse_args()

        tanggal, err = _parse_date(args.get("tanggal"), "tanggal")
        if err:
            return err

        try:
            result = qt.get_kandidat_tukar(
                id_mentor=id_user,
                id_jadwal=args["id_jadwal"],
                tanggal=tanggal,
                filter_mentor=args.get("id_mentor"),
                search=args.get("search"),
            )
            return {"status": "success", "data": result}, 200

        except qt.TukarError as e:
            return _tukar_error(e.message, e.code)

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/tukar/kandidat] Error: {e}")
            return _tukar_error("Internal server error", 500)


@jadwal_ns.route("/tukar")
class JadwalTukarListResource(Resource):

    @role_required("mentor")
    @jadwal_ns.expect(tukar_request_model)
    def post(self):
        """Akses: mentor, Mengajukan tukar grup jadwal dengan mentor lain"""

        id_user = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}

        id_asal = data.get("id_jadwal_asal")
        id_tujuan = data.get("id_jadwal_tujuan")

        if not isinstance(id_asal, int) or not isinstance(id_tujuan, int):
            return _tukar_error("id_jadwal_asal dan id_jadwal_tujuan wajib diisi dengan angka", 400)

        if id_asal == id_tujuan:
            return _tukar_error("id_jadwal_asal dan id_jadwal_tujuan tidak boleh sama", 400)

        alasan, err = _clean_text(data.get("alasan"), "alasan")
        if err:
            return err

        try:
            result = qt.create_tukar_request(id_user, id_asal, id_tujuan, alasan)
            return {
                "status": "success",
                "message": "Request tukar jadwal berhasil dikirim",
                "data": result
            }, 201

        except qt.TukarError as e:
            return _tukar_error(e.message, e.code)

        except SQLAlchemyError as e:
            print(f"[POST /jadwal/tukar] Error: {e}")
            return _tukar_error("Internal server error", 500)

    @role_required(["admin", "mentor"])
    @jadwal_ns.expect(tukar_list_parser)
    def get(self):
        """Akses: admin/mentor, Daftar request tukar jadwal (mentor: masuk/keluar, admin: semua)"""

        id_user = int(get_jwt_identity())
        role = get_jwt()["role"]
        args = tukar_list_parser.parse_args()

        tipe = (args.get("tipe") or "semua").lower()
        status = (args.get("status") or "").upper() or None

        if tipe not in ("masuk", "keluar", "semua"):
            return _tukar_error("Parameter tipe harus masuk, keluar, atau semua", 400)

        if status and status not in qt.STATUS_TUKAR:
            return _tukar_error(f"Parameter status harus salah satu dari {', '.join(qt.STATUS_TUKAR)}", 400)

        err = _validate_paging(args.get("page"), args.get("per_page"))
        if err:
            return err

        try:
            result = qt.get_tukar_requests(
                id_user=id_user,
                role=role,
                tipe=tipe,
                status=status,
                id_mentor=args.get("id_mentor") if role == "admin" else None,
                page=args["page"],
                per_page=args["per_page"],
            )
            return {"status": "success", **result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/tukar] Error: {e}")
            return _tukar_error("Internal server error", 500)


@jadwal_ns.route("/tukar/log")
class JadwalTukarLogResource(Resource):

    @role_required("admin")
    @jadwal_ns.expect(tukar_log_parser)
    def get(self):
        """Akses: admin, Riwayat aksi semua request tukar jadwal"""

        args = tukar_log_parser.parse_args()
        aksi = (args.get("aksi") or "").upper() or None

        if aksi and aksi not in TUKAR_AKSI:
            return _tukar_error(f"Parameter aksi harus salah satu dari {', '.join(TUKAR_AKSI)}", 400)

        start_date, err = _parse_date(args.get("start_date"), "start_date")
        if err:
            return err

        end_date, err = _parse_date(args.get("end_date"), "end_date")
        if err:
            return err

        if start_date and end_date and start_date > end_date:
            return _tukar_error("start_date tidak boleh lebih besar dari end_date", 400)

        err = _validate_paging(args.get("page"), args.get("per_page"))
        if err:
            return err

        try:
            result = qt.get_tukar_logs(
                id_request=args.get("id_request"),
                id_mentor=args.get("id_mentor"),
                aksi=aksi,
                start_date=start_date,
                end_date=end_date,
                page=args["page"],
                per_page=args["per_page"],
            )
            return {"status": "success", **result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/tukar/log] Error: {e}")
            return _tukar_error("Internal server error", 500)


@jadwal_ns.route("/tukar/<int:id_request>")
class JadwalTukarDetailResource(Resource):

    @role_required(["admin", "mentor"])
    def get(self, id_request):
        """Akses: admin/mentor, Detail request tukar beserta isi kedua grup (admin: termasuk log)"""

        id_user = int(get_jwt_identity())
        role = get_jwt()["role"]

        try:
            result = qt.get_tukar_request_detail(id_request, id_user, role)

            if not result:
                return _tukar_error("Request tukar jadwal tidak ditemukan", 404)

            return {"status": "success", "data": result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /jadwal/tukar/{id_request}] Error: {e}")
            return _tukar_error("Internal server error", 500)


@jadwal_ns.route("/tukar/<int:id_request>/terima")
class JadwalTukarTerimaResource(Resource):

    @role_required("mentor")
    @jadwal_ns.expect(tukar_respon_model)
    def patch(self, id_request):
        """Akses: mentor tujuan, Menerima request tukar (jadwal langsung ditukar)"""

        id_user = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}

        catatan, err = _clean_text(data.get("catatan_respon"), "catatan_respon")
        if err:
            return err

        try:
            result = qt.accept_tukar_request(id_request, id_user, catatan)
            return {"status": "success", "message": "Tukar jadwal berhasil", "data": result}, 200

        except qt.TukarError as e:
            return _tukar_error(e.message, e.code)

        except SQLAlchemyError as e:
            print(f"[PATCH /jadwal/tukar/{id_request}/terima] Error: {e}")
            return _tukar_error("Internal server error", 500)


@jadwal_ns.route("/tukar/<int:id_request>/tolak")
class JadwalTukarTolakResource(Resource):

    @role_required("mentor")
    @jadwal_ns.expect(tukar_respon_model)
    def patch(self, id_request):
        """Akses: mentor tujuan, Menolak request tukar"""

        id_user = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}

        catatan, err = _clean_text(data.get("catatan_respon"), "catatan_respon")
        if err:
            return err

        try:
            result = qt.reject_tukar_request(id_request, id_user, catatan)
            return {"status": "success", "message": "Request tukar jadwal ditolak", "data": result}, 200

        except qt.TukarError as e:
            return _tukar_error(e.message, e.code)

        except SQLAlchemyError as e:
            print(f"[PATCH /jadwal/tukar/{id_request}/tolak] Error: {e}")
            return _tukar_error("Internal server error", 500)


@jadwal_ns.route("/tukar/<int:id_request>/batal")
class JadwalTukarBatalResource(Resource):

    @role_required("mentor")
    def patch(self, id_request):
        """Akses: mentor pengaju, Membatalkan request tukar yang masih PENDING"""

        id_user = int(get_jwt_identity())

        try:
            result = qt.cancel_tukar_request(id_request, id_user)
            return {"status": "success", "message": "Request tukar jadwal dibatalkan", "data": result}, 200

        except qt.TukarError as e:
            return _tukar_error(e.message, e.code)

        except SQLAlchemyError as e:
            print(f"[PATCH /jadwal/tukar/{id_request}/batal] Error: {e}")
            return _tukar_error("Internal server error", 500)
