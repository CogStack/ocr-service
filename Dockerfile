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
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && apt-get upgrade -y 

# install req packages
RUN apt-get install -y --no-install-recommends python3-all-dev python3-dev python3.12 python3-pip libpython3.12-dev python3.12-dev
RUN apt-get -y --no-install-recommends -o Dpkg::Options::="--force-confold" -y -o Dpkg::Options::="--force-confdef" -fuy dist-upgrade && \
    apt-get install -y --no-install-recommends \
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

RUN apt-get install -y --no-install-recommends fontconfig ttf-mscorefonts-installer libimage-exiftool-perl libtcnative-1 \
    libsm6 libxext6 gstreamer1.0-libav fonts-deva fonts-dejavu fonts-gfs-didot fonts-gfs-didot-classic fonts-junicode fonts-ebgaramond fonts-noto-cjk fonts-takao-gothic fonts-vlgothic \
    ghostscript ghostscript-x gsfonts gsfonts-other gsfonts-x11 fonts-croscore fonts-crosextra-caladea fonts-crosextra-carlito fonts-liberation fonts-open-sans fonts-noto-core fonts-ibm-plex fonts-urw-base35 \
    fonts-noto fonts-noto-cjk fonts-noto-extra xfonts-terminus fonts-font-awesome fonts-hack fonts-inconsolata fonts-liberation2 fonts-mononoki \
    libpcre3 libpcre3-dev \
    mesa-opencl-icd pocl-opencl-icd libvips-tools libvips libvips-dev \
    imagemagick libcairo2-dev tesseract-ocr tesseract-ocr-all libtesseract5 libtesseract-dev libleptonica-dev liblept5

# tessaract language packages
RUN apt-get install -y --no-install-recommends --fix-missing tesseract-ocr-eng tesseract-ocr-osd tesseract-ocr-lat \
    tesseract-ocr-eng tesseract-ocr-enm tesseract-ocr-ita tesseract-ocr-osd tesseract-ocr-script-latn \
    tesseract-ocr-fra tesseract-ocr-frk tesseract-ocr-deu tesseract-ocr-ces tesseract-ocr-dan tesseract-ocr-nld tesseract-ocr-nor \
    tesseract-ocr-spa tesseract-ocr-swe tesseract-ocr-slk tesseract-ocr-ron tesseract-ocr-script-grek

# Pillow package requirements
RUN apt-get install -y --no-install-recommends tcl8.6-dev tk8.6-dev libopenjp2-7-dev libharfbuzz-dev libfribidi-dev libxcb1-dev libtiff5-dev libjpeg8-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev libglib2.0-dev libgl1

# python3 poppler requirement
RUN apt-get install -y --no-install-recommends poppler-utils

# libre office and java
RUN apt-get install -y --no-install-recommends default-jre libreoffice-java-common libreoffice libreoffice-script-provider-python

# build font cache
RUN fc-cache -f -v

# there is a bug in the blinker package that causes issues with uwsgi
# (this removes software-properties-common)
RUN apt remove -y python3-blinker

RUN apt-get clean autoclean && apt-get autoremove --purge -y

# other openCL packages
# beignet-opencl-icd

RUN rm -rf /var/lib/apt/lists/*

# create and copy the app  
RUN mkdir /ocr_service
COPY ./ /ocr_service
WORKDIR /ocr_service

# Install uwsgi from PyPI source using the global tools
RUN python3.12 -m pip install --no-cache-dir --break-system-packages --no-build-isolation -r ./requirements.txt

# compile the python files
RUN python3.12 -m compileall /ocr_service

# Now run the simple api
CMD ["/bin/bash", "start_service_production.sh"]