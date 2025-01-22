import fcntl
import json
import os
import sys
import psutil
import logging

from sys import platform
from typing import List
from datetime import datetime

import filetype
import xml.sax

from config import OCR_SERVICE_VERSION, TESSDATA_PREFIX, WORKER_PORT_MAP_FILE_PATH, \
                   LIBRE_OFFICE_LISTENER_PORT_RANGE

sys.path.append("..")


def get_app_info() -> dict:
    """ Returns general information about the application.
    Used in the /api/info url.

    Returns:
        dict: _description_ . Application information stored as KVPs
    """
    return {"service_app_name": "ocr-service",
            "service_version": OCR_SERVICE_VERSION,
            "service_model": TESSDATA_PREFIX,
            "config": ""}


def build_response(text, success: bool = True, log_message: str = "", metadata: dict = {}) -> dict:
    metadata["log_message"] = log_message

    return {
        "text": text,
        "metadata": metadata,
        "success": str(success),
        "timestamp": str(datetime.now())
    }


def delete_tmp_files(file_paths: List[str]) -> None:
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)


def is_file_type_xml(stream: bytes) -> bool:
    try:
        xml.sax.parseString(stream, xml.sax.ContentHandler())
        return True
    except xml.sax.SAXParseException:
        logging.warning("Could not determine if file is XML.")
    return False


def detect_file_type(stream: bytes) -> filetype:
    file_type = filetype.guess(stream)
    return file_type


def terminate_hanging_process(process_id: int) -> None:
    """ Kills process given process id.

    Args:
        process_id (int, optional): _description_. Defaults to None.
    """

    if process_id is not None:
        process = psutil.Process(process_id)
        process.kill()
        logging.warning("killed pid:" + str(process_id))
    else:
        logging.warning("No process ID given or process ID is empty")


def get_process_id_by_process_name(process_name: str = "") -> int:
    """ Looks for specific process in process_name
    Used mostly for making sure that the 'soffice' process times out 
    forcefully (it has a habit of hanging or getting stuck so
    we manually shut it down and restart it).

    Args:
        process_name (str, optional): _description_. Defaults to "", 
        actual process name or process path

    Returns:
        int: _description_ . pid, process ID
    """

    pid: int = None

    if "soffice" in process_name:
        soffice_process_name = "soffice"
        if platform == "linux" or platform == "linux2":
            soffice_process_name = "soffice.bin"
    else:
        soffice_process_name = ""

    for proc in psutil.process_iter():
        if proc.name() in process_name or proc.name() in soffice_process_name:
            pid = proc.pid
            break

    return pid


def sync_port_mapping(worker_id: int = None, worker_pid: int = None):
    open_mode = "r+"

    if not os.path.exists(WORKER_PORT_MAP_FILE_PATH):
        open_mode = "w+"

    with open(WORKER_PORT_MAP_FILE_PATH, encoding="utf-8", mode=open_mode) as f:
        fcntl.lockf(f, fcntl.LOCK_EX)

        port_mapping = {}
        text = f.read()

        if len(text) > 0:
            port_mapping = json.loads(text)

        port_mapping[str((LIBRE_OFFICE_LISTENER_PORT_RANGE[0] + worker_id))] = str(worker_pid)
        output = json.dumps(port_mapping, indent=1)
        f.seek(0)
        f.truncate(0)
        f.write(output)
        fcntl.lockf(f, fcntl.LOCK_UN)


def get_assigned_port(current_worker_pid: int) -> int | bool:
    port_mapping: dict = {}

    open_mode = "r+"

    if os.path.exists(WORKER_PORT_MAP_FILE_PATH):
        with open(WORKER_PORT_MAP_FILE_PATH, encoding="utf-8", mode=open_mode) as f:
            text = f.read()
            if len(text) > 0:
                port_mapping = json.loads(text)
                for port_num, worker_pid in port_mapping.items():
                    if int(worker_pid) == int(current_worker_pid):
                        return int(port_num)

    return False


def setup_logging(component_name: str = "config_logger", log_level: int = 20) -> logging.Logger:
    """
        :description: Configure and setup a default logging handler to print messages to stdout
    """
    root_logger = logging.getLogger(component_name)
    log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setFormatter(logging.Formatter(fmt=log_format))
    log_handler.setLevel(level=log_level)
    root_logger.setLevel(level=log_level)

    # only add the handler if a previous one does not exists
    handler_exists = False
    for h in root_logger.handlers:
        if isinstance(h, logging.StreamHandler) and h.level is log_handler.level:
            handler_exists = True
            break

    if not handler_exists:
        root_logger.addHandler(log_handler)

    return root_logger
