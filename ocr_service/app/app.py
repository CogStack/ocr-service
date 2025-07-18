import atexit
import os
import subprocess
import sys
import threading
import time
import logging

import psutil
from flask import Flask

from config import DEBUG_MODE, LIBRE_OFFICE_EXEC_PATH, LIBRE_OFFICE_LISTENER_PORT_RANGE, \
                   LIBRE_OFFICE_NETWORK_INTERFACE, \
                   LIBRE_OFFICE_PYTHON_PATH, LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL, \
                   OCR_WEB_SERVICE_THREADS, OCR_WEB_SERVICE_WORKERS, TMP_FILE_DIR

from ocr_service.api import api
from ocr_service.processor.processor import Processor
from ocr_service.utils.utils import get_assigned_port

sys.path.append("..")

app = Flask(__name__, instance_relative_config=True)


def start_office_server(port_num):
    loffice_process = {"process": subprocess.Popen(args=[LIBRE_OFFICE_PYTHON_PATH, "-m", "unoserver.server",
                                                         "--interface", LIBRE_OFFICE_NETWORK_INTERFACE,
                                                         "--executable", LIBRE_OFFICE_EXEC_PATH,
                                                         "--port", str(port_num)],
                                                   cwd=TMP_FILE_DIR,
                                                   close_fds=True,
                                                   shell=False),
                       "pid": "",
                       "port": str(port_num),
                       "used": False}
    loffice_process["pid"] = loffice_process["process"].pid

    return loffice_process


def start_office_converter_servers():

    loffice_processes = {}

    for port_num in LIBRE_OFFICE_LISTENER_PORT_RANGE:
        if port_num == get_assigned_port(os.getpid()) and OCR_WEB_SERVICE_THREADS == 1:
            logging.debug("STARTED WORKER ON PORT: " + str(port_num))
            process = start_office_server(port_num)
            loffice_processes[port_num] = process
            break
        elif OCR_WEB_SERVICE_WORKERS == 1 and OCR_WEB_SERVICE_THREADS > 1:
            process = start_office_server(port_num)
            loffice_processes[port_num] = process
        elif DEBUG_MODE:
            process = start_office_server(port_num)
            loffice_processes[port_num] = process
            break

    return loffice_processes


def create_app():
    """
        :description: Creates the Flask application using the factory method
        :return: Flask application
    """

    try:
        global _loffice_processes
        _loffice_processes = {}
        _loffice_processes.update(start_office_converter_servers())

        app.register_blueprint(api)
        app.debug = DEBUG_MODE

        # share processes for api call resource allocation
        api.processor = Processor()
        api.processor.loffice_process_list.update(_loffice_processes)

        proc_listener_thread = threading.Thread(target=process_listener, name="loffice_proc_listener")
        proc_listener_thread.daemon = True
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
                    logging.info("Libreoffice port:" + str(port_num) + "unoserver is DOWN, restarting.....")
                    exit_handler(port_num)
                    process = start_office_server(port_num)
                    api.processor.loffice_process_list[port_num] = process

                logging.info("Checking soffice pid: " + str(p.pid) + " | port: " + str(port_num))
                logging.info("Checking loffice subproceess status " + str(p.name))

                _loffice_processes = api.processor.loffice_process_list
            time.sleep(LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL)
    except Exception:
        raise


def exit_handler(port_num: int):
    logging.info("exit handler: libreoffice unoserver shutting down...")
    api.processor.loffice_process_list[port_num]["process"].kill()
    del api.processor.loffice_process_list[port_num]


if __name__ == '__main__':
    atexit.register(exit_handler, port_num=get_assigned_port(os.getpid()))
