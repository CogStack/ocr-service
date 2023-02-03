import os
import sys
import psutil

from sys import platform
from typing import List
from datetime import datetime

import filetype

sys.path.append("..")

def get_app_info() -> dict:
    """
        Returns general information about the application
        :return: application information stored as KVPs
    """
    return {"service_app_name": "ocr-service",
            "service_version": "0.0.1",
            "service_model": "None",
            "config": ""}

def build_response(text, success = True, log_message = "", metadata = {}) -> dict:
    metadata["log_message"] = log_message

    return {
        "text" : text,
        "metadata": metadata,
        "success" : str(success),
        "timestamp" :str(datetime.now())
    }

def delete_tmp_files(file_paths: List[str]) -> None:
    for file_path in file_paths:
        os.remove(file_path)

def detect_file_type(stream: bytes) -> filetype:
    file_type = filetype.guess(stream)
    return file_type

def terminate_hanging_process(process_id : int = None) -> None:
    if process_id != None:
        process = psutil.Process(process_id)
        process.kill()
        print("killed pid :" + str(process_id))
    else:
        print("No process ID given or process ID is empty")

def get_process_id_by_process_name(process_name : str = "") -> int:
    pid = None

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
