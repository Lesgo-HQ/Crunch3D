"""Local community API: upload, inspect, optimize and export a single mesh."""
import asyncio
import functools
import json
import logging
import multiprocessing
import os
import re
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from .schemas import UploadResponse, OptimizeRequest, OptimizeResponse, JobStatus, MeshStats
from ..services.file_handler import (
    generate_job_id, get_upload_path, get_processed_path, validate_extension,
    cleanup_job, UPLOAD_DIR, PROCESSED_DIR,
)
from ..services.mesh_analyzer import analyze_mesh
from ..engine.mesh_optimizer import decimate_mesh, resolve_output_extension

router = APIRouter(prefix="/api", tags=["mesh"])
logger = logging.getLogger(__name__)
jobs = {}
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
PRESET_TARGETS = {
    "tiny_ui": 8000, "decorative_bg": 25000, "hero_standard": 70000,
    "interactive_model": 100000, "multi_scene": 220000, "mobile_hero": 45000,
}


def _save_job(job_id):
    job = jobs[job_id]
    payload = {k: v.model_dump() if isinstance(v, MeshStats) else v for k, v in job.items()}
    path = UPLOAD_DIR / job_id / "_job_meta.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload))
    temporary.replace(path)


def _get_job(job_id):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        raise HTTPException(404, "Job not found")
    if job_id not in jobs:
        path = UPLOAD_DIR / job_id / "_job_meta.json"
        if not path.is_file():
            raise HTTPException(404, "Job not found")
        try:
            job = json.loads(path.read_text())
            for key in ("original_stats", "optimized_stats"):
                if key in job:
                    job[key] = MeshStats(**job[key])
            if job["status"] == "processing":
                job.update(status="failed", error="Processing interrupted; retry optimization")
            jobs[job_id] = job
        except (ValueError, KeyError):
            raise HTTPException(422, "Local job metadata could not be read")
    return jobs[job_id]


@router.post("/upload", response_model=UploadResponse)
async def upload_model(file: UploadFile = File(...)):
    filename = Path((file.filename or "").replace("\\", "/")).name
    if not validate_extension(filename):
        raise HTTPException(400, "Unsupported mesh format")
    job_id = generate_job_id()
    path = get_upload_path(job_id) / filename
    try:
        size = 0
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                    raise HTTPException(413, f"Local upload limit: {MAX_FILE_SIZE_MB} MB")
                output.write(chunk)
        stats = await asyncio.to_thread(analyze_mesh, path)
        jobs[job_id] = dict(status="uploaded", progress=100, stage="Upload complete",
                            filename=filename, original_stats=stats)
        _save_job(job_id)
    except Exception as exc:
        jobs.pop(job_id, None)
        cleanup_job(job_id)
        if isinstance(exc, HTTPException):
            raise
        logger.exception("Mesh upload failed")
        raise HTTPException(422, "Could not read this mesh; use a self-contained static mesh") from exc
    finally:
        await file.close()
    return UploadResponse(job_id=job_id, filename=filename, original_stats=stats,
                          message="Mesh ready for local optimization")


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_mesh(request: OptimizeRequest):
    job = _get_job(request.job_id)
    if job["status"] == "processing":
        raise HTTPException(409, "This mesh is already processing")
    if request.preset and request.preset not in PRESET_TARGETS:
        raise HTTPException(422, "Unknown preset")
    target = PRESET_TARGETS.get(request.preset, request.target_faces)
    source = UPLOAD_DIR / request.job_id / job["filename"]
    source_stats = job["original_stats"]
    if (request.reoptimize_from_latest and job.get("output_filename")
            and target < job["optimized_stats"].face_count):
        source = PROCESSED_DIR / request.job_id / job["output_filename"]
        source_stats = job["optimized_stats"]
    if not source.is_file():
        raise HTTPException(404, "Source mesh is missing")
    output_ext = resolve_output_extension(source.suffix)
    # GLB keeps geometry and textures together for previews and single-file export.
    if source_stats.has_uvs:
        output_ext = ".glb"
    output_dir = get_processed_path(request.job_id)
    output_name = f"mesh_{generate_job_id()}{output_ext}"
    output_path = output_dir / output_name
    job.update(status="processing", progress=10, stage="Optimizing", error=None)
    _save_job(request.job_id)
    started = time.monotonic()
    try:
        # A native geometry crash must not take down the API process.
        with ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn")) as pool:
            stats, meta = await asyncio.get_running_loop().run_in_executor(pool, functools.partial(
                decimate_mesh, input_path=source, output_path=output_path, target_faces=target,
                preserve_normals=request.preserve_normals, preserve_boundaries=request.preserve_boundaries,
                strict_quality=request.strict_quality, max_deviation_percent=request.max_deviation_percent,
                max_target_overshoot_percent=request.max_target_overshoot_percent,
            ))
        elapsed = round(time.monotonic() - started, 2)
        reduction = round((1 - stats.face_count / max(source_stats.face_count, 1)) * 100, 1)
        job.update(status="completed", progress=100, stage="Complete", optimized_stats=stats,
                   output_filename=output_name, importance_scores=meta.get("importance_scores"))
        _save_job(request.job_id)
        return OptimizeResponse(
            job_id=request.job_id, original_stats=source_stats, optimized_stats=stats,
            optimized_filename=output_name, optimized_format=output_ext.lstrip("."),
            format_was_converted=output_ext != source.suffix.lower(),
            target_faces_used=meta.get("target_faces_used"),
            quality_deviation_percent=meta.get("quality_deviation_percent"),
            quality_guard_relaxed=meta.get("quality_guard_relaxed", False),
            quality_guard_satisfied=meta.get("quality_guard_satisfied", True),
            reduction_percent=reduction, processing_time_seconds=elapsed,
            has_importance_map=meta.get("importance_scores") is not None,
            texture_export=meta.get("texture_export_info"),
            message="Optimization complete",
        )
    except Exception as exc:
        logger.exception("Optimization failed")
        job.update(status="failed", stage="Error", error="Optimization failed; retry with a less aggressive target")
        _save_job(request.job_id)
        raise HTTPException(422, job["error"]) from exc


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    job = _get_job(job_id)
    return JobStatus(job_id=job_id, status=job["status"], progress=job["progress"],
                     stage=job.get("stage"), error=job.get("error"))


@router.get("/importance/{job_id}")
async def get_importance_map(job_id: str):
    scores = _get_job(job_id).get("importance_scores")
    return {"job_id": job_id, "scores": scores or []}


def _output(job_id):
    job = _get_job(job_id)
    if not job.get("output_filename"):
        raise HTTPException(404, "Optimize the mesh first")
    path = PROCESSED_DIR / job_id / job["output_filename"]
    if not path.is_file():
        raise HTTPException(404, "Output file is missing")
    return path


@router.get("/preview/{job_id}")
async def preview_result(job_id: str):
    return FileResponse(_output(job_id), headers={"Cache-Control": "no-store"})


@router.get("/download/{job_id}")
async def download_result(job_id: str):
    path = _output(job_id)
    return FileResponse(path, filename=path.name)


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    job = _get_job(job_id)
    if job["status"] == "processing":
        raise HTTPException(409, "Wait for processing to finish")
    cleanup_job(job_id)
    jobs.pop(job_id, None)
    return {"deleted": job_id}
