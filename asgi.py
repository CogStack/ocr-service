"""
This file is used to create a Flask application that will be served by a WSGI server
"""
import sys
import uvicorn

from config import OCR_SERVICE_PORT
from ocr_service.app import create_app

sys.path.append("..")

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=OCR_SERVICE_PORT, reload=False)
