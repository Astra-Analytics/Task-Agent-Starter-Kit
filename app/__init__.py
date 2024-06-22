import logging
import os

from flask import Flask

from utils.custom_log_formatter import ThreadNameColoredFormatter

from .app import main

# Configure colorlog with the custom formatter
formatter = ThreadNameColoredFormatter(
    "%(log_color)s[%(threadName)s] - %(message)s",
)

handler = logging.StreamHandler()
handler.setFormatter(formatter)

# Suppress logging from specific third-party libraries
logging.getLogger("google_auth_httplib2").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)
logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def create_app():
    app = Flask(__name__, template_folder="./templates", static_folder="./static")
    app.secret_key = os.getenv("FLASK_SECRET_KEY")

    app.register_blueprint(main)

    return app
