import builtins
import json
import os
import tempfile
import unittest
from unittest.mock import PropertyMock, patch

from ocr_service.settings import settings
from ocr_service.utils.utils import _resolve_worker_port_map_file_path, get_assigned_port, sync_port_mapping


class TestWorkerPortMap(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.primary_map_path = os.path.join(self.temp_dir.name, "primary", "worker_process_data.txt")
        self.fallback_tmp_root = os.path.join(self.temp_dir.name, "fallback_tmp")
        self.fallback_map_path = os.path.join(self.fallback_tmp_root, "ocr_service", "worker_process_data.txt")
        self.default_port = int(settings.LIBRE_OFFICE_LISTENER_PORT_RANGE[0])
        self.real_open = builtins.open
        _resolve_worker_port_map_file_path.cache_clear()

    def tearDown(self) -> None:
        _resolve_worker_port_map_file_path.cache_clear()
        self.temp_dir.cleanup()

    def _open_with_primary_denied(self, file_path, *args, **kwargs):
        if os.path.normpath(str(file_path)) == os.path.normpath(self.primary_map_path):
            raise PermissionError("permission denied")
        return self.real_open(file_path, *args, **kwargs)

    @patch.object(settings.__class__, "WORKER_PORT_MAP_FILE_PATH", new_callable=PropertyMock)
    @patch("ocr_service.utils.utils.tempfile.gettempdir")
    def test_resolve_worker_port_map_file_path_uses_fallback(self, gettempdir_mock, map_path_mock):
        map_path_mock.return_value = self.primary_map_path
        gettempdir_mock.return_value = self.fallback_tmp_root

        with patch("builtins.open", side_effect=self._open_with_primary_denied):
            resolved = _resolve_worker_port_map_file_path()

        self.assertEqual(os.path.normpath(resolved), os.path.normpath(self.fallback_map_path))
        self.assertTrue(os.path.exists(self.fallback_map_path))

    @patch.object(settings.__class__, "WORKER_PORT_MAP_FILE_PATH", new_callable=PropertyMock)
    @patch("ocr_service.utils.utils.tempfile.gettempdir")
    def test_sync_and_get_assigned_port_work_with_fallback(self, gettempdir_mock, map_path_mock):
        map_path_mock.return_value = self.primary_map_path
        gettempdir_mock.return_value = self.fallback_tmp_root

        worker_pid = 998877
        with patch("builtins.open", side_effect=self._open_with_primary_denied):
            sync_port_mapping(worker_id=0, worker_pid=worker_pid)
            assigned_port = get_assigned_port(current_worker_pid=worker_pid)

        self.assertEqual(assigned_port, self.default_port)

        with open(self.fallback_map_path, encoding="utf-8") as f:
            worker_port_map = json.load(f)
        self.assertEqual(worker_port_map.get(str(self.default_port)), str(worker_pid))

    def test_get_assigned_port_returns_default_on_invalid_json(self):
        bad_map_path = os.path.join(self.temp_dir.name, "bad", "worker_process_data.txt")
        os.makedirs(os.path.dirname(bad_map_path), exist_ok=True)
        with open(bad_map_path, encoding="utf-8", mode="w") as f:
            f.write("{broken-json")

        with patch("ocr_service.utils.utils._resolve_worker_port_map_file_path", return_value=bad_map_path):
            assigned_port = get_assigned_port(current_worker_pid=123456)

        self.assertEqual(assigned_port, self.default_port)

    @patch.object(settings.__class__, "WORKER_PORT_MAP_FILE_PATH", new_callable=PropertyMock)
    @patch("ocr_service.utils.utils.tempfile.gettempdir")
    def test_sync_port_mapping_does_not_raise_when_no_writable_path(self, gettempdir_mock, map_path_mock):
        map_path_mock.return_value = self.primary_map_path
        gettempdir_mock.return_value = self.fallback_tmp_root

        with patch("builtins.open", side_effect=PermissionError("permission denied")):
            sync_port_mapping(worker_id=0, worker_pid=112233)
