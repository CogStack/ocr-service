import base64
import logging
import sys
import traceback
import uuid
from multiprocessing import Pool
from typing import IO, Any, Optional

import orjson
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import ORJSONResponse, Response
from starlette.datastructures import FormData

from config import CPU_THREADS, LOG_LEVEL, TESSERACT_TIMEOUT
from ocr_service.processor.processor import Processor
from ocr_service.utils.utils import build_response, get_app_info, setup_logging

sys.path.append("..")


api = APIRouter(prefix="/api")
log = setup_logging("api", log_level=LOG_LEVEL)


@api.get("/health", response_class=ORJSONResponse)
def health() -> ORJSONResponse:
    return ORJSONResponse(content={"status": "healthy"})


@api.get("/info")
def info() -> ORJSONResponse:
    return ORJSONResponse(content=get_app_info())


@api.post("/process")
def process(request: Request, file: Optional[UploadFile] = File(default=None)) -> ORJSONResponse:
    """
     Processes raw binary input stream, file, or
        JSON containing the binary_data field in base64 format

    Returns:
        Response: json with the result of the OCR processing
    """

    footer: dict = {}
    file_name: str = ""
    stream: bytes = b""
    output_text: str = ""
    doc_metadata: dict = {}

    if file:
        file_name = file.filename if file.filename else ""
        stream = file.file.read()
        log.info(f"Processing file given via 'file' parameter, file name: {file_name}")
    else:
        file_name = uuid.uuid4().hex
        log.info(f"Processing binary as data-binary, generated file name: {file_name}")

        environ: dict = request.scope.get("wsgi_environ", {})
        input_stream: IO[bytes] = environ.get("wsgi.input", {})

        raw_body: bytes = input_stream.read()

        try:
            record = orjson.loads(raw_body)
            if isinstance(record, list) and len(record) > 0:
                record = record[0]

            footer = record.get("footer", {}) # type: ignore
            log.info("Stream contains valid JSON.")

            # JSON with base64 field
            if isinstance(record, dict) and "binary_data" in record:
                encoded: str = record.get("binary_data", {})

                if encoded not in (None, "", {}):
                    try:
                        stream = base64.b64decode(encoded, validate=True)
                        log.info("binary_data successfully base64-decoded")
                    except Exception:
                        log.warning("binary_data is not valid base64; forcing bytes")
                        stream = bytes(encoded) if isinstance(encoded, bytes | bytearray) \
                                else str(encoded).encode("utf-8")
                else:
                    stream = b""
            else:
                log.info("JSON found but no binary_data; using raw body")
                stream = raw_body

        except Exception:
            log.warning("Stream does not contain valid JSON." + str(traceback.format_exc()))

            try:
                try:
                    stream = base64.b64decode(raw_body, validate=True)
                    log.info("Attempting to treat as base64 encoded string")
                except Exception:
                    log.info("Failed, forcing bytes")
                    stream = raw_body if isinstance(raw_body, bytes | bytearray) else str(raw_body).encode("utf-8")
            except Exception:
                stream = raw_body
                log.warning("Could not convert raw body to utf-8, using raw input.")

    processor: Processor = request.app.state.processor

    try:
        if stream:
            output_text, doc_metadata = processor.process_stream(stream=stream, file_name=file_name)
    except Exception:
        return ORJSONResponse(content={"detail": "Service is busy, try again"}, status_code=503)
    
    log.debug(f"Stream size: {len(stream)} bytes")

    code = 200 if len(output_text) > 0 or not stream else 500

    response: dict[Any, Any] = {"result": build_response(output_text, footer=footer, metadata=doc_metadata)}

    return ORJSONResponse(content=response, status_code=code, media_type="application/json")


@api.post("/process_file")
def process_file(request: Request, file: UploadFile = File(...)) -> ORJSONResponse:

    file_name: str = file.filename if file.filename else ""
    stream: bytes = file.file.read()
    log.info(f"Processing file: {file_name}")

    processor: Processor = request.app.state.processor

    output_text: str = ""
    doc_metadata: dict = {}

    try:
        if stream:
            output_text, doc_metadata = processor.process_stream(stream=stream, file_name=file_name)
    except Exception:
        return ORJSONResponse(content={"detail": "Service is busy, try again"}, status_code=503)

    code = 200 if len(output_text) > 0 or not stream else 500

    response: dict[Any, Any] = {"result": build_response(output_text, metadata=doc_metadata)}

    return ORJSONResponse(content=response, status_code=code, media_type="application/json")


@api.post("/process_bulk")
def process_bulk(request: Request, files: list[UploadFile] = File(...)) -> Response:
    """
        Processes multiple files in a single request (multipart/form-data with multiple 'files').
    """

    form: FormData | None = request._form
    file_streams = {}

    proc_results = list()
    ocr_results = []

    processor: Processor = request.app.state.processor

    if isinstance(form, FormData):
        # collect uploaded files
        for name, file in form.items():
            if isinstance(file, UploadFile):
                content = file.read()
                file_streams[file.filename] = content

        with Pool(processes=CPU_THREADS) as process_pool:
            count = 0

            for file_name, file_stream in file_streams.items():
                count += 1
                proc_results.append(process_pool.starmap_async(processor.process_stream,
                                                               [(file_name, file_stream)],
                                                               chunksize=1,
                                                               error_callback=logging.error))
            try:
                for result in proc_results:
                    ocr_results.append(result.get(timeout=TESSERACT_TIMEOUT))
            except Exception as exception:
                raise Exception("OCR exception generated by worker: " + str(traceback.format_exc())) from exception

    return Response(content={"response": "Not yet implemented"}, status_code=200)
