import os
import subprocess
import sys
import time
import logging
import psutil

from typing import Any
from fastapi import FastAPI
from contextlib import asynccontextmanager
from threading import Thread, Event

from config import DEBUG_MODE, LIBRE_OFFICE_EXEC_PATH, LIBRE_OFFICE_LISTENER_PORT_RANGE, \
                   LIBRE_OFFICE_NETWORK_INTERFACE, \
                   LIBRE_OFFICE_PYTHON_PATH, LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL, \
                   OCR_WEB_SERVICE_THREADS, OCR_WEB_SERVICE_WORKERS, TMP_FILE_DIR, OCR_SERVICE_VERSION

from ocr_service.api import api
from ocr_service.processor.processor import Processor
from ocr_service.utils.utils import get_assigned_port

sys.path.append("..")


def start_office_server(port_num) -> dict[str, Any]:
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
                "--port", str(port_num)
            ],
            cwd=TMP_FILE_DIR,
            close_fds=True,
            shell=False
        ),
        "pid": "",
        "port": str(port_num),
        "used": False
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
        if port_num == get_assigned_port(os.getpid()) and OCR_WEB_SERVICE_THREADS == 1:
            logging.debug("STARTED WORKER ON PORT: " + str(port_num))
            process = start_office_server(port_num)
            loffice_processes[str(port_num)] = process
            break
        elif OCR_WEB_SERVICE_WORKERS == 1 and OCR_WEB_SERVICE_THREADS > 1:
            process = start_office_server(port_num)
            loffice_processes[str(port_num)] = process
            break
        elif DEBUG_MODE:
            process = start_office_server(port_num)
            loffice_processes[str(port_num)] = process
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
                libre_office_process = psutil.Process(proc["process"].pid)
                if (
                    not psutil.pid_exists(libre_office_process.pid)
                    or not libre_office_process.is_running()
                    or libre_office_process.status() == psutil.STATUS_ZOMBIE
                ):
                    logging.warning(f"libreoffice on port {port} is down, restarting...")
                    proc["process"].kill()
                    restarted_proc = start_office_server(port)
                    processor.loffice_process_list[port] = restarted_proc

                logging.info(f"libreoffice OK: pid={libre_office_process.pid}, port={port}")
        except Exception as e:
            logging.error("error in libreoffice monitor thread: " + str(e))

        time.sleep(LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL)


@asynccontextmanager
async def office_process_lifespan(app: FastAPI):
    """
        :description: Lifespan context manager to start and stop LibreOffice unoserver processes
        :param app: FastAPI application instance
    """

    # start LibreOffice unoserver processes
    loffice_processes = start_office_converter_servers()
    processor = Processor()
    processor.loffice_process_list.update(loffice_processes)
    app.state.processor = processor

    # start persistent background thread for monitoring
    thread_event: Event = Event()

    proc_listener_thread = Thread(
                target=monitor_office_processes,
                args=(thread_event, processor),
                name="loffice_proc_listener",
                daemon=True
            )
    proc_listener_thread.start()

    try:
        yield
    finally:
        # shutdown: kill processes & stop monitoring
        thread_event.set()
        for port, proc in processor.loffice_process_list.items():
            logging.info(f"shutting down libreoffice process on port {port}")
            proc["process"].kill()


def create_app() -> FastAPI:
    """
        :description: Creates FastAPI application with API router and starts libreoffice unoserver processes
        :return: FastAPI application instance
    """

    try:
        app = FastAPI(title="OCR Service",
                      description="OCR Service API",
                      version=OCR_SERVICE_VERSION,
                      debug=DEBUG_MODE,
                      lifespan=office_process_lifespan)
        app.include_router(api)

    except Exception:
        raise

    return app
