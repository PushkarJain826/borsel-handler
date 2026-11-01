# ---------- build stage ----------
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output.
# PYTHONPATH includes /app/src so the src-layout package "borsel" is importable.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install OS-level dependencies required by asyncpg
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Default command: run the FastAPI dev server
CMD ["uvicorn", "borsel.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]
