# Multi-stage build to optimize image size
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim as builder

WORKDIR /app

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libglu1 \
    libgl1 \
    libglx0 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY face_embedding_processor.py ./
COPY .env* ./

# Install Python dependencies using UV
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN uv pip install --system -e .

# Pre-download and cache ALL models during build
RUN python -c "\
from deepface import DeepFace; \
import numpy as np; \
print('Downloading RetinaFace detector...'); \
DeepFace.extract_faces(np.ones((224,224,3), dtype=np.uint8), detector_backend='retinaface', enforce_detection=False); \
print('Downloading ArcFace embeddings...'); \
DeepFace.represent(np.ones((224,224,3), dtype=np.uint8), model_name='ArcFace', enforce_detection=False); \
print('Downloading age/gender/emotion models...'); \
DeepFace.analyze(np.ones((224,224,3), dtype=np.uint8), actions=['age', 'gender', 'emotion'], enforce_detection=False, detector_backend='skip'); \
print('All models cached successfully'); \
" || echo "Warning: Model caching had errors but continuing..."

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libglu1 \
    libgl1 \
    libglx0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy cached model weights from builder
COPY --from=builder /root/.deepface /root/.deepface

# Copy application files
COPY face_embedding_processor.py ./
COPY .env* ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/models && \
    chmod -R 755 /app/logs /app/data /app/models

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "face_embedding_processor:app", "--host", "0.0.0.0", "--port", "8000"]
