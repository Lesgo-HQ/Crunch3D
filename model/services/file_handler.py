import os
import uuid
import shutil
from pathlib import Path

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
PROCESSED_DIR = Path(__file__).parent.parent / "processed"

ALLOWED_EXTENSIONS = {".obj", ".stl", ".ply", ".glb", ".gltf", ".fbx", ".off"}

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)


def generate_job_id() -> str:
    return uuid.uuid4().hex[:12]


def get_upload_path(job_id: str) -> Path:
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    return job_dir


def get_processed_path(job_id: str) -> Path:
    job_dir = PROCESSED_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    return job_dir


def validate_extension(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def get_file_size_mb(filepath: str | Path) -> float:
    return round(os.path.getsize(filepath) / (1024 * 1024), 3)


def cleanup_job(job_id: str):
    for base_dir in [UPLOAD_DIR, PROCESSED_DIR]:
        job_dir = base_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
