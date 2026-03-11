import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ocr_service.api.health import health_api


class DummySubprocess:
    def __init__(self, pid: int, returncode: int | None = None) -> None:
        self.pid = pid
        self._returncode = returncode

    def poll(self) -> int | None:
        return self._returncode


class DummyPsutilProcess:
    def __init__(self, running: bool, process_status: str) -> None:
        self._running = running
        self._status = process_status

    def is_running(self) -> bool:
        return self._running

    def status(self) -> str:
        return self._status


class DummyProcessor:
    def __init__(self, loffice_process_list):
        self.loffice_process_list = loffice_process_list


class TestHealthApi(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(health_api)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def test_health_returns_healthy(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})

    def test_ready_returns_503_when_processor_not_initialized(self):
        response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data.get("status"), "not_ready")
        self.assertIn("processor_not_initialized", data.get("issues", []))

    def test_ready_returns_503_when_libreoffice_process_exited(self):
        self.app.state.processor = DummyProcessor(
            {
                "9900": {
                    "process": DummySubprocess(pid=12345, returncode=1),
                    "pid": 12345,
                    "unhealthy": False,
                }
            }
        )

        response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data.get("status"), "not_ready")
        self.assertIn("libreoffice_process_exited:9900", data.get("issues", []))

    @patch("ocr_service.api.health.psutil.Process")
    @patch("ocr_service.api.health.psutil.pid_exists", return_value=True)
    def test_ready_returns_200_for_running_libreoffice_process(self, _pid_exists, process_mock):
        process_mock.return_value = DummyPsutilProcess(running=True, process_status="sleeping")
        self.app.state.processor = DummyProcessor(
            {
                "9900": {
                    "process": DummySubprocess(pid=12345, returncode=None),
                    "pid": 12345,
                    "unhealthy": False,
                }
            }
        )

        response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready", "libreoffice_processes": 1})

