import uuid
from datetime import datetime
from typing import Any

_JOBS: dict[str, dict[str, Any]] = {}


def create_job(job_type: str) -> str:
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        "id": job_id,
        "type": job_type,
        "status": "queued",
        "result": None,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    return job_id


def set_running(job_id: str):
    if job_id in _JOBS:
        _JOBS[job_id]["status"] = "running"
        _JOBS[job_id]["updated_at"] = datetime.utcnow().isoformat()


def set_done(job_id: str, result: Any):
    if job_id in _JOBS:
        _JOBS[job_id]["status"] = "done"
        _JOBS[job_id]["result"] = result
        _JOBS[job_id]["updated_at"] = datetime.utcnow().isoformat()


def set_failed(job_id: str, err: str):
    if job_id in _JOBS:
        _JOBS[job_id]["status"] = "failed"
        _JOBS[job_id]["error"] = err
        _JOBS[job_id]["updated_at"] = datetime.utcnow().isoformat()


def get_job(job_id: str) -> dict[str, Any] | None:
    return _JOBS.get(job_id)
