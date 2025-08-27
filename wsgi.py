import re
import sys

from a2wsgi import ASGIMiddleware

from ocr_service.app import create_app

sys.path.append("..")

asgi_app = create_app()
asgi_middleware = ASGIMiddleware(asgi_app)  # type: ignore[arg-type]

_BAD_URI = re.compile(r"(%2e%2e|%00|\${jndi:|/winnt/|/etc/passwd)", re.I)


def app(environ, start_response):
    try:
        path = environ.get("PATH_INFO", "")
        if _BAD_URI.search(path):
            start_response("400 Bad Request", [("Content-Type", "text/plain")])
            return [b"Bad Request: blocked"]

        # hand off to ASGI → WSGI bridge
        return asgi_middleware(environ, start_response)

    except UnicodeDecodeError:
        start_response("400 Bad Request", [("Content-Type", "text/plain")])
        return [b"Bad Request: malformed path"]

    except Exception:
        # last-resort catch so one bad request can’t crash workers
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [b"Internal Server Error"]
