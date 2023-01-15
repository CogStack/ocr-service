import os
import multiprocessing

ROOT_DIR = os.path.abspath(os.curdir)
TMP_FILE_DIR = os.path.join(ROOT_DIR, "tmp")

# Integer or Float - duration in seconds for the OCR processing, after which, pytesseract will terminate and raise RuntimeError
TESSERACT_TIMEOUT = 30

# Tesseract language code string. Defaults to eng if not specified! Example for multiple languages: lang='eng+fra'
TESSERACT_LANGUAGE = "eng"

# Integer - modifies the processor priority for the Tesseract run. Not supported on Windows. Nice adjusts the niceness of unix-like processes.
TESSERACT_NICE = -10

# Any additional custom configuration flags that are not available via the pytesseract function. For example: config='--psm 6'
TESSERACT_CUSTOM_CONFIG_FLAGS = ""

CPU_THREADS = multiprocessing.cpu_count()

# should we convert detected images to greyscale before OCR-ing
OCR_CONVERT_GRAYSCALE_IMAGES = True

# dpi used for images in TESSERACT and other stuff
OCR_IMAGE_DPI = 200

# DO NOT CHANGE THIS UNLESS YOU ARE DEVELOPING OR RUNNING THIS APP LOCALLY
# Description: this sets the paths to the LibreOffice python binary,
#              it is required by default when using the unoserver package
#
# MacOS X:  /Applications/LibreOffice.app/Contents/Resources/python
# Windows: 
# Linux:
LIBRE_OFFICE_PYTHON_PATH="/Applications/LibreOffice.app/Contents/Resources/python"

# DO NOT CHANGE THIS UNLESS YOU ARE DEVELOPING OR RUNNING THIS APP LOCALLY
# Description: this sets the path to the LibreOffice executable,
#              unoserver uses it to start a daemon in the background
#              that listens to any incoming conversion requests
#
# MacOS X: /Applications/LibreOffice.app/Contents/MacOS/soffice
# Windows:
# Linux:
LIBRE_OFFICE_EXEC_PATH="/Applications/LibreOffice.app/Contents/MacOS/soffice"

# used internally for LibreOffice doc conversion
LIBRE_OFFICE_LISTENER_PORT="9999"

LIBRE_OFFICE_NETWORK_INTERFACE="localhost"