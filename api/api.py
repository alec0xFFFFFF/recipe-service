import os

from flask import Flask
from flask_socketio import SocketIO

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
    socketio = SocketIO(app)

    # Database configuration
    app.config[
        'SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_params["user"]}:{db_params["password"]}@{db_params["host"]}:{db_params["port"]}/{db_params["dbname"]}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # Import routes after db to avoid circular imports
    from api.v1.routes import init_api_v1, register_socketio_events
    init_api_v1(app)
    register_socketio_events(socketio)

    return app, socketio
