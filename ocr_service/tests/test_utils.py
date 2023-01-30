import os

TEST_FILES_ROOT_PATH = "ocr_service/tests/resources/docs/"
ROOT_DIR = os.getcwd()

def get_file(file_path):
    with open(os.path.join(ROOT_DIR, TEST_FILES_ROOT_PATH, file_path), "rb") as f:
        file = f.read()
    return file
