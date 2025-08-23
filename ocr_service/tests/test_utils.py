import os
from pathlib import Path
from typing import Union

TEST_FILES_ROOT_PATH = Path(__file__).resolve().parent / "resources" / "docs"
ROOT_DIR = os.getcwd()


def get_file(file_path: Union[str, Path]) -> bytes:
    p = TEST_FILES_ROOT_PATH / Path(file_path)
    return p.read_bytes()
