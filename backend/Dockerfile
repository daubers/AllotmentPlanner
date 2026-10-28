FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# ffmpeg/ffprobe: video metadata and thumbnails (used by the Celery worker)
RUN apt-get update && apt-get install -y --no-install-recommends curl ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY allotment ./allotment
# Database migrations: run by the compose `migrate` service (flask db upgrade) before the app starts.
COPY migrations ./migrations
ENV FLASK_APP=allotment:create_app
EXPOSE 8000

# Published image: no dev extras, no autoreload.
FROM base AS prod
RUN pip install --no-cache-dir .
RUN useradd --system --no-create-home allotment \
 && mkdir -p /data/media && chown allotment /data/media
USER allotment
# One process (the in-process Prometheus counters stay accurate) with threads, so a long upload
# or video stream occupies one thread instead of the whole server, and isn't killed by the
# worker timeout (which only watches the process's heartbeat in the threaded worker).
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--worker-class", "gthread", "--threads", "8", "--timeout", "120", "allotment:create_app()"]

# Local development and test image (default for compose).
FROM base AS dev
RUN pip install --no-cache-dir -e ".[dev]"
COPY tests ./tests
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--worker-class", "gthread", "--threads", "8", "--timeout", "120", "--reload", "allotment:create_app()"]
