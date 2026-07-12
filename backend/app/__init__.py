from flask import Flask

from app.config import Config
from app.utils.api_response import api_response


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.get("/api/health")
    def health():
        return api_response(data={"service": "sico-pandas-lab-backend"}, message="ok")

    return app
