import logging
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Union

from starlette.middleware.base import BaseHTTPMiddleware

TEST_FILES_ROOT_PATH = Path(__file__).resolve().parent / "resources"


@dataclass(frozen=True, slots=True)
class TestDocument:
    filename: str
    text: str


class WSGIEnvironInjector(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        body = await request.body()  # grab raw bytes
        environ = {
            "wsgi.input": BytesIO(body),
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": request.headers.get("content-type", ""),
        }
        request.scope["wsgi_environ"] = environ
        return await call_next(request)


DOCS = [
    TestDocument(filename="pat_id_1",
                 text="The patient’s name is Bart Davidson. His carer’s Name Paul Wayne. \
                       His telephone number is 07754828992. His Address is 61 Basildon Way, \
                       East Croyhurst, Angelton, AL64 9HT. His mother’s name is Pauline Smith. \
                       He is on 100mg Paracetamol, 20 milligrams clozapine.")
]


def get_file(file_path: str | Path) -> bytes:
    p = TEST_FILES_ROOT_PATH / Path(file_path)
    logging.info(f"Reading test file from: {p}")
    return p.read_bytes()


def levenshtein(s: str, t: str) -> int:

    s = s.replace("‘", "'").replace("“", '"').replace("”", '"').replace("\\\n", " ")
    s = re.sub(r'\s+', ' ', s).strip()

    if len(s) < len(t):
        s, t = t, s

    m, n = len(s), len(t)
    if n == 0:
        return m
    if s == t:
        return 0

    prev = list(range(n + 1))  # D[0][*]
    for i, sc in enumerate(s, 1):
        curr = [i] + [0] * n
        for j, tc in enumerate(t, 1):
            ins = curr[j-1] + 1
            delete = prev[j] + 1
            sub = prev[j-1] + (sc != tc)
            curr[j] = min(ins, delete, sub)
        prev = curr
    return prev[n]


def lev_similarity(s: str, t: str) -> float:
    """Normalized similarity in [0,1], 1 means identical."""
    if not s and not t:
        return 1.0
    d = levenshtein(s, t)
    return 1.0 - d / max(len(s), len(t))
