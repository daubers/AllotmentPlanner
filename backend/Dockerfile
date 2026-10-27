FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY allotment ./allotment
EXPOSE 8000

# Published image: no dev extras, no autoreload.
FROM base AS prod
RUN pip install --no-cache-dir .
RUN useradd --system --no-create-home allotment
USER allotment
CMD ["gunicorn", "-b", "0.0.0.0:8000", "allotment:create_app()"]

# Local development and test image (default for compose).
FROM base AS dev
RUN pip install --no-cache-dir -e ".[dev]"
COPY tests ./tests
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--reload", "allotment:create_app()"]
