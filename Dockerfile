# Phase A: preview API only (numpy/Pillow). ffmpeg lands in Phase C for full renders.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY pipeline/ pipeline/
COPY templates/ templates/

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Single worker: CPU-bound previews already use an in-process thread pool.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
