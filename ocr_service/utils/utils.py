import os
import sys
import psutil

from sys import platform
from typing import List
from datetime import datetime

import filetype

sys.path.append("..")

def get_app_info() -> dict:
    """ Returns general information about the application.
    Used in the /api/info url.

    Returns:
        dict: _description_ . Application information stored as KVPs
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

def terminate_hanging_process(process_id : int) -> None:
    """ Kills process given process id.

    Args:
        process_id (int, optional): _description_. Defaults to None.
    """    
    if process_id != None:
        process = psutil.Process(process_id)
        process.kill()
        print("killed pid :" + str(process_id))
    else:
        print("No process ID given or process ID is empty")

def get_process_id_by_process_name(process_name : str = "") -> int:
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
