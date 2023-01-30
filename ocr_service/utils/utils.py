from typing import List

import sys
import os

import filetype

import config

sys.path.append("..")

def get_app_info():
    """
        Returns general information about the application
        :return: application information stored as KVPs
    """
    return {"service_app_name": "ocr-service",
            "service_version": "0.0.1",
            "service_model": "None",
            "config": ""}

def build_response(text, success = True, elapsed_time = 0, log_message = "", metadata = {}):
    metadata["log_message"] = log_message
    metadata["success"] = success
    return {"text": text,
            "metadata" : metadata
            }

def doc_metadata(content_type, page_count):
    return {"page-count":  page_count,
            "content-type": content_type
           }

def delete_tmp_files(file_paths: List[str]):
    for file_path in file_paths:
        os.remove(file_path)


def detect_file_type(stream: bytes) -> filetype:
    file_type = filetype.guess(stream)
    return file_type