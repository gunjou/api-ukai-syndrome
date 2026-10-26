from flask import request, send_file
from werkzeug.datastructures import FileStorage
from flask_restx import Namespace, Resource, fields, reqparse, inputs
from sqlalchemy.exc import SQLAlchemyError

from .utils.decorator import role_required
from .query.q_kelompok import *


kelompok_ns = Namespace("kelompok", description="Manajemen Kelompok Belajar (jadwal offline)")


# ============================================================================ #
#                                #ANCHOR - MODEL                               #
# ============================================================================ #

kelompok_model = kelompok_ns.model("Kelompok", {
    "id_batch": fields.Integer(required=True, description="ID batch kelompok"),
    "nama_kelompok": fields.String(required=True, description="Nama kelompok belajar", example="Kelompok Mataram 1")
})


assign_peserta_kelompok_model = kelompok_ns.model("AssignPesertaKelompok", {
    "id_peserta": fields.List(
        fields.Integer,
        required=True,
        description="Daftar ID peserta yang akan dimasukkan ke kelompok",
        example=[1, 2, 3]
    )
})



# ============================================================================ #
#                                #ANCHOR - PARSER                              #
# ============================================================================ #

kelompok_parser = kelompok_ns.parser()
kelompok_parser.add_argument("page", type=int, required=False, default=1, location="args", help="Halaman")
kelompok_parser.add_argument("limit", type=int, required=False, default=20, location="args", help="Jumlah data per halaman, maksimum 100")
kelompok_parser.add_argument("search", type=str, required=False, location="args", help="Search nama kelompok/batch")
kelompok_parser.add_argument("id_batch", type=int, required=False, location="args", help="Filter berdasarkan batch")


kelompok_dropdown_parser = kelompok_ns.parser()
kelompok_dropdown_parser.add_argument("id_batch", type=int, required=False, location="args", help="Filter berdasarkan batch")


peserta_tersedia_parser = kelompok_ns.parser()
peserta_tersedia_parser.add_argument("search", type=str, required=False, location="args", help="Search nama/email/kelas peserta")


bulk_import_kelompok_parser = reqparse.RequestParser()
bulk_import_kelompok_parser.add_argument("file", type=FileStorage, location="files", required=True, help="File anggota kelompok dalam format CSV atau XLSX")
bulk_import_kelompok_parser.add_argument("id_batch", type=int, location="form", required=True, help="ID batch kelompok")
bulk_import_kelompok_parser.add_argument("dry_run", type=inputs.boolean, location="form", required=False, default=False, help="true = hanya validasi & preview, tidak menyimpan data")


bulk_template_kelompok_parser = kelompok_ns.parser()
bulk_template_kelompok_parser.add_argument("id_batch", type=int, required=False, location="args", help="Jika diisi, template berisi daftar & dropdown kelompok pada batch tersebut")
bulk_template_kelompok_parser.add_argument("format", type=str, required=False, default="xlsx", choices=("xlsx", "csv"), location="args", help="Format template: xlsx (default) atau csv")



# ============================================================================ #
#                          #ANCHOR - HELPER VALIDASI                           #
# ============================================================================ #

def validate_kelompok_payload(data):
    if not data:
        return None, ({"status": "error", "message": "Request body tidak boleh kosong"}, 400)

    required_fields = ["id_batch", "nama_kelompok"]
    missing_fields = [field for field in required_fields if data.get(field) in (None, "")]

    if missing_fields:
        return None, ({
            "status": "error",
            "message": f"Field wajib diisi: {', '.join(missing_fields)}"
        }, 400)

    nama_kelompok = str(data["nama_kelompok"]).strip()

    if not nama_kelompok:
        return None, ({"status": "error", "message": "nama_kelompok tidak boleh kosong"}, 400)

    if len(nama_kelompok) > 100:
        return None, ({"status": "error", "message": "nama_kelompok maksimal 100 karakter"}, 400)

    try:
        id_batch = int(data["id_batch"])
    except (TypeError, ValueError):
        return None, ({"status": "error", "message": "id_batch harus berupa angka"}, 400)

    return {
        "id_batch": id_batch,
        "nama_kelompok": nama_kelompok
    }, None



# ============================================================================ #
#                     #ANCHOR - MANAJEMEN KELOMPOK BY ADMIN                    #
# ============================================================================ #

@kelompok_ns.route("")
class KelompokListResource(Resource):

    @role_required("admin")
    @kelompok_ns.expect(kelompok_parser)
    def get(self):
        """Akses: admin, List kelompok belajar + pagination + search + filter batch"""

        try:
            args = kelompok_parser.parse_args()
            page = args.get("page") or 1
            limit = args.get("limit") or 20

            if page < 1:
                return {
                    "status": "error",
                    "message": "Parameter page harus lebih besar dari 0"
                }, 400

            if not 1 <= limit <= 100:
                return {
                    "status": "error",
                    "message": "Parameter limit harus berada antara 1 dan 100"
                }, 400

            result = get_all_kelompok(
                id_batch=args.get("id_batch"),
                search=args.get("search"),
                page=page,
                limit=limit
            )

            return {
                "status": "success",
                "data": result["data"],
                "meta": {
                    "total": result["total"],
                    "page": result["page"],
                    "limit": result["limit"],
                    "total_page": result["total_page"]
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /kelompok] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required("admin")
    @kelompok_ns.expect(kelompok_model)
    def post(self):
        """Akses: admin, Membuat kelompok belajar baru"""

        payload, error = validate_kelompok_payload(request.get_json())

        if error:
            return error

        try:
            if not is_valid_batch(payload["id_batch"]):
                return {"status": "error", "message": "Batch tidak ditemukan"}, 404

            if is_nama_kelompok_exists(payload["id_batch"], payload["nama_kelompok"]):
                return {
                    "status": "error",
                    "message": "Nama kelompok sudah digunakan pada batch tersebut"
                }, 409

            result = insert_kelompok(payload)

            if not result:
                return {
                    "status": "error",
                    "message": "Gagal membuat kelompok"
                }, 400

            return {
                "status": "success",
                "message": "Kelompok berhasil dibuat",
                "data": result
            }, 201

        except SQLAlchemyError as e:
            print(f"[POST /kelompok] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



@kelompok_ns.route("/all")
class KelompokDropdownResource(Resource):

    @role_required("admin")
    @kelompok_ns.expect(kelompok_dropdown_parser)
    def get(self):
        """Akses: admin, Dropdown kelompok (id + nama saja)"""

        try:
            id_batch = kelompok_dropdown_parser.parse_args().get("id_batch")
            result = get_dropdown_kelompok(id_batch)

            return {
                "status": "success",
                "data": result,
                "meta": {"total": len(result)}
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /kelompok/all] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



# ============================================================================ #
#             #ANCHOR - MANAJEMEN KELOMPOK BY DETAIL (GET, PUT, DELETE)        #
# ============================================================================ #

@kelompok_ns.route("/<int:id_kelompok>")
class KelompokResource(Resource):

    @role_required("admin")
    def get(self, id_kelompok):
        """Akses: admin, Mengambil detail kelompok beserta anggotanya"""

        try:
            kelompok = get_kelompok_by_id(id_kelompok)

            if not kelompok:
                return {"status": "error", "message": "Kelompok tidak ditemukan"}, 404

            anggota = get_anggota_kelompok(id_kelompok)

            return {
                "status": "success",
                "data": {
                    **kelompok,
                    "jumlah_anggota": len(anggota),
                    "anggota": anggota
                }
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /kelompok/{id_kelompok}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required("admin")
    @kelompok_ns.expect(kelompok_model)
    def put(self, id_kelompok):
        """Akses: admin, Mengubah data kelompok"""

        payload, error = validate_kelompok_payload(request.get_json())

        if error:
            return error

        try:
            existing = get_kelompok_by_id(id_kelompok)

            if not existing:
                return {"status": "error", "message": "Kelompok tidak ditemukan"}, 404

            if not is_valid_batch(payload["id_batch"]):
                return {"status": "error", "message": "Batch tidak ditemukan"}, 404

            if (
                payload["id_batch"] != existing["id_batch"]
                and count_anggota_kelompok(id_kelompok) > 0
            ):
                return {
                    "status": "error",
                    "message": (
                        "Batch tidak dapat diubah karena kelompok "
                        "masih memiliki anggota"
                    )
                }, 400

            if is_nama_kelompok_exists(
                payload["id_batch"],
                payload["nama_kelompok"],
                exclude_id_kelompok=id_kelompok
            ):
                return {
                    "status": "error",
                    "message": "Nama kelompok sudah digunakan pada batch tersebut"
                }, 409

            result = update_kelompok({
                "id_kelompok": id_kelompok,
                **payload
            })

            if not result:
                return {"status": "error", "message": "Gagal mengubah kelompok"}, 400

            return {
                "status": "success",
                "message": "Kelompok berhasil diubah",
                "data": result
            }, 200

        except SQLAlchemyError as e:
            print(f"[PUT /kelompok/{id_kelompok}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500


    @role_required("admin")
    def delete(self, id_kelompok):
        """Akses: admin, Soft delete kelompok beserta seluruh anggotanya"""

        try:
            existing = get_kelompok_by_id(id_kelompok)

            if not existing:
                return {"status": "error", "message": "Kelompok tidak ditemukan"}, 404

            if has_upcoming_jadwal_kelompok(id_kelompok):
                return {
                    "status": "error",
                    "message": (
                        "Kelompok tidak dapat dihapus karena masih "
                        "memiliki jadwal aktif yang akan datang"
                    )
                }, 400

            result = delete_kelompok(id_kelompok)

            if not result:
                return {"status": "error", "message": "Gagal menghapus kelompok"}, 400

            return {"status": "success", "message": "Kelompok berhasil dihapus"}, 200

        except SQLAlchemyError as e:
            print(f"[DELETE /kelompok/{id_kelompok}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



# ============================================================================ #
#                       #ANCHOR - ANGGOTA KELOMPOK BY ADMIN                    #
# ============================================================================ #

@kelompok_ns.route("/<int:id_kelompok>/peserta-tersedia")
class KelompokPesertaTersediaResource(Resource):

    @role_required("admin")
    @kelompok_ns.expect(peserta_tersedia_parser)
    def get(self, id_kelompok):
        """Akses: admin, Peserta pada batch kelompok yang belum memiliki kelompok aktif"""

        try:
            kelompok = get_kelompok_by_id(id_kelompok)

            if not kelompok:
                return {"status": "error", "message": "Kelompok tidak ditemukan"}, 404

            search = peserta_tersedia_parser.parse_args().get("search")
            result = get_peserta_tersedia_kelompok(kelompok["id_batch"], search)

            return {
                "status": "success",
                "data": result,
                "meta": {"total": len(result)}
            }, 200

        except SQLAlchemyError as e:
            print(f"[GET /kelompok/{id_kelompok}/peserta-tersedia] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



@kelompok_ns.route("/<int:id_kelompok>/peserta")
class KelompokPesertaResource(Resource):

    @role_required("admin")
    @kelompok_ns.expect(assign_peserta_kelompok_model)
    def post(self, id_kelompok):
        """Akses: admin, Assign satu atau banyak peserta ke kelompok. Body: { "id_peserta": [1,2,3] }"""

        data = request.get_json()

        if not data:
            return {"status": "error", "message": "Request body tidak boleh kosong"}, 400

        list_id_peserta = data.get("id_peserta")

        if not isinstance(list_id_peserta, list) or not list_id_peserta:
            return {
                "status": "error",
                "message": "id_peserta wajib berupa list dan tidak boleh kosong"
            }, 400

        try:
            list_id_peserta = list(dict.fromkeys(int(i) for i in list_id_peserta))
        except (TypeError, ValueError):
            return {
                "status": "error",
                "message": "Seluruh id_peserta harus berupa angka"
            }, 400

        try:
            kelompok = get_kelompok_by_id(id_kelompok)

            if not kelompok:
                return {"status": "error", "message": "Kelompok tidak ditemukan"}, 404

            result = assign_peserta_kelompok(
                id_kelompok,
                kelompok["id_batch"],
                list_id_peserta
            )

            if not result:
                return {"status": "error", "message": "Gagal menambahkan peserta ke kelompok"}, 400

            if result.get("status") == "INVALID":
                return {
                    "status": "error",
                    "message": "Sebagian peserta tidak dapat dimasukkan ke kelompok",
                    "data": {
                        "errors": result.get("errors", [])
                    }
                }, 422

            return {
                "status": "success",
                "message": "Peserta berhasil ditambahkan ke kelompok",
                "data": {
                    "id_kelompok": id_kelompok,
                    "inserted_rows": result.get("inserted_rows", 0)
                }
            }, 201

        except SQLAlchemyError as e:
            print(f"[POST /kelompok/{id_kelompok}/peserta] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



@kelompok_ns.route("/peserta/<int:id_kelompok_peserta>")
class KelompokPesertaDetailResource(Resource):

    @role_required("admin")
    def delete(self, id_kelompok_peserta):
        """Akses: admin, Mengeluarkan peserta dari kelompok (soft delete)"""

        try:
            existing = get_kelompok_peserta_by_id(id_kelompok_peserta)

            if not existing:
                return {"status": "error", "message": "Data anggota kelompok tidak ditemukan"}, 404

            result = delete_kelompok_peserta(id_kelompok_peserta)

            if not result:
                return {"status": "error", "message": "Gagal mengeluarkan peserta dari kelompok"}, 400

            return {
                "status": "success",
                "message": "Peserta berhasil dikeluarkan dari kelompok"
            }, 200

        except SQLAlchemyError as e:
            print(f"[DELETE /kelompok/peserta/{id_kelompok_peserta}] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500



# ============================================================================ #
#                   #ANCHOR - BULK IMPORT ANGGOTA KELOMPOK                     #
# ============================================================================ #

@kelompok_ns.route("/bulk/import")
class KelompokBulkImportResource(Resource):

    @role_required("admin")
    @kelompok_ns.expect(bulk_import_kelompok_parser)
    def post(self):
        """
        Akses: admin

        Import anggota kelompok via file CSV/XLSX.

        - Kolom: nama_kelompok (wajib), email dan/atau nama peserta
        - Peserta dicocokkan dengan email (utama) atau nama (jika unik)
        - Pencocokan tidak membedakan huruf besar/kecil & spasi berlebih
        - Jika ada satu baris error -> tidak ada data yang disimpan
        - dry_run=true -> hanya validasi & preview
        """

        args = bulk_import_kelompok_parser.parse_args()
        file = args.get("file")
        id_batch = args.get("id_batch")
        dry_run = args.get("dry_run") or False

        # ------------------------------------------------------------------ #
        # VALIDASI FILE
        # ------------------------------------------------------------------ #

        if not file or not file.filename:
            return {"status": "error", "message": "File wajib diupload"}, 400

        filename = file.filename.lower()

        if "." not in filename:
            return {"status": "error", "message": "Format file tidak didukung"}, 400

        extension = "." + filename.rsplit(".", 1)[1]

        if extension not in BULK_ALLOWED_EXTENSIONS:
            return {"status": "error", "message": "File harus berformat CSV atau XLSX"}, 400

        file.stream.seek(0, 2)
        file_size = file.stream.tell()
        file.stream.seek(0)

        if file_size == 0:
            return {"status": "error", "message": "File tidak boleh kosong"}, 400

        if file_size > BULK_MAX_FILE_SIZE:
            return {
                "status": "error",
                "message": f"Ukuran file maksimal {BULK_MAX_FILE_SIZE // (1024 * 1024)} MB"
            }, 400

        try:
            if not is_valid_batch(id_batch):
                return {"status": "error", "message": "Batch tidak ditemukan"}, 404

            result = import_bulk_kelompok(
                file=file.stream,
                filename=file.filename,
                id_batch=id_batch,
                dry_run=dry_run
            )

            if not result:
                return {"status": "error", "message": "Gagal melakukan import anggota kelompok"}, 400

            # ============================================================= #
            # FILE TIDAK VALID (header, kosong, terlalu banyak baris)
            # ============================================================= #

            if result.get("status") == "FILE_INVALID":
                return {"status": "error", "message": result.get("message")}, 400

            # ============================================================= #
            # ADA BARIS YANG TIDAK VALID
            # ============================================================= #

            if result.get("status") == "INVALID":
                return {
                    "status": "error",
                    "message": "File memiliki data yang tidak valid",
                    "data": {
                        "total_rows": result.get("total_rows", 0),
                        "valid_rows": result.get("valid_rows", 0),
                        "invalid_rows": result.get("invalid_rows", 0),
                        "errors": result.get("errors", [])
                    }
                }, 422

            # ============================================================= #
            # DRY RUN
            # ============================================================= #

            if result.get("status") == "VALID":
                return {
                    "status": "success",
                    "message": "File valid dan siap di-import",
                    "data": {
                        "dry_run": True,
                        "total_rows": result.get("total_rows", 0),
                        "will_insert_rows": result.get("will_insert_rows", 0),
                        "skipped_rows": result.get("skipped_rows", 0),
                        "per_kelompok": result.get("per_kelompok", []),
                        "preview": result.get("preview", []),
                        "skipped": result.get("skipped", [])
                    }
                }, 200

            # ============================================================= #
            # SUCCESS
            # ============================================================= #

            return {
                "status": "success",
                "message": "Import anggota kelompok berhasil",
                "data": {
                    "dry_run": False,
                    "total_rows": result.get("total_rows", 0),
                    "inserted_rows": result.get("inserted_rows", 0),
                    "skipped_rows": result.get("skipped_rows", 0),
                    "per_kelompok": result.get("per_kelompok", []),
                    "skipped": result.get("skipped", [])
                }
            }, 201

        except SQLAlchemyError as e:
            print(f"[POST /kelompok/bulk/import] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500

        except Exception as e:
            print(f"[POST /kelompok/bulk/import] Unexpected Error: {e}")
            return {"status": "error", "message": "Gagal memproses file"}, 500



@kelompok_ns.route("/bulk/template")
class KelompokBulkTemplateResource(Resource):

    @role_required("admin")
    @kelompok_ns.expect(bulk_template_kelompok_parser)
    def get(self):
        """
        Akses: admin

        Download template import anggota kelompok.

        - format=xlsx (default): sheet Import, Petunjuk, dan jika id_batch diisi
          sheet Daftar Kelompok + dropdown pada kolom nama_kelompok
        - format=csv: header + contoh saja
        """

        args = bulk_template_kelompok_parser.parse_args()
        id_batch = args.get("id_batch")
        file_format = args.get("format") or "xlsx"

        try:
            if id_batch is not None and not is_valid_batch(id_batch):
                return {"status": "error", "message": "Batch tidak ditemukan"}, 404

            buffer, download_name, mimetype = build_template_kelompok(
                id_batch=id_batch,
                file_format=file_format
            )

            return send_file(
                buffer,
                as_attachment=True,
                download_name=download_name,
                mimetype=mimetype
            )

        except SQLAlchemyError as e:
            print(f"[GET /kelompok/bulk/template] Error: {e}")
            return {"status": "error", "message": "Internal server error"}, 500

        except Exception as e:
            print(f"[GET /kelompok/bulk/template] Unexpected Error: {e}")
            return {"status": "error", "message": "Gagal membuat template"}, 500