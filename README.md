# Introduction

This is a python-replacement of the previous Tika-service in an attempt to resolve scalability and performance issues. It also relies on tesseract ocr but without the ambiguities of the Tika framework.

# Dependencies

Python 3.11+ <br>
For the Python packages see [`requirements.txt`](./requirements.txt).
Pillow package deps, see (https://pillow.readthedocs.io/en/stable/installation.html)

## Local development dependencies
Libre office 7.4+

# API

## API specification

Tika Service, by default, will be listening on port `8090` and the returned content extraction result will be represented in JSON format. 

The service exposes such endpoints:
- *GET* `/api/info` - returns information about the service with its configuration,
- *POST* `/api/process` - processes a binary data stream with the binary document content ("Content-Type: application/octet-stream"), also accepts binary files directly via the 'file' parameter, if sending via curl.

# Example use

Using `curl` to send the document to server instance running on localhost on `8090` port:

`curl -F file=@test.pdf http://localhost:8090/api/process/ | jq`


