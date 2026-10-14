"""
curvature.py — Curvature computation with configurable mode.

Provides ``compute_curvature_importance()`` which returns **raw** per-vertex
curvature data.  No adjacency building, smoothing, or normalisation is
performed here — that is owned by ``compute_importance()``.
"""

from __future__ import annotations

import numpy as np
import trimesh

from .config import CURVATURE_MODE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADAPTIVE_RADIUS_FRACTION = 0.02


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _adaptive_radius(mesh: trimesh.Trimesh) -> float:
    bbox_max = float(mesh.bounding_box.extents.max())
    return max(bbox_max * ADAPTIVE_RADIUS_FRACTION, 1e-6)


def _discrete_mean_curvature(mesh: trimesh.Trimesh, radius: float) -> np.ndarray | None:
    """Discrete mean curvature via trimesh's scipy-backed sphere measure."""
    try:
        from trimesh.curvature import discrete_mean_curvature_measure
        curvature = discrete_mean_curvature_measure(mesh, mesh.vertices, radius=radius)
        return np.abs(np.asarray(curvature, dtype=np.float64))
    except Exception:
        return None


def _normal_deviation_curvature(mesh: trimesh.Trimesh) -> np.ndarray:
    """Fast curvature proxy via per-vertex normal deviation from face normals."""
    n_verts = len(mesh.vertices)
    variation = np.zeros(n_verts, dtype=np.float64)
    count = np.zeros(n_verts, dtype=np.float64)

    vertex_normals = mesh.vertex_normals
    face_normals = mesh.face_normals

    for face_idx, face in enumerate(mesh.faces):
        fn = face_normals[face_idx]
        for v_idx in face:
            vn = vertex_normals[v_idx]
            dot = float(np.clip(np.dot(fn, vn), -1.0, 1.0))
            variation[v_idx] += np.arccos(abs(dot))
            count[v_idx] += 1

    mask = count > 0
    variation[mask] /= count[mask]
    variation /= (np.pi / 2)
    return variation


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_curvature_importance(mesh: trimesh.Trimesh) -> np.ndarray:
    """Return raw per-vertex curvature data (no smoothing, no normalisation).

    The backend used depends on ``CURVATURE_MODE``:

    * ``"fast"`` — normal-deviation proxy (no scipy, ~66 ms/component avg).
    * ``"balanced"`` — not yet implemented.
    * ``"accurate"`` — discrete mean curvature via scipy (~3.7 s/component).
    """
    radius = _adaptive_radius(mesh)

    if CURVATURE_MODE == "accurate":
        raw = _discrete_mean_curvature(mesh, radius)
        if raw is None:
            raw = _normal_deviation_curvature(mesh)

    elif CURVATURE_MODE == "fast":
        raw = _normal_deviation_curvature(mesh)

    elif CURVATURE_MODE == "balanced":
        raise NotImplementedError(
            "curvature_mode='balanced' is not yet implemented. "
            "Use 'fast' or 'accurate'."
        )

    else:
        raise ValueError(
            f"Unknown curvature_mode: {CURVATURE_MODE!r}. "
            f"Valid values: 'fast', 'balanced', 'accurate'."
        )

    return raw
