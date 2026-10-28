# Mapping worker: the app's Celery code plus OpenSfM (structure from motion) and GDAL (orthophoto,
# tiles). Build context is ./backend:  docker build -f worker/Dockerfile backend
#
# OpenSfM lives in its own virtualenv and is run as a subprocess, so its pinned numpy/OpenCV never
# touch the app's environment. It has no published image or wheel, so it is built from a pinned
# commit (slow the first time: expect 15-30 minutes; later builds reuse the cached layers).
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
# mapillary/OpenSfM master as of 2026-10-21 (v0.5.2 development)
ARG OPENSFM_REF=65571c8ae9ac6a1d0bcd3fdc1ea5fff97b1b5611

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates cmake curl ffmpeg gdal-bin git \
        libceres-dev libeigen3-dev libopencv-dev libpq5 \
        python3 python3-dev python3-gdal python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Keep the compiler from using more memory than a laptop-sized Docker VM has.
ENV CMAKE_BUILD_PARALLEL_LEVEL=4

RUN git init -q /opt/OpenSfM \
    && git -C /opt/OpenSfM fetch -q --depth 1 https://github.com/mapillary/OpenSfM "$OPENSFM_REF" \
    && git -C /opt/OpenSfM checkout -q FETCH_HEAD \
    && git -C /opt/OpenSfM submodule update -q --init --recursive --depth 1 \
    && python3 -m venv /opt/opensfm-venv \
    && /opt/opensfm-venv/bin/pip install --no-cache-dir /opt/OpenSfM

# The app, in a separate environment.
RUN python3 -m venv /opt/app-venv
COPY . /app
RUN /opt/app-venv/bin/pip install --no-cache-dir /app

ENV PATH="/opt/app-venv/bin:$PATH" \
    OPENSFM_PYTHON=/opt/opensfm-venv/bin/python \
    OPENSFM_MAIN=/opt/OpenSfM/bin/opensfm_main.py \
    MAPPING_WORK_DIR=/data/mapping

RUN useradd --create-home allotment && mkdir -p /data/media /data/mapping \
    && chown -R allotment /data
USER allotment
WORKDIR /app
CMD ["celery", "-A", "allotment.celery_app:celery", "worker", "-Q", "mapping", "-c", "1", "-l", "INFO"]
