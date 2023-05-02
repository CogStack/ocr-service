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
from ocr_service.processor.processor import Processor
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

def start_office_server(port_num):
    loffice_process = { "process" : subprocess.Popen(args=[LIBRE_OFFICE_PYTHON_PATH, "-m", "unoserver.server", "--interface", LIBRE_OFFICE_NETWORK_INTERFACE, "--executable", LIBRE_OFFICE_EXEC_PATH, "--port", str(port_num)],
                                        cwd=TMP_FILE_DIR, close_fds=True, shell=False), "used" : False}
    return loffice_process

def start_office_converter_servers():
    loffice_processes = {}

    port_count = 0
    for port_num in LIBRE_OFFICE_LISTENER_PORT_RANGE:
        if port_count < OCR_WEB_SERVICE_THREADS:
            port_count += 1
            if port_num not in list(loffice_processes.keys()):
                loffice_processes[port_num] = start_office_server(port_num)
        else:
            break
    return loffice_processes
            
def create_app():
    """
        :description: Creates the Flask application using the factory method
        :return: Flask application
    """

    try:
        setup_logging()
        loffice_processes = start_office_converter_servers()

        app = Flask(__name__, instance_relative_config=True)
        app.register_blueprint(api)
        
        # share processes for api call resource allocation 
        api.processor = Processor(loffice_processes)

        proc_listener_thread = threading.Thread(target=process_listener, name="loffice_proc_listener")
        proc_listener_thread.start()

    except Exception:
        raise

    return app

def process_listener():

    try:
        while True:
            for port_num, loffice_process in api.processor.loffice_process_list.items():
                p = psutil.Process(api.processor.loffice_process_list[port_num]["process"].pid)
                if psutil.pid_exists(p.pid) is False or p.is_running() is False or p.status() is psutil.STATUS_ZOMBIE:
                    print("Libreoffice port:" + str(port_num) + "unoserver is DOWN, restarting.....")
                    exit_handler(port_num)
                    api.processor.loffice_process_list[port_num] = start_office_server(port_num)
                
                print("Checking soffice pid: " + str(p.pid) + " | port: " + str(port_num))
                print("Checking loffice subproceess status " + str(p.name))
            time.sleep(LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL)
    except Exception:
        raise

def exit_handler(port_num: int):
    print("exit handler: libreoffice unoserver shutting down...")
    api.processor.loffice_process_list[port_num]["process"].kill()
    del api.processor.loffice_process_list[port_num]

if __name__ == '__main__':
    atexit.register(exit_handler)
