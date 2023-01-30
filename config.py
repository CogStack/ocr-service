import logging
import multiprocessing
import os
from sys import platform

# 50 - CRITICAL, 40 - ERROR, 30 - WARNING, 20 - INFO, 10 - DEBUG, 0 - NOTSET
LOG_LEVEL = os.environ.get("OCR_SERVICE_LOG_LEVEL", 40)

ROOT_DIR = os.path.abspath(os.curdir)
TMP_FILE_DIR = os.path.join(ROOT_DIR, "tmp")

# basic app settings
OCR_SERVICE_PORT = os.environ.get("OCR_SERVICE_PORT", 8090)

# Integer or Float - duration in seconds for the OCR processing, after which, pytesseract will terminate and raise RuntimeError
TESSERACT_TIMEOUT = os.environ.get("OCR_SERVICE_TESSERACT_TIMEOUT", 360)

# Tesseract language code string. Defaults to eng if not specified! Example for multiple languages: lang='eng+fra'
TESSERACT_LANGUAGE = "eng"

# Integer - modifies the processor priority for the Tesseract run. Not supported on Windows. Nice adjusts the niceness of unix-like processes.
TESSERACT_NICE = os.environ.get("OCR_SERVICE_TESSERACT_NICE", -18)

# Any additional custom configuration flags that are not available via the pytesseract function. For example: config='--psm 6'
TESSERACT_CUSTOM_CONFIG_FLAGS = os.environ.get("OCR_SERVICE_TESSERACT_CUSTOM_CONFIG_FLAGS", "")

# controls both threads and cpus
CPU_THREADS = os.environ.get("OCR_SERVICE_CPU_THREADS",  multiprocessing.cpu_count())

# conversion thread number for the pdf -> PIL img conversion
CONVERTER_THREAD_NUM = os.environ.get("OCR_SERVICE_CONVERTER_THREADS", multiprocessing.cpu_count())

# should we convert detected images to greyscale before OCR-ing
OCR_CONVERT_GRAYSCALE_IMAGES = True

# dpi used for images in TESSERACT and other stuff
OCR_IMAGE_DPI = os.environ.get("OCR_SERVICE_IMAGE_DPI", 200)


# LIBRE OFFICE SECTION

# 60 seconds before terminating processes
LIBRE_OFFICE_PROCESS_TIMEOUT =  os.environ.get("OCR_SERVICE_LIBRE_OFFICE_PROCESS_TIMEOUT", 60)

# This is the port for the background soffice listener service that gets started with the app
# used internally for LibreOffice doc conversion
LIBRE_OFFICE_LISTENER_PORT = "9999"

LIBRE_OFFICE_NETWORK_INTERFACE = "localhost"


# DO NOT CHANGE THIS UNLESS YOU ARE DEVELOPING OR RUNNING THIS APP LOCALLY
# Description: this sets the paths to the LibreOffice python binary,
#              it is required by default when using the unoserver package
#
# MacOS X: /Applications/LibreOffice.app/Contents/Resources/python
# Windows: C:/Windows/py.exe
# Linux(Ubuntu): /usr/bin/python3.11 (forcefully uses python3.11, to point to the default python on your system just use /usr/bin/python3)
LIBRE_OFFICE_PYTHON_PATH = "/Applications/LibreOffice.app/Contents/Resources/python"

# DO NOT CHANGE THIS UNLESS YOU ARE DEVELOPING OR RUNNING THIS APP LOCALLY
# Description: this sets the path to the LibreOffice executable,
#              unoserver uses it to start a daemon in the background
#              that listens to any incoming conversion requests
#
# MacOS X: /Applications/LibreOffice.app/Contents/MacOS/soffice
# Windows: %ProgramFiles%/LibreOffice/Program/soffice
# Linux(Ubuntu): /usr/bin/soffice
LIBRE_OFFICE_EXEC_PATH = "/Applications/LibreOffice.app/Contents/MacOS/soffice"

if platform == "linux" or platform == "linux2":
    LIBRE_OFFICE_EXEC_PATH = "/usr/bin/soffice"
    LIBRE_OFFICE_PYTHON_PATH = "/usr/bin/python3.11"
elif platform == "win32":
    LIBRE_OFFICE_EXEC_PATH = "%ProgramFiles%/LibreOffice/Program/soffice"
    LIBRE_OFFICE_PYTHON_PATH = "C:/Windows/py.exe"


# Other settings for image or format conversions

# might speed up pdf to img conversion, normally ppm is used
CONVERTER_USE_PDF_CAIRO = True