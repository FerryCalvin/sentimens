"""
job_store.py — Status store in-memory thread-safe untuk job scrape/batch
yang berjalan di background thread. Dipakai untuk polling progress oleh
frontend (job_id == req_id, lihat pipeline.py).
"""
import threading
import time
import uuid

_lock = threading.Lock()
_store: dict[str, dict] = {}


def create_job() -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        _store[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "percent": 0,
            "message": "Menunggu...",
            "result": None,
            "error": None,
            "created_at": time.time(),
        }
    return job_id


def update_job(job_id: str, **fields) -> None:
    with _lock:
        if job_id in _store:
            _store[job_id].update(fields)


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _store.get(job_id)
        return dict(job) if job else None
