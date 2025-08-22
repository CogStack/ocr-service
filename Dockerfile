FROM ubuntu:noble

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV HTTP_PROXY=$HTTP_PROXY
ENV HTTPS_PROXY=$HTTPS_PROXY
ENV NO_PROXY=$NO_PROXY
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

ENV DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_PRIORITY=critical

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,display

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=0
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# ENV SETUPTOOLS_USE_DISTUTILS=stdlib

# default user
USER root

# install extra features
RUN apt-get update && apt-get upgrade -y && apt-get install -y software-properties-common

# add extra repos
RUN apt-add-repository multiverse && \
    apt-add-repository universe && \
    add-apt-repository ppa:graphics-drivers/ppa && \
    add-apt-repository ppa:apt-fast/stable && \
    apt-get update && apt-get upgrade -y 

RUN apt-get install apt-fast -y --no-install-recommends

# install req packages
RUN apt-fast install -y --no-install-recommends python3-all-dev python3-dev python3.12 python3-pip libpython3.12-dev python3.12-dev python3.12-venv python3-uno
RUN apt-fast -y --no-install-recommends -o Dpkg::Options::="--force-confold" -y -o Dpkg::Options::="--force-confdef" -fuy dist-upgrade && \
    apt-fast install -y --no-install-recommends \
    gnupg \
    libssl-dev \
    wget \
    curl \
    gnupg \
    gnupg-agent \
    dirmngr \
    ca-certificates \
    apt-transport-https \
    fonts-dejavu \
    build-essential \
    unixodbc \
    unixodbc-dev \
    gfortran \
    gcc \
    g++

##### utils for python and TESSERACT
RUN echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections

RUN apt-fast install -y --no-install-recommends fontconfig ttf-mscorefonts-installer libimage-exiftool-perl libtcnative-1 \
    libsm6 libxext6 gstreamer1.0-libav fonts-deva fonts-dejavu fonts-gfs-didot fonts-gfs-didot-classic fonts-junicode fonts-ebgaramond fonts-noto-cjk fonts-takao-gothic fonts-vlgothic \
    ghostscript ghostscript-x gsfonts gsfonts-other gsfonts-x11 fonts-croscore fonts-crosextra-caladea fonts-crosextra-carlito fonts-liberation fonts-open-sans fonts-noto-core fonts-ibm-plex fonts-urw-base35 \
    fonts-noto fonts-noto-cjk fonts-noto-extra xfonts-terminus fonts-font-awesome fonts-hack fonts-inconsolata fonts-liberation2 fonts-mononoki \
    libpcre3 libpcre3-dev \
    mesa-opencl-icd pocl-opencl-icd libvips-tools libvips libvips-dev \
    imagemagick libcairo2-dev tesseract-ocr tesseract-ocr-all libtesseract5 libtesseract-dev libleptonica-dev liblept5

# tessaract language packages
RUN apt-fast install -y --no-install-recommends --fix-missing tesseract-ocr-osd tesseract-ocr-lat \
    tesseract-ocr-eng tesseract-ocr-enm tesseract-ocr-ita tesseract-ocr-osd tesseract-ocr-script-latn \
    tesseract-ocr-fra tesseract-ocr-frk tesseract-ocr-deu tesseract-ocr-ces tesseract-ocr-dan tesseract-ocr-nld tesseract-ocr-nor \
    tesseract-ocr-spa tesseract-ocr-swe tesseract-ocr-slk tesseract-ocr-ron tesseract-ocr-script-grek

# Pillow package requirements
RUN apt-fast install -y --no-install-recommends tcl8.6-dev tk8.6-dev libopenjp2-7-dev libharfbuzz-dev libfribidi-dev libxcb1-dev libtiff5-dev libjpeg8-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev libglib2.0-dev libgl1

# python3 poppler requirement
RUN apt-fast install -y --no-install-recommends poppler-utils

# libre office and java
RUN apt-fast install -y --no-install-recommends default-jre libreoffice-java-common libreoffice libreoffice-script-provider-python

# build font cache
RUN fc-cache -f -v

# there is a bug in the blinker package that causes issues with uwsgi
# (this removes software-properties-common)
RUN apt remove -y python3-blinker

RUN apt-fast clean autoclean && apt-fast autoremove --purge -y

# other openCL packages
# beignet-opencl-icd

RUN rm -rf /var/lib/apt/lists/*

# create and copy the app  
RUN mkdir /ocr_service
COPY ./ /ocr_service
WORKDIR /ocr_service

# --- Install system-wide unoserver to match requirements.txt (for UNO/system Python) ---
# BEFORE creating the venv so /usr/bin/python3.12 can run unoserver
# the reason for this is that the uno python bindings are tied to the system python
# and will not work in a venv
# so we need to install unoserver globally to match the version in requirements.txt
# this is a bit hacky but it works around the issue of unoserver not being available
# via pip for python3.12 (as of 2025-08)
RUN UNOSERVER_PIN=$(awk -F'==' '/^unoserver==/ {print $2; exit}' requirements.txt || true) && \
    if [ -n "$UNOSERVER_PIN" ]; then \
        echo "Installing system unoserver==$UNOSERVER_PIN"; \
        pip3 install --no-cache-dir --break-system-packages "unoserver==$UNOSERVER_PIN"; \
    else \
        echo "No exact pin found for unoserver in requirements.txt; installing latest system unoserver"; \
        pip3 install --no-cache-dir --break-system-packages unoserver; \
    fi
# --- end unoserver system install ---

# Use a virtual environment for Python deps (single-stage build)
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install uwsgi from PyPI source using the global tools
RUN python3.12 -m venv "$VIRTUAL_ENV" && "$VIRTUAL_ENV/bin/python" && "$VIRTUAL_ENV/bin/pip" install --no-cache-dir -r ./requirements.txt

# compile the python files
# Byte-compile using venv python
RUN "$VIRTUAL_ENV/bin/python" -m compileall /ocr_service

# Now run the simple api
CMD ["/bin/bash", "start_service_production.sh"]