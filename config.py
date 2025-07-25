import os
import multiprocessing

from sys import platform

OCR_SERVICE_VERSION: str = "0.3.0"
# 50 - CRITICAL, 40 - ERROR, 30 - WARNING, 20 - INFO, 10 - DEBUG, 0 - NOTSET
LOG_LEVEL: int = int(os.environ.get("OCR_SERVICE_LOG_LEVEL", 40))

DEBUG_MODE: bool = True if os.environ.get("OCR_SERVICE_DEBUG_MODE", False) in [True, "True", "true"] else False

ROOT_DIR: str = os.path.abspath(os.curdir)
TMP_FILE_DIR: str = os.path.join(ROOT_DIR, "tmp")
WORKER_PORT_MAP_FILE_PATH: str = os.path.join(TMP_FILE_DIR, './worker_process_data.txt')


# Should we actually ocr or just extract text from PDFs ?
#  NOTE: OCR IS STILL APPLIED TO IMAGES if detected | possible vals : "OCR", "NO_OCR"
OPERATION_MODE: str = os.environ.get("OCR_SERVICE_OPERATION_MODE", "OCR")

# basic app settings
OCR_SERVICE_PORT: int = int(os.environ.get("OCR_SERVICE_PORT", 8090))

# Tesseract model path: macos - /opt/homebrew/share/tessdata | linux - "/usr/local/share/tessdata"
TESSDATA_PREFIX: str = str(os.environ.get("OCR_TESSDATA_PREFIX", "/opt/homebrew/share/tessdata"))

# Integer or Float - duration in seconds for the OCR processing, after which,
#   tesseract will terminate and raise RuntimeError
TESSERACT_TIMEOUT: int = int(os.environ.get("OCR_SERVICE_TESSERACT_TIMEOUT", 30))

# Tesseract language code string. Defaults to eng if not specified! Example for multiple languages: lang='eng+fra'
TESSERACT_LANGUAGE: str = os.environ.get("OCR_SERVICE_TESSERACT_LANG", "eng+lat")

# Integer - modifies the processor priority for the Tesseract run. Not supported on Windows.
#   Nice adjusts the niceness of unix-like processes.
TESSERACT_NICE: int = int(os.environ.get("OCR_SERVICE_TESSERACT_NICE", -18))

# Any additional custom configuration flags that are not available via the tesseract function.
# For example: config='--psm 6'
TESSERACT_CUSTOM_CONFIG_FLAGS: str = os.environ.get("OCR_SERVICE_TESSERACT_CUSTOM_CONFIG_FLAGS", "")

# Controls both threads and cpus for one WEB SERVICE thread, basically, one request handler.
# This is derived normally from the amount of threads Gunicorn is running with, for example:
#  - if we have OCR_SERVICE_THREADS = 4, the OCR service can handle at most 4 requests at the same time,
#    this means that you can not use all of your CPUS for OCR-ing for 1 request,
#    because that means the other requests are sitting idle while the first one uses all resources,
#    and so it is recommended to regulate the number of threads per request
OCR_WEB_SERVICE_THREADS: int = int(os.environ.get("OCR_WEB_SERVICE_THREADS", 1))

# This controls the number of workers the ocr service may have it is recommended to use this value
#   instead of OCR_WEB_SERVICE_THREADS if you want to process multiple requests in parallel
# WARNING: using more than 1 workers assumes you have set the OCR_WEB_SERVICE_WORKER_CLASS setting to sync !
#          with the above mentioned,
#          setting OCR_WEB_SERVICE_WORKER_CLASS to sync means that a worker will use 1 THREAD only,
#          therefore OCR_WEB_SERVICE_THREADS is disregarded
OCR_WEB_SERVICE_WORKERS: int = int(os.environ.get("OCR_WEB_SERVICE_WORKERS", 1))

# set this to control the number of threads used for OCR-ing per web request thread (check OCR_WEB_SERVICE_THREADS)
CPU_THREADS: int = int(os.environ.get("OCR_SERVICE_CPU_THREADS",
                                      (multiprocessing.cpu_count() / OCR_WEB_SERVICE_WORKERS)))

# conversion thread number for the pdf -> PIL img conversion, per web request thread (check OCR_WEB_SERVICE_THREADS)
CONVERTER_THREAD_NUM: int = int(os.environ.get("OCR_SERVICE_CONVERTER_THREADS",
                                               (multiprocessing.cpu_count() / OCR_WEB_SERVICE_WORKERS)))

# should we convert detected images to greyscale before OCR-ing
OCR_CONVERT_GRAYSCALE_IMAGES: bool = True

# dpi used for images in TESSERACT and other stuff
OCR_IMAGE_DPI: int = int(os.environ.get("OCR_SERVICE_IMAGE_DPI", 200))

# possible values: json (stringified output), dict (dict means no json.dumps() is applied to the output)
OCR_SERVICE_RESPONSE_OUTPUT_TYPE: str = str(os.environ.get("OCR_SERVICE_RESPONSE_OUTPUT_TYPE", "json"))

# LIBRE OFFICE SECTION

# 60 seconds before terminating processes
LIBRE_OFFICE_PROCESS_TIMEOUT: int = int(os.environ.get("OCR_SERVICE_LIBRE_OFFICE_PROCESS_TIMEOUT", 100))

# This is the port for the background soffice listener service that gets started with the app
# used internally for LibreOffice doc conversion
# the service should start multiple libre office servers for doc conversions,
# a libre office server will only use 1 CPU by default (not changable), thus,
# for handling multiple requests, we will have one service per OCR_WEB_SERVICE_THREAD
DEFAULT_LIBRE_OFFICE_SERVER_PORT: int = 9900

LIBRE_OFFICE_PORT_CAP: int = DEFAULT_LIBRE_OFFICE_SERVER_PORT + 1

if OCR_WEB_SERVICE_THREADS > 1:
    LIBRE_OFFICE_PORT_CAP = DEFAULT_LIBRE_OFFICE_SERVER_PORT + OCR_WEB_SERVICE_THREADS
if OCR_WEB_SERVICE_WORKERS > 1:
    LIBRE_OFFICE_PORT_CAP = DEFAULT_LIBRE_OFFICE_SERVER_PORT + OCR_WEB_SERVICE_WORKERS

LIBRE_OFFICE_LISTENER_PORT_RANGE: range | str = os.environ.get("OCR_SERVICE_LIBRE_OFFICE_LISTENER_PORT_RANGE",
                                                               range(DEFAULT_LIBRE_OFFICE_SERVER_PORT,
                                                                     LIBRE_OFFICE_PORT_CAP))

LIBRE_OFFICE_NETWORK_INTERFACE: str = "localhost"


# seconds to check for possible failure of port
LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL: int = 10


# DO NOT CHANGE THIS UNLESS YOU ARE DEVELOPING OR RUNNING THIS APP LOCALLY
# Description: this sets the paths to the LibreOffice python binary,
#              it is required by default when using the unoserver package
#
# MacOS X: /Applications/LibreOffice.app/Contents/Resources/python
# Windows: C:/Windows/py.exe
# Linux(Ubuntu): /usr/bin/python3.12 (forcefully uses python3.12,
#  to point to the default python on your system just use /usr/bin/python3)
LIBRE_OFFICE_PYTHON_PATH: str = "/Applications/LibreOffice.app/Contents/Resources/python"

# DO NOT CHANGE THIS UNLESS YOU ARE DEVELOPING OR RUNNING THIS APP LOCALLY
# Description: this sets the path to the LibreOffice executable,
#              unoserver uses it to start a daemon in the background
#              that listens to any incoming conversion requests
#
# MacOS X: /Applications/LibreOffice.app/Contents/MacOS/soffice
# Windows: %ProgramFiles%/LibreOffice/Program/soffice
# Linux(Ubuntu): /usr/bin/soffice
LIBRE_OFFICE_EXEC_PATH: str = "/Applications/LibreOffice.app/Contents/MacOS/soffice"

if platform == "linux" or platform == "linux2":
    LIBRE_OFFICE_EXEC_PATH = "/usr/bin/soffice"
    LIBRE_OFFICE_PYTHON_PATH = "/usr/bin/python3.12"

    # this is the path from the Docker image, Ubuntu Lunar, Noble too.
    TESSDATA_PREFIX = "/usr/share/tesseract-ocr/5/tessdata"

    # if not found, then set the path to tesseract 4 data, tested with Ubuntu 22.04 LTS on WSL 2
    if os.path.exists(TESSDATA_PREFIX) is False:
        TESSDATA_PREFIX = "/usr/share/tesseract-ocr/4.00/tessdata"

elif platform == "win32":
    LIBRE_OFFICE_EXEC_PATH = "%ProgramFiles%/LibreOffice/Program/soffice"
    LIBRE_OFFICE_PYTHON_PATH = "C:/Windows/py.exe"

elif platform == "darwin":
    LIBRE_OFFICE_EXEC_PATH = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    LIBRE_OFFICE_PYTHON_PATH = "/Applications/LibreOffice.app/Contents/Resources/python"
    TESSDATA_PREFIX = "/opt/homebrew/share/tessdata"
