from __future__ import annotations

import sys
import time
import traceback
from typing import Any

from config import LOG_LEVEL
from ocr_service.dto.process_context import ProcessContext
from ocr_service.processor.converter import DocumentConverter
from ocr_service.processor.ocr_engine import OcrEngine
from ocr_service.utils.utils import detect_file_type, normalise_file_name_with_ext, setup_logging

sys.path.append("..")


class Processor:
    """Orchestrates document conversion and OCR processing via converter and OCR engine helpers."""

    def __init__(self):
        self.log = setup_logging(component_name="processor", log_level=LOG_LEVEL)
        self.log.debug("log level set to : " + str(LOG_LEVEL))
        self.loffice_process_list = {}
        self.converter = DocumentConverter(self.log, self.loffice_process_list)
        self.ocr_engine = OcrEngine(self.log)

    def _process(self, stream: bytes, file_name: str) -> tuple[str, dict]:
        """Process a document stream into extracted text and metadata.

        Flow:
          1) Detect file type + normalize filename for downstream converters.
          2) Convert/prepare content via DocumentConverter (LO/PDF/XML handling, fallback text extraction).
          3) Run OCR on images via OcrEngine when images are present.

        Notes:
          - In NO_OCR mode, PDFs are text-extracted and image inputs skip OCR (empty text + metadata.ocr_skipped).

        Args:
            stream: Raw document bytes.
            file_name: Caller-supplied name; used for temp files and type normalization.

        Returns:
            (text, metadata): Extracted text plus metadata such as content-type, pages, confidence, elapsed_time.
        """

        file_type = detect_file_type(stream)
        file_name = normalise_file_name_with_ext(file_name, stream)
        ctx = ProcessContext(stream=stream, file_name=file_name, file_type=file_type)
        ctx.metadata["content-type"] = self.converter.resolve_content_type(file_type)

        try:
            self.converter.prepare(ctx)

            self.log.info(
                "Detected file type for doc id: " + ctx.file_name + " | " + str(ctx.metadata["content-type"])
            )

            self.ocr_engine.run(ctx)
            ctx.output_text = self.converter.finalize_output_text(ctx.output_text)
        except Exception as converter_exception:
            raise Exception("Failed to convert/generate image content: "
                            + str(traceback.format_exc())) from converter_exception

        return ctx.output_text, ctx.metadata

    def process_stream(self, stream: bytes, file_name: str = "") -> tuple[str, dict]:
        """Public entry point that wraps _process with timing and logging.

        Args:
            stream: Raw document bytes.
            file_name: Optional original filename.

        Returns:
            (text, metadata): Extracted text and metadata, including elapsed_time.

        Behavior:
            Exceptions are logged to stdout and the method returns best-effort output/metadata.
        """

        output_text = ""
        doc_metadata: dict[str, Any] = {}
        elapsed_time: float = 0.0

        try:
            self.log.info("Processing file name:" + file_name)
            start_time = time.time()
            output_text, doc_metadata = self._process(stream, file_name=file_name)

            end_time = time.time()
            elapsed_time = float(round(float(end_time - start_time), 4))
            doc_metadata["elapsed_time"] = elapsed_time

            self.log.info("Finished processing file: " + file_name + " | Elapsed time: " + str(elapsed_time)
                          + " seconds")
        except Exception:
            traceback.print_exc(file=sys.stdout)

        return output_text, doc_metadata
