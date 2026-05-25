"""RQMS Flask application package."""

import os

from flask import Flask

from config import Config
from rqms.db import ensure_result_columns
from rqms.routes import bp


def create_app():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )
    app.config.from_object(Config)
    app.register_blueprint(bp)
    ensure_result_columns()
    return app
