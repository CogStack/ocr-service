import json
import logging
import sys
import uuid
import base64
import traceback

from flask import Response, request

from multiprocessing import Pool

from config import CPU_THREADS, TESSERACT_TIMEOUT, LOG_LEVEL
from ocr_service.api.api_blueprint import ApiBlueprint
from ocr_service.utils.utils import build_response, get_app_info, setup_logging

sys.path.append("..")


api = ApiBlueprint(name="api", import_name="api", url_prefix="/api")
log = setup_logging("api", log_level=LOG_LEVEL)


@api.route("/info", methods=["GET"])
def info() -> Response:
    return Response(response=json.dumps(get_app_info()),
                    status=200,
                    mimetype="application/json")


@api.route("/process", methods=["POST"])
def process() -> Response:
    stream = None
    file_name: str = ""

    footer = {}

    global log

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

        try:
            record = json.loads(stream)
            if isinstance(record, dict) and "binary_data" in record.keys():
                stream = base64.b64decode(record["binary_data"])

                if "footer" in record.keys():
                    footer = record["footer"]
                    log.info("Footer found in the request.")

            log.info("Stream contains valid JSON.")
        except json.JSONDecodeError:
            log.warning("Stream does not contain valid JSON.")

    output_text, doc_metadata = api.processor.process_stream(stream=stream, file_name=file_name)

    if len(output_text) > 0:
        response = build_response(output_text, footer=footer, metadata=doc_metadata)
        return Response(response=json.dumps({"result": response}),
                        status=200,
                        mimetype="application/json")
    else:
        response = build_response(output_text,
                                  metadata=doc_metadata,
                                  success=False,
                                  log_message="No text has been generated")

        return Response(response=json.dumps({"result": response}),
                        status=500,
                        mimetype="application/json")

@api.route("/process_file", methods=["POST"])
def process_file() -> Response:
    stream = None
    file_name: str = ""

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

    output_text, doc_metadata = api.processor.process_stream(stream=stream, file_name=file_name)

    if len(output_text) > 0:
        response = build_response(output_text, metadata=doc_metadata)
        return Response(response=json.dumps({"result": response}),
                        status=200,
                        mimetype="application/json")
    else:
        response = build_response(output_text, success=False,
                                  log_message="No text has been generated",
                                  metadata=doc_metadata)
        return Response(response=json.dumps({"result": response}),
                        status=500,
                        mimetype="application/json")


@api.route("/process_bulk", methods=["POST"])
def process_bulk() -> Response:
    file_streams = {}

    for param_name in request.files:
        file_storage = request.files[param_name]
        file_streams[file_storage.filename] = file_storage.read()

    proc_results = list()
    ocr_results = []

    with Pool(processes=CPU_THREADS) as process_pool:
        count = 0

        for file_name, file_stream in file_streams.items():
            count += 1
            proc_results.append(process_pool.starmap_async(api.processor.process_stream,
                                                           [(file_name, file_stream)],
                                                           chunksize=1, error_callback=logging.error))

        try:
            for result in proc_results:
                ocr_results.append(result.get(timeout=TESSERACT_TIMEOUT))
        except Exception:
            raise Exception("OCR exception generated by worker: " + str(traceback.format_exc()))

    return Response(response=json.dumps({"response": "Not yet implemented"}), status=501, mimetype="application/json")
