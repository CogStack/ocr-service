import sys

from a2wsgi import ASGIMiddleware

from ocr_service.app import create_app

sys.path.append("..")

app = ASGIMiddleware(app=create_app())  # type: ignore[arg-type]
