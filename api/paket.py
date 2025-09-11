from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields
from sqlalchemy.exc import SQLAlchemyError
from .query.q_paket import *
from .utils.decorator import role_required, session_required


paket_ns = Namespace("paket", description="Manajemen paket yang tersedia")

@paket_ns.route('')
class KelasListResource(Resource):
    # @session_required
    @jwt_required()
    @role_required('admin')
    def get(self):
        """Akses: (admin, mentor), Ambil semua kelas aktif untuk admin, dan yang diampu oleh mentor"""
        try:
            # current_user_id = get_jwt_identity()

            result = get_all_paket()

            if not result:
                return {"status": "error", "message": "Tidak ada kelas ditemukan"}, 404
            return {"data": result}, 200
        except SQLAlchemyError as e:
            return {"status": "error", "message": str(e)}, 500