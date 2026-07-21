import os
import unittest
from pathlib import Path
from unittest.mock import Mock

from ocr_service.dto.process_context import ProcessContext
from ocr_service.processor.converter import DocumentConverter
from ocr_service.processor.processor import Processor
from ocr_service.settings import settings
from ocr_service.utils.utils import is_encrypted_office_document, normalise_file_name_with_ext

TEST_RESOURCES = Path(__file__).resolve().parent / "resources"


class TestFilenameHandling(unittest.TestCase):

    def test_unknown_binary_name_remains_extensionless(self):
        file_name = normalise_file_name_with_ext("request-id", b"\x00\x01\x02\x03")
        self.assertEqual(file_name, "request-id")

    def test_detected_file_type_extension_is_used_when_name_has_no_suffix(self):
        file_type = Mock()
        file_type.extension = "docx"

        file_name = normalise_file_name_with_ext("request-id", b"\x00\x01\x02\x03", file_type)

        self.assertEqual(file_name, "request-id.docx")

    def test_encrypted_ooxml_extension_is_inferred_when_name_has_no_suffix(self):
        stream = (TEST_RESOURCES / "docs/invalid/word_enc_noerror.docx").read_bytes()

        file_name = normalise_file_name_with_ext("request-id", stream)

        self.assertEqual(file_name, "request-id.docx")
        self.assertTrue(is_encrypted_office_document(stream))

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

    def test_converter_skips_encrypted_office_without_unoserver(self):
        stream = (TEST_RESOURCES / "docs/invalid/word_enc_noerror.docx").read_bytes()
        converter = DocumentConverter(Mock(), {})
        converter._preprocess_doc = Mock(return_value=b"")  # type: ignore[method-assign]
        ctx = ProcessContext(stream=stream, file_name="request-id.docx", file_type=None)

        converter.prepare(ctx)

        converter._preprocess_doc.assert_not_called()
        self.assertTrue(ctx.metadata["encrypted"])
        self.assertEqual(ctx.metadata["unsupported_reason"], "encrypted_office_document")

    def test_rtf_falls_back_to_text_when_converted_pdf_handling_fails(self):
        converter = DocumentConverter(Mock(), {})
        converter._preprocess_doc = Mock(return_value=b"%PDF-1.7\nnot usable")  # type: ignore[method-assign]
        converter._handle_pdf_stream = Mock(side_effect=RuntimeError("bad converted pdf"))  # type: ignore[method-assign]
        ctx = ProcessContext(stream=b"{\\rtf1\\ansi fallback text}", file_name="request-id.rtf", file_type=None)

        converter.prepare(ctx)

        self.assertIn("fallback text", ctx.output_text)
        self.assertEqual(ctx.pdf_stream, b"")
        self.assertEqual(ctx.metadata["fallback_reason"], "converted_pdf_handling_failed")

    def test_xml_falls_back_to_text_when_converted_pdf_handling_fails(self):
        converter = DocumentConverter(Mock(), {})
        converter._preprocess_xml_to_pdf = Mock(return_value=b"")  # type: ignore[method-assign]
        converter._preprocess_doc = Mock(return_value=b"%PDF-1.7\nnot usable")  # type: ignore[method-assign]
        converter._handle_pdf_stream = Mock(side_effect=RuntimeError("bad converted pdf"))  # type: ignore[method-assign]
        ctx = ProcessContext(
            stream=b'<?xml version="1.0"?><root><note>fallback text</note></root>',
            file_name="request-id.xml",
            file_type=None,
        )

        converter.prepare(ctx)

        self.assertIn("fallback text", ctx.output_text)
        self.assertEqual(ctx.pdf_stream, b"")
        self.assertEqual(ctx.metadata["fallback_reason"], "converted_pdf_handling_failed")

    def test_docx_falls_back_to_document_xml_when_libreoffice_produces_no_pdf(self):
        stream = (TEST_RESOURCES / "docs/generic/pat_id_1.docx").read_bytes()
        converter = DocumentConverter(Mock(), {})
        converter._preprocess_doc = Mock(return_value=b"")  # type: ignore[method-assign]
        ctx = ProcessContext(stream=stream, file_name="request-id.docx", file_type=None)

        converter.prepare(ctx)

        self.assertIn("Bart Davidson", ctx.output_text)
        self.assertEqual(ctx.metadata["fallback_reason"], "no_pdf_produced")

    def test_odt_falls_back_to_content_xml_when_libreoffice_produces_no_pdf(self):
        stream = (TEST_RESOURCES / "docs/generic/pat_id_1.odt").read_bytes()
        converter = DocumentConverter(Mock(), {})
        converter._preprocess_doc = Mock(return_value=b"")  # type: ignore[method-assign]
        ctx = ProcessContext(stream=stream, file_name="request-id.odt", file_type=None)

        converter.prepare(ctx)

        self.assertIn("Bart Davidson", ctx.output_text)
        self.assertEqual(ctx.metadata["fallback_reason"], "no_pdf_produced")
