"""
mesh_analyzer.py — Crunch3D / OptiMesh

Analyzes a mesh file and returns a MeshStats object.

Uses Trimesh (not PyMeshLab) so that multi-component files
(multi-group OBJ, GLB scenes, FBX multi-mesh) report accurate
aggregate vertex / face counts instead of only the first mesh.

Public API — one function, same signature as the original:

    analyze_mesh(filepath: str | Path) -> MeshStats
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import trimesh
import trimesh.util

from ..api.schemas import MeshStats


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_components(path: str | Path) -> list[trimesh.Trimesh]:
    """
    Load every mesh component in a file.

    Handles:
      - Single Trimesh  (plain OBJ / STL / PLY with one body)
      - trimesh.Scene   (GLB / GLTF / FBX / multi-group OBJ)
      - Disconnected geometry merged into one Trimesh (split by body)

    Returns a non-empty list or raises ValueError.
    """
    loaded = trimesh.load(str(path), process=False)

    meshes: list[trimesh.Trimesh] = []

    if isinstance(loaded, trimesh.Scene):
        for node_name in loaded.graph.nodes_geometry:
            val = loaded.graph[node_name]
            transform = val[0]
            geom_name = val[1] if len(val) >= 2 else node_name
            geom = loaded.geometry.get(geom_name)
            if not isinstance(geom, trimesh.Trimesh) or len(geom.faces) == 0:
                continue
            verts = trimesh.transformations.transform_points(
                geom.vertices.copy(), transform
            )
            # Keep the visual so UV/texture statistics are reported correctly.
            transformed = trimesh.Trimesh(
                vertices=verts,
                faces=geom.faces.copy(),
                visual=geom.visual,
                process=False,
            )
            meshes.append(transformed)

    elif isinstance(loaded, trimesh.Trimesh):
        # A plain file may contain disconnected bodies merged into one
        # vertex soup — split so we count them accurately.
        parts = loaded.split(only_watertight=False)
        for part in parts:
            if isinstance(part, trimesh.Trimesh) and len(part.faces) > 0:
                meshes.append(part)
        # Fallback: unsplit-able mesh that still has geometry
        if not meshes and len(loaded.faces) > 0:
            meshes.append(loaded)

    if not meshes:
        raise ValueError(f"No usable mesh geometry found in: {path}")

    return meshes


def _has_uvs(components: list[trimesh.Trimesh]) -> bool:
    for mesh in components:
        visual = getattr(mesh, "visual", None)
        if visual is None:
            continue
        # TextureVisuals carries UV coordinates
        if hasattr(visual, "uv") and visual.uv is not None:
            return True
        # Some loaders store them under kind
        if getattr(visual, "kind", None) == "texture":
            return True
    return False


def _has_normals(components: list[trimesh.Trimesh]) -> bool:
    for mesh in components:
        vn = getattr(mesh, "vertex_normals", None)
        if vn is not None and len(vn) > 0:
            return True
    return False


def _bounding_box(components: list[trimesh.Trimesh]) -> dict:
    """
    Compute the world-space bounding box across all components.
    """
    if len(components) == 1:
        combined = components[0]
    else:
        combined = trimesh.util.concatenate(components)

    bounds = combined.bounds          # shape (2, 3): [[minX,minY,minZ],[maxX,maxY,maxZ]]
    extents = combined.bounding_box.extents   # [dx, dy, dz]
    diagonal = float(np.linalg.norm(extents))

    return {
        "min": bounds[0].tolist(),
        "max": bounds[1].tolist(),
        "diagonal": diagonal,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_mesh(filepath: str | Path) -> MeshStats:
    """
    Analyze a mesh file and return aggregate statistics.

    Works correctly for:
      - Single-mesh files  (OBJ, STL, PLY, OFF)
      - Multi-mesh files   (GLB, GLTF, FBX, multi-group OBJ)

    Raises ValueError if no geometry is found, or any OS/IO error
    propagates naturally so the caller (upload endpoint) can surface it.
    """
    filepath = Path(filepath)
    file_size = os.path.getsize(filepath)

    components = _load_components(filepath)

    # Aggregate counts across all components
    total_vertices = sum(len(c.vertices) for c in components)
    total_faces = sum(len(c.faces) for c in components)

    return MeshStats(
        vertex_count=total_vertices,
        face_count=total_faces,
        file_size_bytes=file_size,
        file_size_mb=round(file_size / (1024 * 1024), 3),
        has_uvs=_has_uvs(components),
        has_normals=_has_normals(components),
        bounding_box=_bounding_box(components),
    )