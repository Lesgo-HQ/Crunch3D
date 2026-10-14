"""Curvature-only importance for the community optimizer."""
import numpy as np
from .curvature import compute_curvature_importance


def compute_importance(mesh):
    raw = np.nan_to_num(compute_curvature_importance(mesh), nan=0.0, posinf=0.0, neginf=0.0)
    if len(raw) == 0:
        return raw
    scale = float(np.percentile(raw, 95))
    return np.clip(raw / scale, 0.0, 1.0) if scale > 1e-12 else np.zeros_like(raw)
