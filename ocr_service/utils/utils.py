from typing import List

import os

def get_app_info():
    """
        Returns general information about the application
        :return: application information stored as KVPs
    """
    return {"service_app_name": "ocr-service",
            "service_version": "0.0.1",
            "service_model": "None"}

def build_response(text, success=True, elapsed_time=0):
    return {"text": text,
            "successful": success,
            "elapsed_time" : elapsed_time
            }

def doc_metadata(content_type, page_count):
    return {"page-count":  page_count,
             "content-type": content_type
            }

def delete_tmp_files(file_paths: List[str]):
    for file_path in file_paths:
        os.remove(file_path)