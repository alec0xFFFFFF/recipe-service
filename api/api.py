import os

from flask import Flask

from data.models import db

db_params = {
    "dbname": os.environ.get("PGDATABASE"),
    "user": os.environ.get("PGUSER"),
    "password": os.environ.get("PGPASSWORD"),
    "host": os.environ.get("PGHOST"),
    "port": int(os.environ.get("PGPORT"))
}


def create_api():
    app = Flask(__name__)

    # Database configuration
    app.config[
        'SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_params["user"]}:{db_params["password"]}@{db_params["host"]}:{db_params["port"]}/{db_params["dbname"]}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # Import routes after db to avoid circular imports
    from api.v1.routes import init_api_v1
    init_api_v1(app)

    return app
