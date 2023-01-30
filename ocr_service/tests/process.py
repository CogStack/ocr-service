import json
import logging
import time
import unittest

from ocr_service.app.app import create_app

from ..tests.test_utils import *


class TestOcrServiceProcessor(unittest.TestCase):

    ENDPOINT_API_INFO = '/api/info'
    ENDPOINT_PROCESS_SINGLE = '/api/process'

    def __init__(self, *args, **kwargs) -> None:
        super(TestOcrServiceProcessor, self).__init__(*args, **kwargs)

    @staticmethod
    def client(app):
        return app.test_client()

    @staticmethod
    def runner(app):
        return app.test_cli_runner()
    
    def test_request_api_info(cls):
        response = cls.client.get(cls.ENDPOINT_API_INFO)
        api_info = json.loads(response.data)
        assert len(api_info.keys()) > 0
    
    def test_request_api_process_doc(cls):
        file = get_file("generic/pat_id_1.doc")
        response = cls.client.post(cls.ENDPOINT_PROCESS_SINGLE, data=file)
        response = json.loads(response.data)
        assert len(response["result"]["text"]) > 100

    def test_request_api_process_docx(cls):
        file = get_file("generic/pat_id_1.docx")
        response = cls.client.post(cls.ENDPOINT_PROCESS_SINGLE, data=file)
        response = json.loads(response.data)
        assert len(response["result"]["text"]) > 100

    def test_request_api_process_pdf(cls):
        file = get_file("generic/pat_id_1.pdf")
        response = cls.client.post(cls.ENDPOINT_PROCESS_SINGLE, data=file)
        response = json.loads(response.data)
        assert len(response["result"]["text"]) > 100

    def test_request_api_process_odt(cls):
        file = get_file("generic/pat_id_1.odt")
        response = cls.client.post(cls.ENDPOINT_PROCESS_SINGLE, data=file)
        response = json.loads(response.data)
        assert len(response["result"]["text"]) > 100

    def test_request_api_process_rtf(cls):
        file = get_file("generic/pat_id_1.rtf")
        response = cls.client.post(cls.ENDPOINT_PROCESS_SINGLE, data=file)
        response = json.loads(response.data)
        assert len(response["result"]["text"]) > 100

    def test_request_api_process_txt(cls):
        file = get_file("generic/pat_id_1.txt")
        response = cls.client.post(cls.ENDPOINT_PROCESS_SINGLE, data=file)
        response = json.loads(response.data)
        assert len(response["result"]["text"]) > 100
    
    def test_request_api_process_png(cls):
        file = get_file("generic/pat_id_1.png")
        response = cls.client.post(cls.ENDPOINT_PROCESS_SINGLE, data=file)
        response = json.loads(response.data)
        assert len(response["result"]["text"]) > 100

    def test_request_api_process_html(cls):
        file = get_file("generic/pat_id_1.html")
        response = cls.client.post(cls.ENDPOINT_PROCESS_SINGLE, data=file)
        response = json.loads(response.data)
        assert len(response["result"]["text"]) > 100

    # Static initialization methods
    #
    @classmethod
    def setUpClass(cls):
        """
        Initializes the resources before all the tests are run. It is run only once.
        The Flask app instance is created only once when starting all the unit tests.
        :return:
        """
        cls._setup_logging(cls)
        cls._setup_app(cls)

    @staticmethod
    def _setup_logging(cls):
        log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
        logging.basicConfig(format=log_format, level=logging.INFO)
        cls.log = logging.getLogger(__name__)

    @staticmethod
    def _setup_app(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

        # sleep 10 seconds to allow libre unoserver to start
        time.sleep(10)