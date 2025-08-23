from pathlib import Path
from typing import Union
from config import TMP_FILE_DIR  # noqa: F401

TEST_FILES_ROOT_PATH = Path(__file__).resolve().parent / "resources" / "docs"


def get_file(file_path: Union[str, Path]) -> bytes:
    p = TEST_FILES_ROOT_PATH / Path(file_path)
    return p.read_bytes()
