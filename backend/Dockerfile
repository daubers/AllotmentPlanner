FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY allotment ./allotment
RUN pip install --no-cache-dir -e ".[dev]"
COPY tests ./tests
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--reload", "allotment:create_app()"]
