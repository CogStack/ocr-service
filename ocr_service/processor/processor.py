from __future__ import annotations

import logging
import os
import subprocess
import json
import sys
import time
import injector
import traceback
import time

import filetype
import pytesseract

from PIL import Image
from typing import List, TypeVar

from filetype.types import archive,image,document,IMAGE,DOCUMENT
from config import *
from pdf2image import convert_from_bytes
from html2image import Html2Image
from ocr_service.utils import *

sys.path.append("..")

PILImage = TypeVar('PILImage', bound=Image)

class Processor:

    @injector.inject
    def __init__(self):
        app_log_level = os.getenv("LOG_LEVEL", LOG_LEVEL)
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.setLevel(level=app_log_level)
        self.log.debug("Processor log level set to : ", str(app_log_level))

    def detect_file_type(self, stream:bytes) -> filetype:
        file_type = filetype.guess(stream)
        return file_type

    def _preprocess_html_to_img(self, stream: bytes, file_name: str) -> List[PILImage]:

        hti = Html2Image(output_path=TMP_FILE_DIR, temp_path=TMP_FILE_DIR)
        html_file_path = os.path.join(TMP_FILE_DIR, file_name)
        png_img_file_path = html_file_path + ".png"
        
        with open(file=html_file_path, mode="wb") as tmp_html_file:
            tmp_html_file.write(stream)

        hti.screenshot(html_str=html_file_path, save_as=png_img_file_path)

        return [Image.open(png_img_file_path)]

    
    def _preprocess_pdf_to_img(self, stream: bytes) -> List[PILImage]:
        """
            :descripton: converts a stream of bytes from a PDF file into images
            
            :param stream: byte array from file
            :type stream: bytes

            :returns: list of PIL images
            :rtype: List[PILImage]
        """

        self.log.info("pre-processing pdf...")
        pdf_image_pages = convert_from_bytes(stream, OCR_IMAGE_DPI, thread_count=CPU_THREADS, use_pdftocairo=CONVERTER_USE_PDF_CAIRO, grayscale=OCR_CONVERT_GRAYSCALE_IMAGES, timeout=TESSERACT_TIMEOUT)
        
        return pdf_image_pages
    
    def _preprocess_doc(self, stream: bytes, file_name: str) -> List[PILImage]:
        """
            :descripton: pre-processing step, all non-pdf(docx/doc/odt/ppt/xls etc.) 
                office doc type files are sent as a stream so that they 
                can be converted to PDF using libreoffice,
                stream -> pdf tmp file, it will delete all the temporary files created
                in the TMP_FILE_DIR after getting the images into memory
            
            :param stream: byte array from file
            :type stream: bytes

            :param file_name: required file name, it will be used to create
                temporary files on disk (TMP_FILE_DIR)
            :type file_name: str

            :returns: list of PIL images
            :rtype: List[PILImage]
        """
        doc_file_path = os.path.join(TMP_FILE_DIR, file_name)
        pdf_file_path = doc_file_path + ".pdf"

        with open(file=doc_file_path, mode="wb") as tmp_doc_file:
            tmp_doc_file.write(stream)

        subprocess.run(args=[LIBRE_OFFICE_PYTHON_PATH, "-m", "unoserver.converter", doc_file_path, pdf_file_path, "--interface", LIBRE_OFFICE_NETWORK_INTERFACE, "--port", LIBRE_OFFICE_LISTENER_PORT, "--convert-to", "pdf"], capture_output=False, check=True, cwd=TMP_FILE_DIR)

        pdf_stream = None
        with open(file=pdf_file_path, mode="rb") as tmp_pdf_file:
            pdf_stream = tmp_pdf_file.read()

        delete_tmp_files([pdf_file_path, doc_file_path])

        return self._preprocess_pdf_to_img(pdf_stream)

    def _process_image(self, img: Image, img_id: int) -> str:
        """
            :description: processes a PIL(Pillow) Image, calls tesseract ocr with the configured params
            
            :param img: the actual image of a page from a PDF file
            :type img: Image

            :returns: text from the image, post-ocr
            :rtype: str
        """

        output_str = pytesseract.image_to_string(img, lang=TESSERACT_LANGUAGE, timeout=TESSERACT_TIMEOUT, nice=TESSERACT_NICE, config=TESSERACT_CUSTOM_CONFIG_FLAGS)
        self.log.info("finished processing img: " + str(img_id))

        return (output_str, img_id)

    def _process(self, stream: bytes, file_name: str) -> str:
        """
            :description: processes a stream of bytes, resulting in the output string
                files have their type detected and then managed accordingly to their requirements
                images will be directly OCRed, while actual documents will undergo
                the following process : byte_stream -> convert to pdf -> convert each pdf page to images ->
                -> multiprocess ocr for the images -> output string text

            :param stream: byte array from file
            :type stream: bytes

            :param file_name: required file name, it will be used to create
                temporary files on disk (TMP_FILE_DIR)
            :type file_name: str

            :raises: :class:`Exception`: if ocr-ing fails

            :returns: output_text, the resulting text post-ocr
            :rtype: str
        """

        file_type = self.detect_file_type(stream)
        output_text = ""
        images = []

        if type(file_type) == archive.Pdf:
            images = self._preprocess_pdf_to_img(stream)
        elif file_type in DOCUMENT:
            images = self._preprocess_doc(stream, file_name=file_name)
        elif file_type in IMAGE:
            images = [Image.open(stream)]

        image_count = len(images) if images else 0

        if image_count > 0:
            self.log.info("A total of " + str(image_count) + " images have been generated from " + file_name)
            ocr_start_time = time.time()
            proc_results = list()

            from multiprocessing.dummy import Pool

            with Pool(CPU_THREADS) as process_pool:
                count = 0
                for img in images:
                    count += 1
                    proc_results.append(process_pool.starmap_async(self._process_image, [(img, count)], chunksize=1))
            
                try:
                    for result in proc_results:
                        output_text += str((result.get(timeout=TESSERACT_TIMEOUT))[0])
                except Exception:
                    raise Exception("OCR exception generated by worker: " + str(traceback.format_exc()))
            
            ocr_end_time = time.time()

            self.log.info("OCR processing finished | Elapsed : " + str(ocr_end_time - ocr_start_time) + " seconds")

        return output_text

    def process_stream(self, stream: bytes, file_name : str = None) -> json:
        """
            :description: sends the stream of bytes to the `_process` function
                that will do all the pre-processing + ocr-ing work

            :param stream: byte array from file
            :type stream: bytes

            :param file_name: file id generated by the service(if none provided)
                 or the actual file name if the file was provided with the `file` parameter
            :type file_name: str

            :raises: :class:`Exception`: if ocr-ing fails

            :returns: output_text, the resulting text post-ocr
            :rtype: str
        """

        output_text = ""
        try:
            self.log.info("Processing file name:" + file_name)
            start_time = time.time()
            output_text = self._process(stream, file_name=file_name)
            end_time = time.time()
            self.log.info("Finished processing file: " + file_name + " | Elapsed time: " + str(end_time - start_time) + " seconds")
        except Exception as exception:
            traceback.print_exc(file=sys.stdout)

        return output_text
