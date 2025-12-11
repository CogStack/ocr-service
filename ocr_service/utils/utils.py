import fcntl
import json
import logging
import os
import string
import sys
import xml.sax
from datetime import datetime
from sys import platform
from typing import Any

import filetype
import psutil

from config import LIBRE_OFFICE_LISTENER_PORT_RANGE, OCR_SERVICE_VERSION, TESSDATA_PREFIX, WORKER_PORT_MAP_FILE_PATH
import contextlib

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


def build_response(
    text,
    success: bool = True,
    log_message: str = "",
    footer: dict | None = None,
    metadata: dict | None  = None
) -> dict[str, Any]:

    if metadata is None:
        metadata = {}
    metadata["log_message"] = log_message

    if len(text) > 0:
        success = True
    else:
        success = False
        log_message = "No text has been generated."

    return {
        "text": text,
        "footer": footer,
        "metadata": metadata,
        "success": str(success),
        "timestamp": str(datetime.now())
    }


def delete_tmp_files(file_paths: list[str]) -> None:
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)

PRINTABLE = set(bytes(string.printable, "ascii")) | {9, 10, 13}

def is_file_content_plain_text(stream: bytes, threshold: float = 0.95) -> bool:
    if not stream:
        return False

    sample = stream[:4096]

    # If it can't be decoded as UTF-8 at all, treat as binary
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False

    printable = sum(1 for b in sample if b in PRINTABLE)
    return printable / len(sample) >= threshold

def is_file_type_html(stream: bytes) -> bool:
    head = stream[:2048].decode(errors="ignore").lower()
    return "<html" in head or "<!doctype html" in head

def is_file_type_xml(stream: bytes) -> bool:
    try:
        xml.sax.parseString(stream, xml.sax.ContentHandler())
        return True
    except Exception:
        logging.warning("Could not determine if file is XML.")
    return False

def is_file_type_rtf(stream: bytes) -> bool:
    head = stream[:32].lstrip()
    return head.startswith(b"{\\rtf")


def detect_file_type(stream: bytes) -> object | None:
    file_type = None
    try:
        file_type = filetype.guess(stream)
    except Exception:
        logging.error("Could not determine file Type")
    return file_type


def terminate_hanging_process(process_id: int) -> None:
    """ Kills process given process id.

    Args:
        process_id (int, optional): _description_. Defaults to None.
    """

    if not process_id:
        logging.warning("No process ID given or process ID is empty")
        return

    try:
        parent = psutil.Process(process_id)
    except psutil.NoSuchProcess:
        logging.warning(f"Process {process_id} does not exist")
        return

    children = parent.children(recursive=True)

    # First try terminate
    for p in children + [parent]:
        with contextlib.suppress(Exception):
            p.terminate()

    gone, alive = psutil.wait_procs(children + [parent], timeout=3)

    # Force kill anything still alive
    for p in alive:
        with contextlib.suppress(Exception):
            p.kill()

    logging.warning(
        "Killed process tree rooted at pid=%s (children=%s)",
        process_id,
        [c.pid for c in children],
    )


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

    pid: int = -1

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


def sync_port_mapping(worker_id: int = -1, worker_pid: int = -1):
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
        :description: Configure and setup a default logging handler to print messages to stdout.
    """
    root_logger = logging.getLogger(component_name)
    log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setFormatter(logging.Formatter(fmt=log_format))
    log_handler.setLevel(level=log_level)
    root_logger.setLevel(level=log_level)
    root_logger.propagate = False

    # only add the handler if a previous one does not exists
    handler_exists = False
    for h in root_logger.handlers:
        if isinstance(h, logging.StreamHandler) and h.level is log_handler.level:
            handler_exists = True
            break

    if not handler_exists:
        root_logger.addHandler(log_handler)

    return root_logger
