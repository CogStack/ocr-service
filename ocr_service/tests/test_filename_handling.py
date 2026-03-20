import os
import unittest
from unittest.mock import Mock

from ocr_service.processor.converter import DocumentConverter
from ocr_service.processor.processor import Processor
from ocr_service.settings import settings
from ocr_service.utils.utils import normalise_file_name_with_ext


class TestFilenameHandling(unittest.TestCase):

    def test_unknown_binary_name_remains_extensionless(self):
        file_name = normalise_file_name_with_ext("request-id", b"\x00\x01\x02\x03")
        self.assertEqual(file_name, "request-id")

    def test_detected_file_type_extension_is_used_when_name_has_no_suffix(self):
        file_type = Mock()
        file_type.extension = "docx"

        file_name = normalise_file_name_with_ext("request-id", b"\x00\x01\x02\x03", file_type)

        self.assertEqual(file_name, "request-id.docx")

    def test_processor_passes_extensionless_unknown_name_to_converter(self):
        processor = Processor()
        processor.converter = Mock()
        processor.converter.resolve_content_type.return_value = "application/octet-stream"
        processor.converter.finalize_output_text.side_effect = lambda output_text: output_text
        processor.ocr_engine = Mock()

        observed = {}

        def capture_context(ctx):
            observed["file_name"] = ctx.file_name
            observed["file_type"] = ctx.file_type

        processor.converter.prepare.side_effect = capture_context

        processor._process(b"\x00\x01\x02\x03", "request-id")

        self.assertEqual(observed["file_name"], "request-id")
        self.assertIsNone(observed["file_type"])

    def test_converter_builds_pdf_path_for_extensionless_input(self):
        doc_path, pdf_path = DocumentConverter._build_conversion_paths("request-id", uid="abc123")

        self.assertEqual(doc_path, os.path.join(settings.TMP_FILE_DIR, "abc123_request-id"))
        self.assertEqual(pdf_path, os.path.join(settings.TMP_FILE_DIR, "abc123_request-id.pdf"))
