
import os
from flask import Blueprint

from ocr_service.processor.processor import Processor


class ApiBlueprint(Blueprint):

    processor: Processor = None

    def __init__(self, name: str, import_name: str, processor: Processor = None,
                 static_folder: str | os.PathLike | None = None,
                 static_url_path: str | None = None, template_folder: str | os.PathLike | None = None,
                 url_prefix: str | None = None, subdomain: str | None = None,
                 url_defaults: dict | None = None, root_path: str | None = None,
                 cli_group: str | None = ...):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder,
                         url_prefix, subdomain, url_defaults, root_path, cli_group)
        self.processor = processor
