from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class MeshStats(BaseModel):
    vertex_count: int
    face_count: int
    file_size_bytes: int
    file_size_mb: float
    has_uvs: bool
    has_normals: bool
    bounding_box: Optional[dict] = None


class UploadResponse(BaseModel):
    job_id: str
    filename: str
    original_stats: MeshStats
    message: str


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    target_faces: int = Field(gt=0)
    preset: Optional[str] = None
    preserve_normals: bool = True
    preserve_boundaries: bool = True
    reoptimize_from_latest: bool = True
    strict_quality: bool = True
    max_deviation_percent: float = Field(default=2.0, gt=0.05, le=15.0)
    max_target_overshoot_percent: float = Field(default=12.0, ge=0.0, le=40.0)


class TextureExportInfo(BaseModel):
    texture_preserved: bool = True
    texture_loss_reason: Optional[str] = None
    export_mode_used: str = "full"
    warnings: list[str] = []


class OptimizeResponse(BaseModel):
    job_id: str
    original_stats: MeshStats
    optimized_stats: MeshStats
    optimized_filename: str
    optimized_format: str
    format_was_converted: bool = False
    target_faces_used: Optional[int] = None
    quality_deviation_percent: Optional[float] = None
    quality_guard_relaxed: bool = False
    quality_guard_satisfied: bool = True
    reduction_percent: float
    processing_time_seconds: float
    has_importance_map: bool = False
    texture_export: Optional[TextureExportInfo] = None
    message: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # "uploaded", "processing", "completed", "failed"
    progress: int  # 0-100
    stage: Optional[str] = None
    error: Optional[str] = None
