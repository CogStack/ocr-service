import atexit
import logging
import os
import subprocess
import sys
import threading
import time

import psutil
from flask import Flask

from config import *
from ocr_service.api import api
from ocr_service.utils.utils import get_process_id_by_process_name

sys.path.append("..")

def setup_logging():
    """
        :description: Configure and setup a default logging handler to print messages to stdout
    """
    global root_logger
    root_logger = logging.getLogger()
    log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    app_log_level = os.getenv("LOG_LEVEL", LOG_LEVEL)
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
    loffice_process = subprocess.Popen(args=[LIBRE_OFFICE_PYTHON_PATH, "-m", "unoserver.server", "--interface", LIBRE_OFFICE_NETWORK_INTERFACE, "--executable", LIBRE_OFFICE_EXEC_PATH, "--port", LIBRE_OFFICE_LISTENER_PORT],
                            cwd=TMP_FILE_DIR, close_fds=True, shell=False)

def create_app():
    """
        :description: Creates the Flask application using the factory method
        :return: Flask application
    """

    try:
        setup_logging()
        start_office_converter_server()

        proc_listener_thread = threading.Thread(target=process_listener, name="loffice_proc_listener")
        proc_listener_thread.start()

        app = Flask(__name__, instance_relative_config=True)
        app.register_blueprint(api)

    except Exception:
        raise

    return app

def process_listener():

    try:
        while True:
            p = psutil.Process(loffice_process.pid)
            if psutil.pid_exists(p.pid) is False or p.is_running() is False:
                print("Libreoffice unoserver is DOWN, restarting.....")
                exit_handler()
                start_office_converter_server()
            elif p.status() is psutil.STATUS_ZOMBIE:
                p.kill()
                exit_handler()
                start_office_converter_server()
            
            print("Checking soffice pid: " + str(get_process_id_by_process_name(LIBRE_OFFICE_EXEC_PATH)))
            print("Checking loffice subproceess status " + str(p.name))
            time.sleep(10)
    except Exception:
        raise

def exit_handler():
    print("exit handler: libreoffice unoserver shutting down...")
    loffice_process.kill()

if __name__ == '__main__':
    atexit.register(exit_handler)
