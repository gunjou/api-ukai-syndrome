import os
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_restx import Api

from .utils.blacklist_store import is_blacklisted

from .auth import auth_ns


api = Flask(__name__)
CORS(api)

load_dotenv()

api.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")
# api.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=3)  # waktu login sesi
api.config['JWT_BLACKLIST_ENABLED'] = True
api.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access', 'refresh']

jwt = JWTManager(api)

@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    return is_blacklisted(jwt_payload['jti'])

authorizations = {
    'Bearer Auth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': 'Masukkan token JWT Anda dengan format: **Bearer &lt;JWT&gt;**'
    }
}

# Swagger API instance
restx_api = Api(
    api, 
    version="1.0", 
    title="Ukai Syndrome", 
    description="Dokumentasi API Ukai Syndrome", 
    doc="/documentation",
    authorizations=authorizations,
    security='Bearer Auth'
)

restx_api.add_namespace(auth_ns, path="/auth")