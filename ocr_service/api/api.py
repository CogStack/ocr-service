import json
import logging
import os
import sys
import uuid

from flask import Blueprint, Response, request

from config import *
from ocr_service.utils.utils import get_app_info

from ..processor import Processor
from ..utils import build_response

sys.path.append("..")

log = logging.getLogger("API")
log.setLevel(level=os.getenv("APP_LOG_LEVEL", LOG_LEVEL))

api = Blueprint(name="api", import_name="api", url_prefix="/api")

processor = Processor()

@api.route("/info", methods=["GET"])
def info() -> Response:
    return Response(response=json.dumps(get_app_info()), status=200, mimetype="application/json")

@api.route("/process", methods=["POST"])
def process_file() -> Response:
    stream = None
    file_name = None

    # if it is sent via the file parameter (file keeps its original name)
    if len(request.files):
        file = list(request.files.values())[0]
        stream = file.stream.read()
        file_name = file.filename
        del file
        log.info("Processing file given via 'file' parameter, file name: " + file_name)
    else:
        # if it is sent as a data-binary
        log.info("Processing binary as data-binary, generating temporary file name...")
        file_name = uuid.uuid4().hex
        log.info("Generated file name:" + file_name)
       
        stream = request.get_data(cache=False, as_text=False, parse_form_data=False)

    output_text, doc_metadata = processor.process_stream(stream=stream, file_name=file_name)

    if len(output_text) > 0:
        response = build_response(output_text, metadata=doc_metadata)
        return Response(response=json.dumps({"result" : response}), status=200, mimetype="application/json")
    else:
        response = build_response(output_text, success=False, log_message="No text has been generated", metadata=doc_metadata)
        return Response(response=json.dumps({"result" : response}), status=500, mimetype="application/json")

@api.route("/process_bulk", methods=["POST"])
def process_bulk() -> Response:
    return Response(response=json.dumps({"response" : "Not yet implemented"}), status=501, mimetype="application/json")