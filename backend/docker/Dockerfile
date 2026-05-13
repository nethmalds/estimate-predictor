# NEW: Multi-stage production Dockerfile for the FastAPI backend.
# Stage 1 (builder) installs build tools + pip packages; Stage 2 (runtime) is lean.

# ---- builder ----
FROM python:3.10-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# NEW: Install C build tools + native libs needed by some Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# NEW: Install into /install so we can copy only that prefix into runtime stage
RUN pip install --prefix=/install -r requirements.txt

# ---- runtime ----
FROM python:3.10-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # NEW: Point HuggingFace & sentence-transformers cache to the persistent volume mount
    HF_HOME=/cache/huggingface \
    TRANSFORMERS_CACHE=/cache/huggingface

WORKDIR /app

# NEW: Only runtime native libs (no gcc / build-essential) to keep the image lean
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
    curl \
 && rm -rf /var/lib/apt/lists/* \
 # NEW: Non-root user for security — UID 1000 is conventional
 && useradd -m -u 1000 app \
 && mkdir -p /cache/huggingface && chown -R app:app /cache

# NEW: Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# NEW: Copy application source with correct ownership
COPY --chown=app:app . .

USER app

EXPOSE 8000

# NEW: Healthcheck uses the existing /health endpoint; start-period covers Chroma + HF model cold-start
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD curl -fs http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.api.server:app", "--host", "0.0.0.0", "--port", "8000"]