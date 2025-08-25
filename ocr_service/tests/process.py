import logging
import os
import time
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ocr_service.app import create_app
from ocr_service.utils.utils import sync_port_mapping

from ..tests.test_utils import get_file


class TestOcrServiceProcessor(unittest.TestCase):

    ENDPOINT_API_INFO = "/api/info"
    ENDPOINT_PROCESS_SINGLE = "/api/process"

    app: FastAPI
    client: TestClient
    log: logging.Logger

    def __init__(self, *args, **kwargs) -> None:
        super(TestOcrServiceProcessor, self).__init__(*args, **kwargs)

    @classmethod
    def _setup_logging(cls):
        log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
        logging.basicConfig(format=log_format, level=logging.INFO)
        cls.log = logging.getLogger(__name__)

    @classmethod
    def tearDownClass(cls):
        # ensure lifespan shutdown + resource cleanup (unoserver, etc.)
        try:
            cls.client_ctx.__exit__(None, None, None)
        except Exception:
            pass

    @classmethod
    def setUpClass(cls):
        """
            Initializes the resources before all the tests are run. It is run only once.
            The app instance is created only once when starting all the unit tests.
            :return:
        """
        cls._setup_logging()
        sync_port_mapping(worker_id=0, worker_pid=os.getpid())
        cls.app = create_app()
        # This ensures lifespan (startup/shutdown) events are run
        cls.client_ctx = TestClient(cls.app, raise_server_exceptions=False)
        cls.client_ctx.__enter__()
        cls.client = cls.client_ctx
        # allow LibreOffice processes to initialize
        time.sleep(15)

    def test_request_api_info(self):
        response = self.client.get(self.ENDPOINT_API_INFO)
        self.assertEqual(response.status_code, 200)
        api_info = response.json()
        self.assertIsInstance(api_info, dict)
        self.assertGreater(len(api_info.keys()), 0)

    def _test_file(self, filename: str):
        test_file = get_file(f"generic/{filename}")
        files = {"file": (filename, test_file, "application/octet-stream")}
        response = self.client.post(self.ENDPOINT_PROCESS_SINGLE, files=files)
        data = response.json()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("result", data)
        self.assertIn("text", data["result"])
        self.assertGreaterEqual(len(data["result"]["text"]), 100)

    def test_process_doc(self):
        self.log.info("Testing DOC file processing")
        self._test_file("pat_id_1.doc")

    def test_process_docx(self):
        self.log.info("Testing DOCX file processing")
        self._test_file("pat_id_1.docx")

    def test_process_pdf(self):
        self.log.info("Testing PDF file processing")
        self._test_file("pat_id_1.pdf")

    def test_process_odt(self):
        self.log.info("Testing ODT file processing")
        self._test_file("pat_id_1.odt")

    def test_process_rtf(self):
        self.log.info("Testing RTF file processing")
        self._test_file("pat_id_1.rtf")

    def test_process_txt(self):
        self.log.info("Testing TXT file processing")
        self._test_file("pat_id_1.txt")

    def test_process_png(self):
        self.log.info("Testing PNG file processing")
        self._test_file("pat_id_1.png")

    def test_process_html(self):
        self.log.info("Testing HTML file processing")
        self._test_file("pat_id_1.html")
