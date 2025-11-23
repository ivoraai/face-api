"""Compatibility shim: expose `app` for uvicorn and Celery entrypoints.

This file keeps older run commands like

    uvicorn face_service_fastapi:app --reload

working while the main code lives in `face_embedding_processor.py`.
"""
from face_embedding_processor import app

# Optional Celery app (may be None)
try:
    from face_embedding_processor import celery_app
except Exception:
    celery_app = None

__all__ = ["app", "celery_app"]
