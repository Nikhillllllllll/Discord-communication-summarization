# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV TZ=America/New_York \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY scripts ./scripts

ENV PYTHONPATH=/app/src

# Default to ingestion, but can be overridden for summarization
CMD ["python", "-m", "tradesbot.main"]
