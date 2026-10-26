from datetime import datetime

from flask import send_file
from flask_jwt_extended import get_jwt_identity
from flask_restx import Namespace, Resource, inputs
from sqlalchemy.exc import SQLAlchemyError

from .utils.decorator import role_required
from .utils.config import get_wib
from .query.q_payroll import *
from .export.e_slip_payroll import build_slip_payroll_pdf


payroll_ns = Namespace("payroll", description="Rekap Jam Mengajar & Payroll Mentor")


# ============================================================================ #
#                                #ANCHOR - PARSER                              #
# ============================================================================ #

payroll_list_parser = payroll_ns.parser()
payroll_list_parser.add_argument("bulan", type=str, required=False, location="args", help="Periode bulan (YYYY-MM), default bulan berjalan")
payroll_list_parser.add_argument("search", type=str, required=False, location="args", help="Search nama/nickname mentor")


payroll_bulan_parser = payroll_ns.parser()
payroll_bulan_parser.add_argument("bulan", type=str, required=False, location="args", help="Periode bulan (YYYY-MM), default bulan berjalan")


payroll_riwayat_parser = payroll_ns.parser()
payroll_riwayat_parser.add_argument("tahun", type=int, required=False, location="args", help="Tahun (YYYY), default tahun berjalan")


payroll_slip_parser = payroll_ns.parser()
payroll_slip_parser.add_argument("bulan", type=str, required=False, location="args", help="Periode bulan (YYYY-MM), default bulan berjalan")
payroll_slip_parser.add_argument("preview", type=inputs.boolean, required=False, default=False, location="args", help="true = tampil di browser (inline), false = download")


# ============================================================================ #
#                          #ANCHOR - HELPER VALIDASI                           #
# ============================================================================ #

def resolve_bulan(value):
    """
    'YYYY-MM' -> periode tanggal 1 s/d akhir bulan.
    Kosong -> bulan berjalan.
    Return (periode, error).
    """

    if not value or not str(value).strip():
        today = get_wib().date()
        tahun, bulan = today.year, today.month

    else:
        try:
            parsed = datetime.strptime(str(value).strip(), "%Y-%m")
        except ValueError:
            return None, ({
                "status": "error",
                "message": "Format bulan harus YYYY-MM, contoh 2026-10"
            }, 400)

        tahun, bulan = parsed.year, parsed.month

    start_date, end_date = get_periode_bulan(tahun, bulan)

    return {
        "bulan": f"{tahun:04d}-{bulan:02d}",
        "nama_bulan": f"{NAMA_BULAN[bulan]} {tahun}",
        "start_date": start_date,
        "end_date": end_date
    }, None


def build_periode_meta(periode):
    return {
        "bulan": periode["bulan"],
        "nama_bulan": periode["nama_bulan"],
        "start_date": periode["start_date"].isoformat(),
        "end_date": periode["end_date"].isoformat(),
        "tarif_per_jam": PAYROLL_TARIF_PER_JAM
    }


def build_mentor_data(mentor):
    return {
        "id_mentor": mentor["id_mentor"],
        "nama_mentor": mentor["nama_mentor"],
        "nickname_mentor": mentor["nickname_mentor"],
        "email": mentor["email"]
    }



# ============================================================================ #
#                       #ANCHOR - PAYROLL MENTOR BY ADMIN                      #
# ============================================================================ #

@payroll_ns.route("/mentor")
class PayrollMentorListResource(Resource):

        @role_required("admin")
        @payroll_ns.expect(payroll_list_parser)
        def get(self):
            """Akses: admin, Rekap jam mengajar & honor seluruh mentor dalam 1 bulan + search"""

            try:
                args = payroll_list_parser.parse_args()

                periode, error = resolve_bulan(args.get("bulan"))

                if error:
                    return error

                result = get_rekap_payroll_bulanan(
                    start_date=periode["start_date"],
                    end_date=periode["end_date"],
                    search=args.get("search")
                )

                return {
                    "status": "success",
                    "data": result["data"],
                    "meta": {
                        **build_periode_meta(periode),
                        "total": result["total"],
                        "total_menit_dibayar": result["total_menit_dibayar"],
                        "total_jam_dibayar_label": result["total_jam_dibayar_label"],
                        "total_honor": result["total_honor"]
                    }
                }, 200

            except SQLAlchemyError as e:
                print(f"[GET /payroll/mentor] Error: {e}")
                return {"status": "error", "message": "Internal server error"}, 500



@payroll_ns.route("/mentor/<int:id_mentor>")
class PayrollMentorDetailResource(Resource):

    @role_required("admin")
    @payroll_ns.expect(payroll_bulan_parser)
    def get(self, id_mentor):
        """Akses: admin, Ringkasan + rincian per sesi payroll satu mentor dalam 1 bulan"""

        try:
            periode, error = resolve_bulan(payroll_bulan_parser.parse_args().get("bulan"))

            if error:
                return error

            mentor = get_mentor_payroll(id_mentor)

            if not mentor:
                return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

            result = get_detail_payroll_mentor(
                id_mentor,
                periode["start_date"],
                periode["end_date"]
            )

            return {
                "status": "success",
                "data": {
                    "mentor": build_mentor_data(mentor),
                    "ringkasan": result["ringkasan"],
                    "rincian": result["rincian"]
                },
                "meta": {
                    **build_periode_meta(periode),
                    "total": len(result["rincian"])
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /payroll/mentor/{id_mentor}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



@payroll_ns.route("/mentor/export")
class PayrollMentorExportResource(Resource):

    @role_required("admin")
    @payroll_ns.expect(payroll_bulan_parser)
    def get(self):
        """
        Akses: admin

        Download rekap payroll seluruh mentor (XLSX).

        - Sheet Rekap: ringkasan per mentor + total
        - Sheet Rincian: rincian per sesi
        - Sheet Keterangan: aturan perhitungan
        """

        try:
            periode, error = resolve_bulan(payroll_bulan_parser.parse_args().get("bulan"))

            if error:
                return error

            buffer, download_name, mimetype = build_export_payroll(
                periode["start_date"],
                periode["end_date"],
                periode["bulan"]
            )

            return send_file(
                buffer,
                as_attachment=True,
                download_name=download_name,
                mimetype=mimetype
            )

        except SQLAlchemyError as e:
            print(f"[GET /payroll/mentor/export] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500

        except Exception as e:
            print(f"[GET /payroll/mentor/export] Unexpected Error: {e}")
            return {"status": "error", "message": "Gagal membuat file export"}, 500



# ============================================================================ #
#                         #ANCHOR - PAYROLL MILIK MENTOR                       #
# ============================================================================ #

@payroll_ns.route("/saya")
class PayrollSayaResource(Resource):

    @role_required("mentor")
    @payroll_ns.expect(payroll_bulan_parser)
    def get(self):
        """Akses: mentor, Ringkasan + rincian payroll milik mentor yang sedang login dalam 1 bulan"""

        id_mentor = int(get_jwt_identity())

        try:
            periode, error = resolve_bulan(payroll_bulan_parser.parse_args().get("bulan"))

            if error:
                return error

            mentor = get_mentor_payroll(id_mentor)

            if not mentor:
                return {"status": "error", "message": "Data mentor tidak ditemukan"}, 404

            result = get_detail_payroll_mentor(
                id_mentor,
                periode["start_date"],
                periode["end_date"]
            )

            return {
                "status": "success",
                "data": {
                    "mentor": build_mentor_data(mentor),
                    "ringkasan": result["ringkasan"],
                    "rincian": result["rincian"]
                },
                "meta": {
                    **build_periode_meta(periode),
                    "total": len(result["rincian"])
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /payroll/saya] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



@payroll_ns.route("/saya/riwayat")
class PayrollSayaRiwayatResource(Resource):

    @role_required("mentor")
    @payroll_ns.expect(payroll_riwayat_parser)
    def get(self):
        """Akses: mentor, Ringkasan payroll per bulan dalam 1 tahun milik mentor yang sedang login"""

        id_mentor = int(get_jwt_identity())

        try:
            tahun = payroll_riwayat_parser.parse_args().get("tahun") or get_wib().year

            if not 2000 <= tahun <= 2100:
                return {"status": "error", "message": "Parameter tahun tidak valid"}, 400

            result = get_riwayat_payroll_mentor(id_mentor, tahun)

            return {
                "status": "success",
                "data": result,
                "meta": {
                    "tahun": tahun,
                    "tarif_per_jam": PAYROLL_TARIF_PER_JAM,
                    "total": len(result),
                    "total_menit_dibayar": sum(item["total_menit_dibayar"] for item in result),
                    "total_honor": sum(item["honor"] for item in result)
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /payroll/saya/riwayat] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


# ============================================================================ #
#  payroll.py - TAMBAHKAN DI BAGIAN #ANCHOR - HELPER VALIDASI
# ============================================================================ #

def send_slip_payroll(id_mentor, periode, preview=False):
    """Return response file PDF, atau None jika mentor tidak ditemukan"""

    mentor = get_mentor_payroll(id_mentor)

    if not mentor:
        return None

    detail = get_detail_payroll_mentor(
        id_mentor,
        periode["start_date"],
        periode["end_date"]
    )

    buffer, download_name, mimetype = build_slip_payroll_pdf(mentor, periode, detail)

    return send_file(
        buffer,
        as_attachment=not preview,
        download_name=download_name,
        mimetype=mimetype
    )



# ============================================================================ #
#  payroll.py - TAMBAHKAN DI BAGIAN #ANCHOR - PAYROLL MENTOR BY ADMIN
# ============================================================================ #

@payroll_ns.route("/mentor/<int:id_mentor>/slip")
class PayrollMentorSlipResource(Resource):

    @role_required("admin")
    @payroll_ns.expect(payroll_slip_parser)
    def get(self, id_mentor):
        """
        Akses: admin

        Download slip honor (PDF) satu mentor dalam 1 bulan.
        preview=true -> ditampilkan di browser (inline)
        """

        try:
            args = payroll_slip_parser.parse_args()
            periode, error = resolve_bulan(args.get("bulan"))

            if error:
                return error

            result = send_slip_payroll(id_mentor, periode, args.get("preview") or False)

            if not result:
                return {"status": "error", "message": "Mentor tidak ditemukan"}, 404

            return result

        except SQLAlchemyError as e:
            print(f"[GET /payroll/mentor/{id_mentor}/slip] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500

        except Exception as e:
            print(f"[GET /payroll/mentor/{id_mentor}/slip] Unexpected Error: {e}")
            return {"status": "error", "message": "Gagal membuat slip honor"}, 500



# ============================================================================ #
#  payroll.py - TAMBAHKAN DI BAGIAN #ANCHOR - PAYROLL MILIK MENTOR
# ============================================================================ #

@payroll_ns.route("/saya/slip")
class PayrollSayaSlipResource(Resource):

    @role_required("mentor")
    @payroll_ns.expect(payroll_slip_parser)
    def get(self):
        """
        Akses: mentor

        Download slip honor (PDF) milik mentor yang sedang login dalam 1 bulan.
        preview=true -> ditampilkan di browser (inline)
        """

        id_mentor = int(get_jwt_identity())

        try:
            args = payroll_slip_parser.parse_args()
            periode, error = resolve_bulan(args.get("bulan"))

            if error:
                return error

            result = send_slip_payroll(id_mentor, periode, args.get("preview") or False)

            if not result:
                return {"status": "error", "message": "Data mentor tidak ditemukan"}, 404

            return result

        except SQLAlchemyError as e:
            print(f"[GET /payroll/saya/slip] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500

        except Exception as e:
            print(f"[GET /payroll/saya/slip] Unexpected Error: {e}")
            return {"status": "error", "message": "Gagal membuat slip honor"}, 500