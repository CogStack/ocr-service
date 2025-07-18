"""
This file is used to create a Flask application that will be served by a WSGI server
"""
import sys

from config import OCR_SERVICE_PORT
from ocr_service.app import create_app

sys.path.append("..")

application = create_app()

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=int(OCR_SERVICE_PORT))
