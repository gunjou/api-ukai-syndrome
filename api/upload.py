# api/upload.py
from flask_restx import Namespace, Resource, reqparse
from flask_jwt_extended import jwt_required
from werkzeug.datastructures import FileStorage

from .utils.cdn import upload_image_to_cdn


upload_ns = Namespace("upload", description="Upload file (image)")

upload_image_parser = reqparse.RequestParser()
upload_image_parser.add_argument('file', type=FileStorage, location='files', required=True, help='File gambar (jpg, png)')

@upload_ns.route('/image')
class UploadImageResource(Resource):
    @upload_ns.expect(upload_image_parser)
    @jwt_required()
    def post(self):
        """
        Upload gambar ke CDN (MGF) dan kembalikan URL
        """
        args = upload_image_parser.parse_args()
        image_file = args.get("file")

        if not image_file:
            return {"success": False, "message": "File tidak ditemukan"}, 400

        try:
            response = upload_image_to_cdn(image_file)

            if not response["success"]:
                return response, 400

            return response, 201

        except Exception as e:
            print(f"[ERROR upload image] {e}")
            return {
                "success": False,
                "message": "Terjadi kesalahan saat upload gambar"
            }, 500
