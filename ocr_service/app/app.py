import contextlib
import logging
import os
import subprocess
import time
from threading import Event, Thread
from typing import Any, cast

import psutil
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from ocr_service.api import api
from ocr_service.processor.processor import Processor
from ocr_service.settings import settings
from ocr_service.utils.utils import cleanup_stale_lo_profiles, get_assigned_port, terminate_hanging_process

# guard so LibreOffice startup runs only once per worker
_started: bool = False


def start_office_server(port_num: str) -> dict[str, Any]:
    """
        :description: Starts LibreOffice unoserver process for OCR processing
        :param port_num: Port number to start the server on
        :return: Dictionary with process information
    """

    # used in unoserver 2.1>=
    uno_port = str(int(port_num) + 1000)  # e.g. XML-RPC 9900, UNO 10900
    user_installation = f"{settings.TMP_FILE_DIR}/lo_profile_{port_num}"

    lo_python = cast(str, settings.LIBRE_OFFICE_PYTHON_PATH)
    lo_exec = cast(str, settings.LIBRE_OFFICE_EXEC_PATH)

    loffice_process: dict[str, Any] = {
        "process": subprocess.Popen(
            args=[
                lo_python,
                "-m",
                "unoserver.server",
                "--interface", settings.LIBRE_OFFICE_NETWORK_INTERFACE,
                "--uno-interface", settings.LIBRE_OFFICE_NETWORK_INTERFACE,
                "--executable", lo_exec,
                "--port", port_num,
                "--uno-port", uno_port,
                "--user-installation", user_installation,
               # "--logfile", f"loffice_{port_num}.log"
            ], # type: ignore
            cwd=settings.TMP_FILE_DIR,
            close_fds=True,
            shell=False
        ), # type: ignore
        "pid": "",
        "port": port_num,
        "used": False,
        "unhealthy": False
    }

    logging.info("LIBRE_OFFICE_STARTED PID: " + str(loffice_process["process"].pid) + " PORT: " + str(port_num))

    loffice_process["pid"] = loffice_process["process"].pid

    return loffice_process


def start_office_converter_servers() -> dict[str, Any]:
    """
        :description: Starts LibreOffice unoserver processes for OCR processing
        :return: Dictionary with port numbers and process information
    """

    loffice_processes: dict[str, Any] = {}
    assigned_port = get_assigned_port(os.getpid())
    _port = str(assigned_port)

    for port_num in settings.LIBRE_OFFICE_LISTENER_PORT_RANGE:
        _port_num = str(port_num)
        logging.info(
            "STARTED WORKER ON PORT: %s PID: %s ASSIGNED PORT: %s",
            _port_num, os.getpid(), assigned_port,
        )
        if port_num == assigned_port and settings.OCR_WEB_SERVICE_THREADS == 1:
            process = start_office_server(_port_num)
            loffice_processes[_port_num] = process
            break
        elif (settings.OCR_WEB_SERVICE_WORKERS == 1 and settings.OCR_WEB_SERVICE_THREADS > 1) or settings.DEBUG_MODE:
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
                        terminate_hanging_process(proc["process"].pid)
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
                        terminate_hanging_process(proc["process"].pid)
                    restarted_proc = start_office_server(_port)
                    processor.loffice_process_list[_port] = restarted_proc

                logging.info(f"libreoffice OK: pid={libre_office_process.pid}, port={_port}")
        except Exception as e:
            logging.error("error in libreoffice monitor thread: " + str(e))

        time.sleep(settings.LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL)


def create_app() -> FastAPI:
    """
        :description: Creates FastAPI application with API router and starts libreoffice unoserver processes
        :return: FastAPI application instance
    """

    global _started

    try:
        app = FastAPI(title="OCR Service",
                      description="OCR Service API",
                      version=settings.OCR_SERVICE_VERSION,
                      default_response_class=ORJSONResponse,
                      debug=settings.DEBUG_MODE)
        app.include_router(api)

        # start once per worker
        if not _started:
            _started = True
            # clean stale LibreOffice profiles before starting new processes
            cleanup_stale_lo_profiles()
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
                            terminate_hanging_process(p.pid)
                        except Exception as e:
                            logging.error("error in when shutting down libreoffice process: " + str(e))
            atexit.register(cleanup)

    except Exception:
        raise

    return app
