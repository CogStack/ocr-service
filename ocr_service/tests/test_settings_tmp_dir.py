import os
import tempfile
import unittest
from unittest.mock import patch

from ocr_service.settings import resolve_writable_tmp_dir, settings


class TestSettingsTmpDir(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.configured_tmp_dir = os.path.join(self.temp_dir.name, "configured_tmp")
        self.fallback_tmp_root = os.path.join(self.temp_dir.name, "fallback_root")
        self.expected_fallback = os.path.join(self.fallback_tmp_root, "ocr_service")
        self.original_ocr_tmp_dir = settings.OCR_TMP_DIR
        self.real_named_tempfile = tempfile.NamedTemporaryFile
        resolve_writable_tmp_dir.cache_clear()

    def tearDown(self) -> None:
        settings.OCR_TMP_DIR = self.original_ocr_tmp_dir
        resolve_writable_tmp_dir.cache_clear()
        self.temp_dir.cleanup()

    def _named_tempfile_with_configured_denied(self, *args, **kwargs):
        dir_path = kwargs.get("dir") if "dir" in kwargs else (args[0] if args else None)
        if dir_path and os.path.normpath(str(dir_path)) == os.path.normpath(self.configured_tmp_dir):
            raise PermissionError("permission denied")
        return self.real_named_tempfile(*args, **kwargs)

    @patch("ocr_service.settings.tempfile.gettempdir")
    def test_resolve_writable_tmp_dir_prefers_configured_path(self, gettempdir_mock):
        gettempdir_mock.return_value = self.fallback_tmp_root

        resolved = resolve_writable_tmp_dir(self.configured_tmp_dir)

        self.assertEqual(os.path.normpath(resolved), os.path.normpath(self.configured_tmp_dir))
        self.assertTrue(os.path.exists(self.configured_tmp_dir))

    @patch("ocr_service.settings.tempfile.gettempdir")
    def test_resolve_writable_tmp_dir_falls_back_when_configured_unwritable(self, gettempdir_mock):
        gettempdir_mock.return_value = self.fallback_tmp_root

        with patch(
            "ocr_service.settings.tempfile.NamedTemporaryFile",
            side_effect=self._named_tempfile_with_configured_denied,
        ):
            resolved = resolve_writable_tmp_dir(self.configured_tmp_dir)

        self.assertEqual(os.path.normpath(resolved), os.path.normpath(self.expected_fallback))
        self.assertTrue(os.path.exists(self.expected_fallback))

    @patch("ocr_service.settings.tempfile.gettempdir")
    def test_tmp_file_dir_property_uses_fallback_when_configured_unwritable(self, gettempdir_mock):
        settings.OCR_TMP_DIR = self.configured_tmp_dir
        gettempdir_mock.return_value = self.fallback_tmp_root

        with patch(
            "ocr_service.settings.tempfile.NamedTemporaryFile",
            side_effect=self._named_tempfile_with_configured_denied,
        ):
            resolved = settings.TMP_FILE_DIR

        self.assertEqual(os.path.normpath(resolved), os.path.normpath(self.expected_fallback))
