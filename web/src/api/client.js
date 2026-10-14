import axios from "axios";

const rawApiBase = (import.meta.env.VITE_API_BASE_URL || "").trim();
const normalizedApiBase = rawApiBase.replace(/\/+$/, "");
const API_BASE = normalizedApiBase
  ? (normalizedApiBase.endsWith("/api") ? normalizedApiBase : `${normalizedApiBase}/api`)
  : "/api";

const api = axios.create({ baseURL: API_BASE });

export async function uploadMesh(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    },
  });
  return response.data;
}

export async function optimizeMesh({
  jobId,
  targetFaces,
  preset,
  preserveNormals,
  preserveBoundaries,
  reoptimizeFromLatest,
  strictQuality,
  maxDeviationPercent,
}) {
  const response = await api.post("/optimize", {
    job_id: jobId,
    target_faces: targetFaces,
    preset: preset || null,
    preserve_normals: preserveNormals !== false,
    preserve_boundaries: preserveBoundaries !== false,
    reoptimize_from_latest: reoptimizeFromLatest !== false,
    strict_quality: strictQuality !== false,
    max_deviation_percent: maxDeviationPercent || 2.0,
  });
  return response.data;
}

export async function getJobStatus(jobId) {
  const response = await api.get(`/status/${jobId}`);
  return response.data;
}

export function getDownloadUrl(jobId) {
  const t = Date.now();
  return `${API_BASE}/download/${jobId}?t=${t}`;
}

export async function downloadResult(jobId) {
  const response = await api.get(`/download/${jobId}`, {
    responseType: "blob",
  });
  return response;
}

export function getPreviewUrl(jobId) {
  const t = Date.now();
  return `${API_BASE}/preview/${jobId}?t=${t}`;
}

export async function getImportanceMap(jobId) {
  const response = await api.get(`/importance/${jobId}`);
  return response.data;
}
