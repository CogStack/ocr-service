import contextlib
import logging
import os
import subprocess
import sys
import time
from threading import Event, Thread
from typing import Any

import psutil
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from config import (
    DEBUG_MODE,
    LIBRE_OFFICE_EXEC_PATH,
    LIBRE_OFFICE_LISTENER_PORT_RANGE,
    LIBRE_OFFICE_NETWORK_INTERFACE,
    LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL,
    LIBRE_OFFICE_PYTHON_PATH,
    OCR_SERVICE_VERSION,
    OCR_WEB_SERVICE_THREADS,
    OCR_WEB_SERVICE_WORKERS,
    TMP_FILE_DIR,
)
from ocr_service.api import api
from ocr_service.processor.processor import Processor
from ocr_service.utils.utils import get_assigned_port

sys.path.append("..")

# guard so LibreOffice startup runs only once per worker
_started: bool = False


def start_office_server(port_num: str) -> dict[str, Any]:
    """
        :description: Starts LibreOffice unoserver process for OCR processing
        :param port_num: Port number to start the server on
        :return: Dictionary with process information
    """

    loffice_process: dict[str, Any] = {
        "process": subprocess.Popen(
            args=[
                LIBRE_OFFICE_PYTHON_PATH,
                "-m",
                "unoserver.server",
                "--interface", LIBRE_OFFICE_NETWORK_INTERFACE,
                "--executable", LIBRE_OFFICE_EXEC_PATH,
                "--port", port_num
            ],
            cwd=TMP_FILE_DIR,
            close_fds=True,
            shell=False
        ),
        "pid": "",
        "port": port_num,
        "used": False,
        "unhealthy": False
    }

    loffice_process["pid"] = loffice_process["process"].pid

    return loffice_process


def start_office_converter_servers() -> dict[str, Any]:
    """
        :description: Starts LibreOffice unoserver processes for OCR processing
        :return: Dictionary with port numbers and process information
    """

    loffice_processes: dict[str, Any] = {}

    for port_num in LIBRE_OFFICE_LISTENER_PORT_RANGE:
        _port_num = str(port_num)
        if port_num == get_assigned_port(os.getpid()) and OCR_WEB_SERVICE_THREADS == 1:
            logging.debug("STARTED WORKER ON PORT: " + _port_num)
            process = start_office_server(_port_num)
            loffice_processes[_port_num] = process
            break
        elif (OCR_WEB_SERVICE_WORKERS == 1 and OCR_WEB_SERVICE_THREADS > 1) or DEBUG_MODE:
            process = start_office_server(_port_num)
            loffice_processes[_port_num] = process
            break
        else:
            process = start_office_server(_port_num)
            loffice_processes[_port_num] = process
            break

    return loffice_processes


def monitor_office_processes(thread_event: Event, processor: Processor) -> None:
    """
        :description: Monitors LibreOffice unoserver processes and restarts them if they are down
        :param thread_event: Event to signal the thread to stop
        :param processor: Processor instance to manage office processes
    """
    while not thread_event.is_set():
        try:
            for port, proc in list(processor.loffice_process_list.items()):
                _port = str(port)
                if proc.get("unhealthy"):
                    logging.warning(f"libreoffice on port {_port} marked unhealthy, restarting...")
                    with contextlib.suppress(Exception):
                        proc["process"].kill()
                    restarted_proc = start_office_server(_port)
                    processor.loffice_process_list[_port] = restarted_proc
                    continue

                libre_office_process = psutil.Process(proc["process"].pid)
                if (
                    not psutil.pid_exists(libre_office_process.pid)
                    or not libre_office_process.is_running()
                    or libre_office_process.status() == psutil.STATUS_ZOMBIE
                ):
                    logging.warning(f"libreoffice on port {_port} is down, restarting...")
                    with contextlib.suppress(Exception):
                        proc["process"].kill()
                    restarted_proc = start_office_server(_port)
                    processor.loffice_process_list[_port] = restarted_proc

                logging.info(f"libreoffice OK: pid={libre_office_process.pid}, port={_port}")
        except Exception as e:
            logging.error("error in libreoffice monitor thread: " + str(e))

        time.sleep(LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL)


def create_app() -> FastAPI:
    """
        :description: Creates FastAPI application with API router and starts libreoffice unoserver processes
        :return: FastAPI application instance
    """

    global _started

    try:
        app = FastAPI(title="OCR Service",
                      description="OCR Service API",
                      version=OCR_SERVICE_VERSION,
                      default_response_class=ORJSONResponse,
                      debug=DEBUG_MODE)
        app.include_router(api)

        # start once per worker
        if not _started:
            _started = True
            # Start LibreOffice unoserver processes
            loffice_processes = start_office_converter_servers()
            processor = Processor()
            processor.loffice_process_list.update(loffice_processes)
            app.state.processor = processor

            # Start monitor thread
            thread_event = Event()
            proc_listener_thread = Thread(
                target=monitor_office_processes,
                args=(thread_event, processor),
                name="loffice_proc_listener",
                daemon=True
            )
            proc_listener_thread.start()

            import atexit

            def cleanup():
                thread_event.set()
                if proc_listener_thread.is_alive():
                    proc_listener_thread.join(timeout=5)
                for port, proc in processor.loffice_process_list.items():
                    p = proc["process"]
                    try:
                        logging.info(f"shutting down libreoffice process on port {port}")
                        p.terminate()
                        p.wait(timeout=3)
                    except Exception:
                        try:
                            p.kill()
                        except Exception as e:
                            logging.error("error in when shutting down libreoffice process: " + str(e))
            atexit.register(cleanup)

    except Exception:
        raise

    return app
