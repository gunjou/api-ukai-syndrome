from flask_jwt_extended import jwt_required
from flask_restx import Namespace, Resource, fields


auth_ns = Namespace('auth', description='Endpoint Autentikasi Admin, Mentor dan Peserta')

login_model = auth_ns.model('Login', {
    'username': fields.String(required=True),
    'password': fields.String(required=True)
})

logout_model = auth_ns.model('Logout', {
    'jti': fields.String(required=True)
})

@auth_ns.route('/protected')
class ProtectedResource(Resource):
    # @jwt_required()
    def get(self):
        """Akses: (admin/mentor/peserta), Cek token masih valid"""
        return {'status': 'Token masih valid'}, 200