import unittest
from unittest.mock import MagicMock, Mock, patch

from ocr_service.processor.converter import DocumentConverter


class TestPdfTextCleanup(unittest.TestCase):
    def test_closes_text_pages_pages_and_document_after_extraction(self):
        first_textpage = Mock()
        first_textpage.get_text_bounded.return_value = "first"
        first_page = Mock()
        first_page.get_textpage.return_value = first_textpage

        second_textpage = Mock()
        second_textpage.get_text_bounded.return_value = "second"
        second_page = Mock()
        second_page.get_textpage.return_value = second_textpage

        pdf = MagicMock()
        pdf.__len__.return_value = 2
        pdf.__iter__.return_value = iter([first_page, second_page])
        converter = DocumentConverter(Mock(), {})

        with patch("ocr_service.processor.converter.pdfium.PdfDocument", return_value=pdf):
            text, metadata = converter._pdf_to_text(b"pdf")

        self.assertEqual(text, "firstsecond")
        self.assertEqual(metadata["pages"], 2)
        first_textpage.close.assert_called_once_with()
        second_textpage.close.assert_called_once_with()
        first_page.close.assert_called_once_with()
        second_page.close.assert_called_once_with()
        pdf.close.assert_called_once_with()

    def test_closes_resources_and_reraises_extraction_error(self):
        textpage = Mock()
        textpage.get_text_bounded.side_effect = RuntimeError("bad text page")
        page = Mock()
        page.get_textpage.return_value = textpage
        pdf = MagicMock()
        pdf.__len__.return_value = 1
        pdf.__iter__.return_value = iter([page])
        log = Mock()
        converter = DocumentConverter(log, {})

        with (
            patch("ocr_service.processor.converter.pdfium.PdfDocument", return_value=pdf),
            self.assertRaisesRegex(RuntimeError, "bad text page"),
        ):
            converter._pdf_to_text(b"pdf")

        textpage.close.assert_called_once_with()
        page.close.assert_called_once_with()
        pdf.close.assert_called_once_with()
        log.exception.assert_called_once_with("PDF text extraction failed on page %s", 1)


if __name__ == "__main__":
    unittest.main()
