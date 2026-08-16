import requests
from flask import request
from werkzeug.datastructures import FileStorage
from flask_jwt_extended import get_jwt_identity, get_jwt
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError

from .utils.watermark import add_watermark
from .utils.helper import calculate_distance_meter
from .utils.decorator import role_required
from .query.q_absensi import *
from .utils.config import CDN_API_KEY, CDN_UPLOAD_URL


absensi_ns = Namespace("absensi", description="Manajemen Absensi")


# ============================================================================ #
#                                #ANCHOR - MODEL                               #
# ============================================================================ #

absensi_peserta_update_model = absensi_ns.model(
    "AbsensiPesertaUpdate",
    {
        "status_kehadiran": fields.String(
            required=True,
            description="Status kehadiran peserta",
            enum=["HADIR", "IZIN", "SAKIT", "ALPHA"])
    }
)


mentor_absensi_peserta_model = absensi_ns.model(
    "MentorAbsensiPeserta",
    {
        "id_jadwal": fields.Integer( required=True, description="ID jadwal"),
        "id_peserta": fields.Integer( required=True, description="ID peserta"),
        "status_kehadiran": fields.String(
            required=True,
            description="Status kehadiran peserta",
            enum=["HADIR", "IZIN", "SAKIT", "ALPHA"]
        )
    }
)


mentor_absensi_peserta_update_model = absensi_ns.model(
    "MentorAbsensiPesertaUpdate",
    {
        "status_kehadiran": fields.String(
            required=True,
            description="Status kehadiran peserta",
            enum=["HADIR", "IZIN", "SAKIT", "ALPHA"]
        )
    }
)



# ============================================================================ #
#                                #ANCHOR - PARSER                              #
# ============================================================================ #

mentor_checkin_parser = absensi_ns.parser()
mentor_checkin_parser.add_argument("id_jadwal", type=int, required=True, location="form", help="ID jadwal yang akan dilakukan check-in")
mentor_checkin_parser.add_argument("latitude", type=float, required=False, location="form", help="Latitude lokasi mentor")
mentor_checkin_parser.add_argument("longitude", type=float, required=False, location="form", help="Longitude lokasi mentor")
mentor_checkin_parser.add_argument("accuracy", type=float, required=False, location="form", help="Akurasi GPS dalam meter")
mentor_checkin_parser.add_argument("evidence_url", type=FileStorage, location="files", required=False, help="Foto evidence check-in")

mentor_checkout_parser = absensi_ns.parser()
mentor_checkout_parser.add_argument("id_jadwal", type=int, required=True, location="form", help="ID jadwal yang akan dilakukan check-out")
mentor_checkout_parser.add_argument("latitude", type=float, required=False, location="form", help="Latitude lokasi mentor")
mentor_checkout_parser.add_argument("longitude", type=float, required=False, location="form", help="Longitude lokasi mentor")
mentor_checkout_parser.add_argument("accuracy", type=float, required=False, location="form", help="Akurasi GPS dalam meter")
mentor_checkout_parser.add_argument("evidence", type=FileStorage, location="files", required=False, help="Foto evidence check-out")

kelas_peserta_parser = absensi_ns.parser()
kelas_peserta_parser.add_argument("id_paketkelas", type=int, required=True, location="args", help="ID paket kelas")



# ============================================================================ #
#                            #ANCHOR - ABSENSI MENTOR                          #
# ============================================================================ #

@absensi_ns.route("/mentor")
class AbsensiMentorListResource(Resource):

    @role_required("admin")
    def get(self):
        """Akses: admin, Mengambil seluruh absensi mentor"""

        try:
            result = get_all_absensi_mentor()

            return {
                "status": "success",
                "data": result,
                "meta": {"total": len(result)}
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /absensi/mentor] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@absensi_ns.route("/mentor/<int:id_absensi>")
class AbsensiMentorResource(Resource):

    @role_required("admin")
    def get(self, id_absensi):
        """Akses: admin, Mengambil detail absensi mentor"""

        try:
            result = get_absensi_mentor_by_id(id_absensi)

            if not result:
                return {
                    "status": "error",
                    "message": "Absensi mentor tidak ditemukan"
                }, 404

            return {"status": "success", "data": result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /absensi/mentor/{id_absensi}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@absensi_ns.route("/mentor/check-in")
class AbsensiMentorCheckInResource(Resource):

    @role_required("mentor")
    @absensi_ns.expect(mentor_checkin_parser)
    def post(self):
        """Akses: mentor, Melakukan check-in"""

        id_mentor = get_jwt_identity()
        data = mentor_checkin_parser.parse_args()
        id_jadwal = data.get("id_jadwal")
        
        user = get_user_nickname(id_mentor)

        if not user:
            return {
                "status": "error",
                "message": "Data mentor tidak ditemukan"
            }, 404

        nickname = user["nickname"] or user["nama"]

        if not id_jadwal:
            return {"status": "error", "message": "id_jadwal wajib diisi"}, 400

        try:
            jadwal = get_jadwal_absensi_mentor(id_jadwal, id_mentor)

            if not jadwal:
                return {
                    "status": "error",
                    "message": "Jadwal tidak ditemukan atau bukan jadwal mentor"
                }, 404

            if jadwal["sudah_check_in"]:
                return {"status": "error", "message": "Mentor sudah melakukan check-in"}, 400

            latitude = data.get("latitude")
            longitude = data.get("longitude")
            accuracy = data.get("accuracy")
            image_file = data.get("evidence_url")

            if jadwal["type_pertemuan"] == "OFFLINE":
                if latitude is None or longitude is None:
                    return {
                        "status": "error",
                        "message": (
                            "Latitude dan longitude wajib "
                            "untuk pertemuan offline"
                        )
                    }, 400

                if accuracy is None:
                    return {
                        "status": "error",
                        "message": (
                            "Accuracy GPS wajib "
                            "untuk pertemuan offline"
                        )
                    }, 400

                if not image_file:
                    return {
                        "status": "error",
                        "message": (
                            "Evidence check-in wajib "
                            "untuk pertemuan offline"
                        )
                    }, 400

            evidence_url = None

            if image_file:
                try:
                    now = get_wib()

                    watermarked_file, filename, mimetype = add_watermark(
                        image_file=image_file,
                        watermark_text=f"CHECK-IN ({nickname.upper()})",
                        date_text=now.strftime("%d %B %Y"),
                        time_text=now.strftime("%H:%M:%S WIB"),
                        latitude=latitude,
                        longitude=longitude,
                    )

                except ValueError as e:
                    return {
                        "status": "error",
                        "message": (
                            f"Gagal memproses evidence: {str(e)}"
                        )
                    }, 400

                try:
                    cdn_response = requests.post(
                        f"{CDN_UPLOAD_URL}/absensi",
                        headers={
                            "X-API-KEY": CDN_API_KEY,
                        },
                        files={
                            "file": (
                                filename,
                                watermarked_file,
                                mimetype,
                            )
                        },
                    )

                except requests.RequestException as e:
                    print(
                        "[POST /absensi/mentor/check-in] "
                        f"CDN Error: {e}"
                    )

                    return {
                        "status": "error",
                        "message": "Gagal menghubungi CDN"
                    }, 500

                if not cdn_response.ok:
                    return {
                        "status": "error",
                        "message": (
                            "Gagal mengupload evidence ke CDN"
                        ),
                        "detail": cdn_response.text,
                    }, 400

                try:
                    cdn_data = cdn_response.json()

                except ValueError:
                    return {
                        "status": "error",
                        "message": (
                            "Response CDN tidak valid"
                        ),
                    }, 400

                evidence_url = cdn_data.get("url")

                if not evidence_url:
                    return {
                        "status": "error",
                        "message": (
                            "CDN tidak mengembalikan URL gambar"
                        ),
                    }, 400

            result = insert_absensi_mentor_checkin({
                "id_jadwal": id_jadwal,
                "id_mentor": id_mentor,
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": accuracy,
                "evidence_url": evidence_url,
            })

            if not result:
                return {"status": "error", "message": "Gagal melakukan check-in"}, 400

            return {
                "status": "success",
                "message": "Check-in berhasil",
                "data": result
            }, 201

        except SQLAlchemyError as e:
            print(f"[POST /absensi/mentor/check-in] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500

        except requests.RequestException as e:
            print(f"[POST /absensi/mentor/check-in] CDN Error: {e}")
            return {"status": "error", "message": "Gagal menghubungi CDN"}, 500


@absensi_ns.route("/mentor/check-out")
class AbsensiMentorCheckOutResource(Resource):

    @role_required("mentor")
    @absensi_ns.expect(mentor_checkout_parser)
    def post(self):
        """Akses: mentor, Melakukan check-out"""

        id_mentor = get_jwt_identity()
        data = mentor_checkout_parser.parse_args()
        id_jadwal = data.get("id_jadwal")

        user = get_user_nickname(id_mentor)

        if not user:
            return {
                "status": "error",
                "message": "Data mentor tidak ditemukan"
            }, 404

        nickname = user["nickname"] or user["nama"]
        
        if not id_jadwal:
            return {"status": "error", "message": "id_jadwal wajib diisi"}, 400

        try:
            absensi = get_absensi_mentor_for_checkout(id_jadwal, id_mentor)

            if not absensi:
                return {"status": "error", "message": "Data absensi tidak ditemukan"}, 404

            if not absensi["check_in_at"]:
                return {"status": "error", "message": "Mentor belum melakukan check-in"}, 400

            if absensi["check_out_at"]:
                return {"status": "error", "message": "Mentor sudah melakukan check-out"}, 400

            latitude = data.get("latitude")
            longitude = data.get("longitude")
            accuracy = data.get("accuracy")
            image_file = data.get("evidence")

            if absensi["type_pertemuan"] == "OFFLINE":
                if latitude is None or longitude is None:
                    return {
                        "status": "error",
                        "message": "Latitude dan longitude wajib untuk pertemuan offline"
                    }, 400

                if accuracy is None:
                    return {
                        "status": "error",
                        "message": "Accuracy GPS wajib untuk pertemuan offline"
                    }, 400

                if not image_file:
                    return {
                        "status": "error",
                        "message": "Evidence check-out wajib untuk pertemuan offline"
                    }, 400

                check_in_latitude = absensi["check_in_latitude"]
                check_in_longitude = absensi["check_in_longitude"]
                check_in_accuracy = absensi["check_in_accuracy"]

                if check_in_latitude is not None and check_in_longitude is not None:
                    distance = calculate_distance_meter(
                        check_in_latitude,
                        check_in_longitude,
                        latitude,
                        longitude
                    )

                    if check_in_accuracy is not None and distance > check_in_accuracy:
                        return {
                            "status": "error",
                            "message": "Lokasi checkout berada di luar radius lokasi check-in",
                            "data": {
                                "distance": round(distance, 2),
                                "radius": check_in_accuracy
                            }
                        }, 400

            evidence_url = None

            if image_file:
                try:
                    now = get_wib()

                    watermarked_file, filename, mimetype = add_watermark(
                        image_file=image_file,
                        watermark_text=f"CHECK-IN ({nickname.upper()})",
                        date_text=now.strftime("%d %B %Y"),
                        time_text=now.strftime("%H:%M:%S WIB"),
                        latitude=latitude,
                        longitude=longitude,
                    )

                except ValueError as e:
                    return {
                        "status": "error",
                        "message": (
                            f"Gagal memproses evidence: {str(e)}"
                        )
                    }, 400

                try:
                    cdn_response = requests.post(
                        f"{CDN_UPLOAD_URL}/absensi",
                        headers={
                            "X-API-KEY": CDN_API_KEY,
                        },
                        files={
                            "file": (
                                filename,
                                watermarked_file,
                                mimetype,
                            )
                        },
                    )

                except requests.RequestException as e:
                    print(
                        "[POST /absensi/mentor/check-in] "
                        f"CDN Error: {e}"
                    )

                    return {
                        "status": "error",
                        "message": "Gagal menghubungi CDN"
                    }, 500

                if not cdn_response.ok:
                    return {
                        "status": "error",
                        "message": (
                            "Gagal mengupload evidence ke CDN"
                        ),
                        "detail": cdn_response.text,
                    }, 400

                try:
                    cdn_data = cdn_response.json()

                except ValueError:
                    return {
                        "status": "error",
                        "message": (
                            "Response CDN tidak valid"
                        ),
                    }, 400

                evidence_url = cdn_data.get("url")

                if not evidence_url:
                    return {
                        "status": "error",
                        "message": (
                            "CDN tidak mengembalikan URL gambar"
                        ),
                    }, 400

            result = update_absensi_mentor_checkout({
                "id_absensi_mentor": absensi["id_absensi_mentor"],
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": accuracy,
                "evidence_url": evidence_url
            })

            if not result:
                return {"status": "error", "message": "Gagal melakukan check-out"}, 400

            return {
                "status": "success",
                "message": "Check-out berhasil",
                "data": result
            }, 200

        except SQLAlchemyError as e:
            print(f"[POST /absensi/mentor/check-out] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500

        except requests.RequestException as e:
            print(f"[POST /absensi/mentor/check-out] CDN Error: {e}")
            return {"status": "error", "message": "Gagal menghubungi CDN"}, 500



# ============================================================================ #
#                           #ANCHOR - ABSENSI PESERTA                          #
# ============================================================================ #

@absensi_ns.route("/peserta")
class AbsensiPesertaListResource(Resource):

    # @role_required(["admin", "mentor"])
    # def get(self):
    #     """Akses: admin/mentor, Mengambil absensi peserta"""

    #     id_user = get_jwt_identity()

    #     try:
    #         role = get_jwt()["role"]

    #         if role == "admin":
    #             result = get_all_absensi_peserta()
    #         else:
    #             result = get_all_absensi_peserta_by_mentor(id_user)

    #         return {
    #             "status": "success",
    #             "data": result,
    #             "meta": {
    #                 "total": len(result)
    #             }
    #         }, 200

    #     except SQLAlchemyError as e:
    #         print(f"[GET /absensi/peserta] Error: {e}")
    #         return {
    #             "status": "error",
    #             "message": "Internal server error"
    #         }, 500


    @role_required("mentor")
    @absensi_ns.expect(mentor_absensi_peserta_model)
    def post(self):
        """Akses: mentor, Menambahkan absensi peserta secara manual"""

        id_mentor = get_jwt_identity()
        data = request.get_json()

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        required_fields = ["id_jadwal", "id_peserta", "status_kehadiran"]
        missing_fields = [field for field in required_fields if data.get(field) is None]

        if missing_fields:
            return {
                "status": "error",
                "message": f"Field wajib diisi: {', '.join(missing_fields)}"
            }, 400

        status_kehadiran = data["status_kehadiran"].upper()
        allowed_status = ["HADIR", "IZIN", "SAKIT", "ALPHA"]

        if status_kehadiran not in allowed_status:
            return {
                "status": "error",
                "message": "status_kehadiran harus HADIR, IZIN, SAKIT, atau ALPHA"
            }, 400

        try:
            jadwal = get_jadwal_for_manual_attendance(data["id_jadwal"], id_mentor)

            if not jadwal:
                return {
                    "status": "error",
                    "message": "Jadwal tidak ditemukan atau bukan jadwal mentor"
                }, 404

            peserta = get_peserta_for_manual_attendance(
                data["id_peserta"],
                jadwal["id_paketkelas"]
            )

            if not peserta:
                return {
                    "status": "error",
                    "message": "Peserta tidak terdaftar pada kelas tersebut"
                }, 404

            existing = get_absensi_peserta_by_jadwal_peserta(
                data["id_jadwal"],
                data["id_peserta"]
            )

            if existing:
                return {
                    "status": "error",
                    "message": "Peserta sudah memiliki data absensi pada jadwal tersebut"
                }, 409

            result = insert_absensi_peserta_manual({
                "id_jadwal": data["id_jadwal"],
                "id_peserta": data["id_peserta"],
                "status_kehadiran": status_kehadiran
            })

            if not result:
                return {
                    "status": "error",
                    "message": "Gagal menambahkan absensi peserta"
                }, 400

            return {
                "status": "success",
                "message": "Absensi peserta berhasil ditambahkan",
                "data": result
            }, 201

        except SQLAlchemyError as e:
            print(f"[POST /absensi/peserta] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@absensi_ns.route("/peserta/<int:id_absensi>")
class AbsensiPesertaResource(Resource):

    @role_required(["admin", "mentor"])
    def get(self, id_absensi):
        """Akses: admin/mentor, Mengambil detail absensi peserta"""

        id_user = get_jwt_identity()

        try:
            role = get_jwt()["role"]

            if role == "admin":
                result = get_absensi_peserta_by_id(id_absensi)
            else:
                result = get_absensi_peserta_by_id_mentor(id_absensi, id_user)

            if not result:
                return {
                    "status": "error",
                    "message": "Absensi peserta tidak ditemukan"
                }, 404

            return {"status": "success", "data": result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /absensi/peserta/{id_absensi}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required(["admin", "mentor"])
    @absensi_ns.expect(mentor_absensi_peserta_update_model)
    def patch(self, id_absensi):
        """Akses: admin/mentor, Mengubah status kehadiran peserta"""

        id_user = get_jwt_identity()
        data = request.get_json()

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        status_kehadiran = data.get("status_kehadiran")

        if not status_kehadiran:
            return {"status": "error", "message": "status_kehadiran wajib diisi"}, 400

        status_kehadiran = status_kehadiran.upper()
        allowed_status = ["HADIR", "IZIN", "SAKIT", "ALPHA"]

        if status_kehadiran not in allowed_status:
            return {
                "status": "error",
                "message": "status_kehadiran harus HADIR, IZIN, SAKIT, atau ALPHA"
            }, 400

        try:
            role = get_jwt()["role"]

            if role == "admin":
                existing = get_absensi_peserta_by_id(id_absensi)
            else:
                existing = get_absensi_peserta_by_id_mentor(id_absensi, id_user)

            if not existing:
                return {
                    "status": "error",
                    "message": "Absensi peserta tidak ditemukan"
                }, 404

            payload = {
                "id_absensi_peserta": id_absensi,
                "status_kehadiran": status_kehadiran
            }

            if role == "admin":
                result = update_absensi_peserta(payload)
            else:
                result = update_absensi_peserta_by_mentor({
                    **payload,
                    "id_mentor": id_user
                })

            if not result:
                return {
                    "status": "error",
                    "message": "Gagal mengubah absensi peserta"
                }, 400

            return {
                "status": "success",
                "message": "Absensi peserta berhasil diubah",
                "data": result
            }, 200

        except SQLAlchemyError as e:
            print(f"[PATCH /absensi/peserta/{id_absensi}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required("mentor")
    def delete(self, id_absensi):
        """Akses: mentor, Soft delete absensi peserta"""

        id_mentor = get_jwt_identity()

        try:
            existing = get_absensi_peserta_by_id_mentor(id_absensi, id_mentor)

            if not existing:
                return {
                    "status": "error",
                    "message": "Absensi peserta tidak ditemukan"
                }, 404

            result = delete_absensi_peserta_by_mentor(id_absensi, id_mentor)

            if not result:
                return {
                    "status": "error",
                    "message": "Gagal menghapus absensi peserta"
                }, 400

            return {
                "status": "success",
                "message": "Absensi peserta berhasil dihapus"
            }, 200

        except SQLAlchemyError as e:
            print(f"[DELETE /absensi/peserta/{id_absensi}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


@absensi_ns.route("/peserta/<int:id_jadwal>")
class AbsensiPesertaByJadwalResource(Resource):

    @role_required(["admin", "mentor"])
    def get(self, id_jadwal):
        """Akses: admin/mentor, Mengambil absensi peserta berdasarkan jadwal"""

        id_user = get_jwt_identity()

        try:
            role = get_jwt()["role"]

            if role == "admin":
                jadwal = get_jadwal_absensi_peserta(id_jadwal)
                error_message = "Jadwal tidak ditemukan"
            else:
                jadwal = get_jadwal_absensi_peserta_by_mentor(id_jadwal, id_user)
                error_message = "Jadwal tidak ditemukan atau bukan jadwal mentor"

            if not jadwal:
                return {"status": "error", "message": error_message}, 404

            result = get_absensi_peserta_by_jadwal(id_jadwal)

            return {
                "status": "success",
                "data": result,
                "meta": {
                    "total": len(result),
                    "hadir": sum(row["status_kehadiran"] == "HADIR" for row in result),
                    "izin": sum(row["status_kehadiran"] == "IZIN" for row in result),
                    "sakit": sum(row["status_kehadiran"] == "SAKIT" for row in result),
                    "alpha": sum(row["status_kehadiran"] == "ALPHA" for row in result)
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /absensi/jadwal/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500




# ============================================================================ #
#                      #ANCHOR - PESERTA BERDASARKAN KELAS                     #
# ============================================================================ #

@absensi_ns.route("/kelas/peserta")
class KelasPesertaResource(Resource):

    @role_required("mentor")
    @absensi_ns.expect(kelas_peserta_parser)
    def get(self):
        """Akses: mentor, Mengambil peserta berdasarkan kelas"""

        id_mentor = get_jwt_identity()

        try:
            id_paketkelas = kelas_peserta_parser.parse_args().get("id_paketkelas")
            result = get_peserta_by_mentor(id_mentor, id_paketkelas)

            return {
                "status": "success",
                "data": result,
                "meta": {"total": len(result)}
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /kelas/peserta] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



# ============================================================================ #
#                      #ANCHOR - ABSENSI BERDASARKAN JADWAL                    #
# ============================================================================ #

@absensi_ns.route("/jadwal/<int:id_jadwal>")
class AbsensiJadwalResource(Resource):

    @role_required("admin")
    def get(self, id_jadwal):
        """Akses: admin, Mengambil absensi berdasarkan jadwal"""

        try:
            result = get_absensi_by_jadwal(id_jadwal)

            if not result:
                return {
                    "status": "error",
                    "message": "Jadwal tidak ditemukan"
                }, 404

            return {"status": "success", "data": result}, 200

        except SQLAlchemyError as e:
            print(f"[GET /absensi/jadwal/{id_jadwal}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500
