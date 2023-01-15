import logging
import os
import sys
import subprocess
import time
import atexit

from flask import Flask
from ocr_service.api import api
from config import *

sys.path.append("..")

def setup_logging():
    """
    Configure and setup a default logging handler to print messages to stdout
    """
    root_logger = logging.getLogger()
    log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    app_log_level = os.getenv("LOG_LEVEL", logging.INFO)
    log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setFormatter(logging.Formatter(fmt=log_format))
    log_handler.setLevel(level=app_log_level)

    # only add the handler if a previous one does not exists
    handler_exists = False
    for h in root_logger.handlers:
        if isinstance(h, logging.StreamHandler) and h.level is log_handler.level:
            handler_exists = True
            break

    if not handler_exists:
        root_logger.addHandler(log_handler)


def start_office_converter_server():
    global loffice_process
    loffice_process = subprocess.Popen(args=[LIBRE_OFFICE_PYTHON_PATH, "-m", "unoserver.server","--daemon", "--interface", LIBRE_OFFICE_NETWORK_INTERFACE, "--executable", LIBRE_OFFICE_EXEC_PATH, "--port", LIBRE_OFFICE_LISTENER_PORT],
                        cwd=TMP_FILE_DIR)
    # allow subprocess to start
    time.sleep(10)

def create_app():
    """
    Creates the Flask application using the factory method
    :return: Flask application
    """

    setup_logging()
    start_office_converter_server()
    exit_handler()

    app = Flask(__name__, instance_relative_config=True)
    app.register_blueprint(api)

    return app

def exit_handler():
    loffice_process.kill()

atexit.register(exit_handler)
