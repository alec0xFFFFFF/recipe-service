import os

from authlib.integrations.flask_client import OAuth
from flask import Flask
from flask_jwt_extended import JWTManager

from data.models import db
from dotenv import load_dotenv
load_dotenv()

db_params = {
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
    "host": os.getenv("PGHOST"),
    "port": int(os.getenv("PGPORT"))
}


def create_api():
    app = Flask(__name__)

    # Database configuration
    app.config[
        'SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_params["user"]}:{db_params["password"]}@{db_params["host"]}:{db_params["port"]}/{db_params["dbname"]}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")
    app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
    app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
    app.config['APPLE_CLIENT_ID'] = os.getenv('APPLE_CLIENT_ID')
    app.config['APPLE_TEAM_ID'] = os.getenv('APPLE_TEAM_ID')
    app.config['APPLE_KEY_ID'] = os.getenv('APPLE_KEY_ID')
    app.config['APPLE_PRIVATE_KEY'] = os.getenv('APPLE_PRIVATE_KEY')

    db.init_app(app)

    jwt = JWTManager(app)

    oauth = OAuth(app)

    # Import routes after db to avoid circular imports
    from api.v1.routes import init_api_v1
    init_api_v1(app)

    return app
