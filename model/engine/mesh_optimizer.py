"""
mesh_optimizer.py — Crunch3D / OptiMesh
Clean rewrite with proper multi-component mesh handling.

Architecture:
  input_file
    → Trimesh  (split into N components)
    → PyMeshLab per component  (QEM decimation)
    → Trimesh  (merge all components back)
    → output_file

Community edition: curvature-weighted QEM and sampled quality checks.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time as _time
from pathlib import Path

import numpy as np
import pymeshlab
import trimesh
import trimesh.util

logger = logging.getLogger(__name__)

from ..api.schemas import MeshStats
from ..importance.importance_mapper import compute_importance
# ---------------------------------------------------------------------------
# Timing instrumentation (temporary — left in place for profiling)
# ---------------------------------------------------------------------------

def _timing_reset() -> None:
    pass

def _timing_report() -> None:
    pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

QUALITY_SAMPLE_CAP = 700
QUALITY_CHUNK_SIZE = 160

SUPPORTED_SAVE_EXTENSIONS = {".obj", ".stl", ".ply", ".off", ".glb", ".gltf"}

def resolve_output_extension(input_extension: str) -> str:
    ext = (input_extension or "").lower().strip()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    if ext in {".gltf", ".off"}:
        return ".glb"
    return ext if ext in SUPPORTED_SAVE_EXTENSIONS else ".obj"


# ---------------------------------------------------------------------------
# Helpers — component loading / saving
# ---------------------------------------------------------------------------

def _load_components(path: str | Path) -> list[trimesh.Trimesh]:
    """
    Load a mesh file and return a flat list of Trimesh components.

    Materials, textures and UV visuals are carried through so downstream
    decimation/export never loses them.
    """
    loaded = trimesh.load(str(path), process=False)
    if isinstance(loaded, trimesh.Scene):
        dumped = loaded.dump(concatenate=False)
        # `dump()` can sometimes return a single mesh or a numpy array of meshes
        if isinstance(dumped, trimesh.Trimesh):
            dumped = [dumped]
        meshes = []
        for geom in dumped:
            if not isinstance(geom, trimesh.Trimesh) or len(geom.faces) == 0:
                continue
            # Re-attach original visuals (texture/vertex-colour materials) — the
            # scene dump path can strip them.
            visual = getattr(geom, "visual", None)
            if visual is not None and getattr(visual, "kind", None) == "none":
                original = loaded.geometry.get(geom.name) if hasattr(geom, "name") else None
                if original is not None and getattr(original, "visual", None) is not None:
                    try:
                        visual = original.visual
                    except Exception:
                        visual = None
            if visual is not None:
                try:
                    geom = trimesh.Trimesh(
                        vertices=geom.vertices.copy(),
                        faces=geom.faces.copy(),
                        visual=visual,
                        process=False,
                    )
                except Exception:
                    pass
            meshes.append(geom)
    elif isinstance(loaded, trimesh.Trimesh):
        meshes = [loaded]
    else:
        meshes = []

    if not meshes:
        raise ValueError(f"No usable mesh geometry found in: {path}")

    return meshes


def _component_to_pymeshlab(mesh: trimesh.Trimesh) -> pymeshlab.MeshSet:
    """Export a Trimesh component to a temp OBJ, load it into a fresh MeshSet."""
    _ensure_uv_material(mesh)
    tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        mesh.export(tmp_path)
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(tmp_path)
    finally:
        _safe_remove(tmp_path)
    return ms


def _pymeshlab_to_trimesh(ms: pymeshlab.MeshSet, _export_info: dict | None = None) -> trimesh.Trimesh | None:
    """Save the current MeshSet mesh to a temp OBJ, reload as Trimesh.

    If *_export_info* is provided, it is updated with the export metadata.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        info = _save_current_mesh(ms, tmp_path)
        if _export_info is not None:
            _export_info.update(info)
        result = trimesh.load(tmp_path, process=False)
        if isinstance(result, trimesh.Scene):
            parts = [g for g in result.geometry.values()
                     if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0]
            return trimesh.util.concatenate(parts) if parts else None
        if isinstance(result, trimesh.Trimesh) and len(result.faces) > 0:
            return result
        return None
    finally:
        _safe_remove(tmp_path)


def _safe_remove(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _scene_merge(parts: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Merge components while keeping each part's UVs and materials.

    ``trimesh.util.concatenate`` silently drops texture visuals (and can
    raise when two parts carry different materials).  Round-tripping the
    parts through a multi-object OBJ export/import preserves per-part UVs
    and material references, which is exactly what multi-group GLB/OBJ
    uploads need.
    """
    scene = trimesh.Scene()
    for idx, part in enumerate(parts):
        _ensure_uv_material(part)
        scene.add_geometry(
            part,
            node_name=f"mesh_{idx}",
            geom_name=f"geo_{idx}",
            parent_node_name=None,
        )

    tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        scene.export(tmp_path)
        loaded = trimesh.load(tmp_path, process=False)
        if isinstance(loaded, trimesh.Scene):
            geoms = [g for g in loaded.geometry.values()
                     if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0]
            if not geoms:
                raise RuntimeError("Scene merge produced no geometry")
            merged = trimesh.util.concatenate(geoms)
        else:
            merged = loaded
        return _ensure_uv_material(merged)
    finally:
        # Clean up the .obj plus any sidecar .mtl / texture files
        import glob as _glob
        for side in _glob.glob(tmp_path[:-4] + ".*"):
            _safe_remove(side)


def _ensure_uv_material(mesh: trimesh.Trimesh) -> trimesh.Trimesh | None:
    """Keep UV coordinates when exporting a mesh that carries them.

    Trimesh's OBJ/GLB writers silently drop ``vt`` texture coordinates when
    the visual has UVs but no material attached (e.g. after a scene dump,
    a concatenate, or loading a UV-only mesh).  That is the root cause of
    "the texture completely changed" — the geometry survives but the UV map
    vanishes, so the model renders with a broken/untextured surface.

    When UVs exist but the material is missing, attach a minimal unnamed
    SimpleMaterial so writers emit the UV data.  Returns the same mesh.
    """
    try:
        visual = getattr(mesh, "visual", None)
        if visual is None or getattr(visual, "kind", None) != "texture":
            return mesh
        if visual.uv is None:
            return mesh
        if getattr(visual, "material", None) is None:
            from trimesh.visual.material import SimpleMaterial
            mesh.visual = trimesh.visual.TextureVisuals(
                uv=np.asarray(visual.uv, dtype=np.float64),
                material=SimpleMaterial(name="material"),
            )
    except Exception as exc:
        logger.debug("UV material guard failed: %s", exc)
    return mesh


# ---------------------------------------------------------------------------
# Helpers — texture-aware export
# ---------------------------------------------------------------------------

def _export_mesh_with_texture_tracking(
    mesh: trimesh.Trimesh,
    output_path: str,
    original_has_textures: bool,
) -> dict:
    """
    Export a Trimesh to disk and report texture preservation status.

    Tries trimesh's export (which may preserve textures via material files
    for OBJ/MTL).  If the output format does not support textures or the
    export loses them, records the reason.
    """
    output_ext = os.path.splitext(output_path)[1].lower()
    texture_loss_reason: str | None = None
    export_mode_used = "full"
    warnings: list[str] = []

    try:
        _ensure_uv_material(mesh)
        mesh.export(output_path)
    except Exception as exc:
        warnings.append(f"Standard trimesh export failed: {exc}")
        try:
            geo = trimesh.Trimesh(
                vertices=np.asarray(mesh.vertices, dtype=np.float64),
                faces=np.asarray(mesh.faces, dtype=np.int64),
                process=False,
            )
            geo.export(output_path)
            export_mode_used = "trimesh_fallback"
        except Exception as exc2:
            raise RuntimeError(f"Could not save mesh output: {exc2}")

    # Determine texture preservation
    texture_preserved = True
    if original_has_textures:
        if output_ext not in (".obj", ".glb", ".gltf"):
            texture_preserved = False
            texture_loss_reason = (
                f"Output format '{output_ext}' does not support embedded textures"
            )
            warnings.append(texture_loss_reason)
        elif export_mode_used == "trimesh_fallback":
            texture_preserved = False
            texture_loss_reason = "Fallback export mode — textures not preserved"
            warnings.append(texture_loss_reason)

    return _export_result(
        texture_preserved=texture_preserved,
        texture_loss_reason=texture_loss_reason,
        export_mode_used=export_mode_used,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Helpers — PyMeshLab save with texture-export tracking
# ---------------------------------------------------------------------------

# Export mode descriptions for the texture tracking log
_EXPORT_MODE_LABELS: dict[str, str] = {
    "full": "Full export with textures and all attributes",
    "no_textures": "Textures disabled — geometry only with vertex attributes",
    "no_texcoord": "Textures and UV coordinates disabled",
    "minimal": "Minimal export — geometry only, no normals, no colours",
    "trimesh_fallback": "Fallback trimesh export — pure geometry",
}


def _export_result(
    texture_preserved: bool,
    texture_loss_reason: str | None,
    export_mode_used: str,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "texture_preserved": texture_preserved,
        "texture_loss_reason": texture_loss_reason,
        "export_mode_used": export_mode_used,
        "warnings": warnings or [],
    }


def _save_current_mesh(
    ms: pymeshlab.MeshSet,
    output_path: str | Path,
    original_has_textures: bool = False,
) -> dict:
    """
    Save the current PyMeshLab mesh to disk, tracking texture fidelity.

    Tries progressively simpler save configurations until one succeeds.
    Returns a dict with texture-preservation metadata.
    """
    output_path = str(output_path)
    save_attempts = [
        ({"save_textures": True}, "full"),
        ({"save_textures": False}, "no_textures"),
        ({"save_textures": False, "save_wedge_texcoord": False}, "no_texcoord"),
        (
            {
                "save_textures": False,
                "save_wedge_texcoord": False,
                "save_vertex_normal": False,
                "save_vertex_color": False,
                "save_face_color": False,
            },
            "minimal",
        ),
    ]

    last_error: Exception | None = None
    export_mode_used = "full"

    for kwargs, mode_name in save_attempts:
        try:
            ms.save_current_mesh(output_path, **kwargs)
            export_mode_used = mode_name
            break
        except Exception as exc:
            last_error = exc
            continue
    else:
        # Final fallback: export pure geometry through trimesh.
        try:
            mesh = ms.current_mesh()
            vertices = np.asarray(mesh.vertex_matrix(), dtype=np.float64)
            faces = np.asarray(mesh.face_matrix(), dtype=np.int64)
            if vertices.size > 0 and faces.size > 0:
                tri_mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
                tri_mesh.export(output_path)
                export_mode_used = "trimesh_fallback"
        except Exception as exc:
            last_error = exc
            raise RuntimeError(f"Could not save mesh output: {last_error}")

    # Determine texture preservation status
    texture_preserved = True
    texture_loss_reason = None
    warnings: list[str] = []

    if original_has_textures and export_mode_used != "full":
        texture_preserved = False
        texture_loss_reason = (
            f"PyMeshLab could not export with textures; "
            f"used '{export_mode_used}' mode instead"
        )
        warnings.append(texture_loss_reason)
    elif not original_has_textures and export_mode_used == "full":
        if output_path.endswith((".obj", ".ply")):
            pass  # Full mode without textures is fine for these formats

    return _export_result(
        texture_preserved=texture_preserved,
        texture_loss_reason=texture_loss_reason,
        export_mode_used=export_mode_used,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Helpers — topology cleanup
# ---------------------------------------------------------------------------

def _apply_structure_preclean(ms: pymeshlab.MeshSet) -> None:
    for filter_name, kwargs in [
        ("meshing_remove_duplicate_vertices", {}),
        ("meshing_remove_duplicate_faces", {}),
        ("meshing_remove_unreferenced_vertices", {}),
        ("meshing_repair_non_manifold_vertices", {}),
        ("meshing_repair_non_manifold_edges", {"method": 0}),
    ]:
        try:
            ms.apply_filter(filter_name, **kwargs)
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Core — per-component QEM decimation
# ---------------------------------------------------------------------------

def _apply_decimation(
    ms: pymeshlab.MeshSet,
    target_faces: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
) -> None:
    """
    Run importance-weighted (quality-weighted) QEM on the current mesh.

    The per-vertex quality scalar must have been injected beforehand (see
    ``_inject_importance_as_quality``).  When ``qualityweight=True``
    the quadric error metric penalises collapsing high-quality (high-importance)
    vertices, biasing decimation toward low-importance regions.
    """
    ms.apply_filter(
        "meshing_decimation_quadric_edge_collapse",
        targetfacenum=int(max(target_faces, 4)),
        preservenormal=preserve_normals,
        preserveboundary=preserve_boundaries,
        preservetopology=False,       # True breaks disconnected components
        planarquadric=False,          # Distorts curved/organic surfaces
        qualitythr=0.3,
        qualityweight=True,
        selected=False,
    )


def _inject_importance_as_quality(ms: pymeshlab.MeshSet, importance: np.ndarray) -> bool:
    """
    Write per-vertex importance scores into PyMeshLab's quality field.

    PyMeshLab's weighted QEM reads from this field when qualityweight=True.
    Higher quality = protected from collapse.

    This is done fully in-memory by adding a custom scalar attribute and
    using the compute_scalar_by_function_per_vertex filter to copy it
    into the primary quality scalar.

    Returns True if the injection succeeded, False if decimation will run
    without the quality scalar.
    """
    n_verts = ms.current_mesh().vertex_number()
    if len(importance) != n_verts:
        logger.warning(
            "Importance length %d ≠ vertex count %d", len(importance), n_verts
        )
        return False

    quality = np.clip(importance.astype(np.float64), 0.0, 1.0)

    try:
        mesh = ms.current_mesh()

        # Add as a custom attribute (name must be unique to this MeshSet run)
        mesh.add_vertex_custom_scalar_attribute(quality, "crunch3d_importance")

        # Copy the custom attribute into the mesh's quality field
        ms.apply_filter(
            "compute_scalar_by_function_per_vertex",
            q="crunch3d_importance",
            normalize=False,
        )
        return True

    except Exception as exc:
        logger.warning("Importance injection failed: %s. Falling back to plain QEM.", exc)
        return False




def _decimate_component(
    mesh: trimesh.Trimesh,
    target_faces: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
    use_importance: bool = True,
    precomputed_importance: np.ndarray | None = None,
    cache: dict[int, np.ndarray] | None = None,
) -> trimesh.Trimesh | None:
    """
    Run QEM decimation on a single Trimesh component.

    When *use_importance* is True the importance map is computed and
    injected into the mesh's quality field, and ``qualityweight=True``
    causes the decimation to preferentially collapse low-importance
    edges.

    If *precomputed_importance* is provided and its length matches the
    vertex count after PyMeshLab preclean, it is used directly —
    skipping the expensive ``compute_importance()`` call.

    If *cache* is provided, importance computed on the post-preclean
    mesh is stored keyed by ``id(mesh)``, so subsequent retries that
    pass the same component object hit the cache regardless of whether
    *precomputed_importance* matched.
    """
    logger.info("Trimesh before conversion: %d", len(mesh.vertices))

    ms = _component_to_pymeshlab(mesh)
    logger.info("PyMeshLab after load: %d", ms.current_mesh().vertex_number())

    _apply_structure_preclean(ms)
    pml_verts = ms.current_mesh().vertex_number()
    logger.info("PyMeshLab after preclean: %d", pml_verts)

    current_faces = ms.current_mesh().face_number()
    if target_faces >= current_faces:
        return _pymeshlab_to_trimesh(ms)

    # ── Resolve importance: cache → precomputed → fresh compute ──
    importance: np.ndarray | None = None
    if use_importance:
        cache_key = id(mesh)
        if cache is not None and cache_key in cache:
            importance = cache[cache_key]
            logger.info("Using inter-retry cached importance (%d)", len(importance))
        elif (
            precomputed_importance is not None
            and len(precomputed_importance) == pml_verts
        ):
            importance = precomputed_importance
            logger.info("Using precomputed importance (%d)", len(importance))
        else:
            pml_mesh = ms.current_mesh()
            verts = np.asarray(pml_mesh.vertex_matrix(), dtype=np.float64)
            faces = np.asarray(pml_mesh.face_matrix(), dtype=np.int64)
            tmp_trimesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)

            importance = compute_importance(tmp_trimesh)
            logger.info("Importance array: %d", len(importance))
            assert len(importance) == pml_verts, (
                f"Importance len {len(importance)} != vertex count {pml_verts}"
            )
            if cache is not None:
                cache[cache_key] = importance
                logger.info("Stored in inter-retry cache (%d)", len(importance))

    if importance is not None:
        injection_ok = _inject_importance_as_quality(ms, importance)
        logger.info("Injection success: %s", injection_ok)

    _apply_decimation(
        ms=ms,
        target_faces=target_faces,
        preserve_normals=preserve_normals,
        preserve_boundaries=preserve_boundaries,
    )

    result = _pymeshlab_to_trimesh(ms)

    return result


def _decimate_all_components(
    components: list[trimesh.Trimesh],
    target_faces: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
    use_importance: bool = True,
    component_importance: list[np.ndarray] | None = None,
    cache: dict[int, np.ndarray] | None = None,
) -> trimesh.Trimesh:
    """
    Decimate each component proportionally with importance weighting,
    then merge back into one mesh.

    If *component_importance* is provided it must be the same length as
    *components*; each entry is the precomputed importance array for the
    corresponding component.

    If *cache* is provided it is forwarded to ``_decimate_component``
    for inter-retry importance caching.
    """
    total_faces = sum(len(c.faces) for c in components)
    output_parts: list[trimesh.Trimesh] = []

    for idx, component in enumerate(components):
        if len(component.faces) == 0:
            continue

        ratio = len(component.faces) / total_faces if total_faces > 0 else 1.0
        component_target = max(4, int(target_faces * ratio))

        precomputed = (
            component_importance[idx]
            if component_importance is not None and idx < len(component_importance)
            else None
        )

        result = _decimate_component(
            mesh=component,
            target_faces=component_target,
            preserve_normals=preserve_normals,
            preserve_boundaries=preserve_boundaries,
            use_importance=use_importance,
            precomputed_importance=precomputed,
            cache=cache,
        )
        if result is not None:
            output_parts.append(result)

    if not output_parts:
        raise RuntimeError("All mesh components failed decimation")

    if len(output_parts) == 1:
        return _ensure_uv_material(output_parts[0])

    try:
        return _scene_merge(output_parts)
    except Exception as exc:
        logger.warning("Scene merge failed (%s), falling back to concatenate.", exc)
        return trimesh.util.concatenate(output_parts)


# ---------------------------------------------------------------------------
# Helpers — texture / animation detection
# ---------------------------------------------------------------------------

def _components_have_textures(components: list[trimesh.Trimesh]) -> bool:
    """Check if any component carries texture data (UVs + material)."""
    for c in components:
        visual = getattr(c, "visual", None)
        if visual is not None and getattr(visual, "kind", None) == "texture":
            return True
    return False




# ---------------------------------------------------------------------------
# Helpers — quality guard
# ---------------------------------------------------------------------------

def _sample_vertices(vertices: np.ndarray, max_count: int) -> np.ndarray:
    if vertices.shape[0] <= max_count:
        return vertices
    rng = np.random.default_rng(42)
    indices = rng.choice(vertices.shape[0], max_count, replace=False)
    return vertices[indices]




def _build_quality_reference(components: list[trimesh.Trimesh]) -> dict | None:
    all_vertices = np.vstack([np.asarray(c.vertices, dtype=np.float64)
                               for c in components if len(c.vertices) > 0])
    if len(all_vertices) == 0:
        return None

    all_faces = sum(len(c.faces) for c in components)
    if all_faces == 0:
        return None

    combined = trimesh.util.concatenate(components)
    diagonal = float(np.linalg.norm(combined.bounding_box.extents))
    if diagonal <= 1e-9:
        return None

    sampled = _sample_vertices(all_vertices, QUALITY_SAMPLE_CAP)
    return {"points": sampled, "diagonal": diagonal}


def _nearest_neighbor_distances(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    count = source.shape[0]
    min_dist_sq = np.full(count, np.inf, dtype=np.float64)

    for start in range(0, count, QUALITY_CHUNK_SIZE):
        chunk = source[start:start + QUALITY_CHUNK_SIZE]
        delta = chunk[:, None, :] - target[None, :, :]
        dist_sq = np.sum(delta * delta, axis=2)
        min_dist_sq[start:start + len(chunk)] = np.min(dist_sq, axis=1)

    return np.sqrt(min_dist_sq)


def _surface_deviation_percent(
    quality_ref: dict,
    result_mesh: trimesh.Trimesh,
) -> float | None:
    optimized_points = np.asarray(result_mesh.vertices, dtype=np.float64)
    if optimized_points.shape[0] == 0:
        return None

    optimized_points = _sample_vertices(optimized_points, QUALITY_SAMPLE_CAP)
    reference_points = quality_ref["points"]

    src_to_dst = _nearest_neighbor_distances(reference_points, optimized_points)
    dst_to_src = _nearest_neighbor_distances(optimized_points, reference_points)

    p95 = float(max(np.percentile(src_to_dst, 95), np.percentile(dst_to_src, 95)))
    return round((p95 / quality_ref["diagonal"]) * 100, 4)


def _build_target_candidates(
    current_faces: int,
    target_faces: int,
    max_target_overshoot_percent: float,
) -> list[int]:
    target = int(max(4, min(target_faces, current_faces - 1)))
    overshoot_factor = max(0.0, float(max_target_overshoot_percent)) / 100.0
    cap = int(max(target, min(int(round(target * (1.0 + overshoot_factor))), current_faces - 1)))

    candidates: list[int] = []
    for ratio in [0.0, 0.03, 0.06, 0.09, 0.12]:
        candidate = target + int((cap - target) * ratio / 0.12) if cap > target else target
        candidate = int(max(4, min(candidate, cap)))
        if candidate not in candidates:
            candidates.append(candidate)

    if cap not in candidates:
        candidates.append(cap)

    return candidates


# ---------------------------------------------------------------------------
# Helpers — stats
# ---------------------------------------------------------------------------

def _stats_from_trimesh(mesh: trimesh.Trimesh, output_path: str) -> MeshStats:
    file_size = os.path.getsize(output_path)
    bb = mesh.bounding_box
    extents = bb.extents.tolist()
    bounds = mesh.bounds  # shape (2, 3)
    bounding_box = {
        "min": bounds[0].tolist(),
        "max": bounds[1].tolist(),
        "diagonal": float(np.linalg.norm(extents)),
    }
    return MeshStats(
        vertex_count=len(mesh.vertices),
        face_count=len(mesh.faces),
        file_size_bytes=file_size,
        file_size_mb=round(file_size / (1024 * 1024), 3),
        has_uvs=hasattr(mesh, "visual") and hasattr(mesh.visual, "uv") and mesh.visual.uv is not None,
        has_normals=mesh.vertex_normals is not None and len(mesh.vertex_normals) > 0,
        bounding_box=bounding_box,
    )


# ---------------------------------------------------------------------------
# Public API — decimate_mesh  (signature unchanged)
# ---------------------------------------------------------------------------

def decimate_mesh(
    input_path: str | Path,
    output_path: str | Path,
    target_faces: int,
    preserve_normals: bool = True,
    preserve_boundaries: bool = True,
    strict_quality: bool = True,
    max_deviation_percent: float = 2.0,
    max_target_overshoot_percent: float = 12.0,
    use_importance: bool = True,       # v1.1: importance-weighted QEM
) -> tuple[MeshStats, dict]:
    input_path = str(input_path)
    output_path = str(output_path)

    _timing_reset()

    # ── 1. Load all components ──────────────────────────────────────────────
    components = _load_components(input_path)
    total_faces = sum(len(c.faces) for c in components)

    # ── Detect texture metadata ────────────────────────────
    original_has_textures = _components_have_textures(components)
    texture_export_info: dict | None = None

    # ── 2. Skip decimation if mesh is already at or below target ───────────
    if total_faces <= 4 or target_faces >= total_faces:
        combined = (
            _scene_merge(components)
            if len(components) > 1
            else _ensure_uv_material(components[0])
        )
        combined.export(output_path)
        stats = _stats_from_trimesh(combined, output_path)
        _timing_report()
        return stats, {
            "target_faces_used": total_faces,
            "quality_deviation_percent": 0.0,
            "quality_guard_relaxed": False,
            "quality_guard_satisfied": True,
            "importance_scores": None,
            "texture_export_info": {
                "texture_preserved": original_has_textures,
                "texture_loss_reason": None,
                "export_mode_used": "full",
                "warnings": [],
            },
            "original_has_textures": original_has_textures,
        }

    requested_target = int(max(4, min(target_faces, total_faces - 1)))

    # ── 3. Precompute importance once per component (cached for retries) ──
    component_importance: list[np.ndarray] | None = None
    flat_importance: list[float] = []
    if use_importance:
        component_importance = []
        for c in components:
            if len(c.faces) == 0:
                component_importance.append(np.array([], dtype=np.float64))
                continue
            imp = compute_importance(c)
            component_importance.append(imp)
            flat_importance.extend(imp.tolist())
    importance_scores = flat_importance if flat_importance else None

    # ── 4. Inter-retry importance cache (post-preclean, keyed by id) ────
    _importance_cache: dict[int, np.ndarray] = {}

    # ── 5. Build quality reference from original components ────────────────
    quality_ref = _build_quality_reference(components) if strict_quality else None

    # ── 6. Build candidate targets for quality-guard retry loop ───────────
    candidate_targets = (
        _build_target_candidates(
            current_faces=total_faces,
            target_faces=requested_target,
            max_target_overshoot_percent=max_target_overshoot_percent,
        )
        if strict_quality
        else [requested_target]
    )

    last_stats: MeshStats | None = None
    last_deviation: float | None = None
    last_target = requested_target
    last_result: trimesh.Trimesh | None = None

    # ── 7. Retry loop — tighten target until quality guard is satisfied ────
    for candidate_target in candidate_targets:
        result = _decimate_all_components(
            components=components,
            target_faces=candidate_target,
            preserve_normals=preserve_normals,
            preserve_boundaries=preserve_boundaries,
            use_importance=use_importance,
            component_importance=component_importance,
            cache=_importance_cache,
        )

        texture_export_info = _export_mesh_with_texture_tracking(
            result, output_path, original_has_textures
        )
        stats = _stats_from_trimesh(result, output_path)
        deviation = _surface_deviation_percent(quality_ref, result) if quality_ref else None

        last_stats = stats
        last_deviation = deviation
        last_target = candidate_target
        last_result = result

        if not strict_quality or quality_ref is None:
            break

        if deviation is not None and deviation <= max_deviation_percent:
            _timing_report()
            return stats, {
                "target_faces_used": stats.face_count,
                "quality_deviation_percent": deviation,
                "quality_guard_relaxed": candidate_target != requested_target,
                "quality_guard_satisfied": True,
                "importance_scores": importance_scores,
                "texture_export_info": texture_export_info,
                "original_has_textures": original_has_textures,
            }

    if last_stats is None:
        raise RuntimeError("Decimation failed to produce an output mesh")

    quality_guard_satisfied = True
    if strict_quality and quality_ref is not None and last_deviation is not None:
        quality_guard_satisfied = last_deviation <= max_deviation_percent

    _timing_report()
    return last_stats, {
        "target_faces_used": last_stats.face_count,
        "quality_deviation_percent": last_deviation,
        "quality_guard_relaxed": last_target != requested_target,
        "quality_guard_satisfied": quality_guard_satisfied,
        "importance_scores": importance_scores,
        "texture_export_info": texture_export_info,
        "original_has_textures": original_has_textures,
    }


# ---------------------------------------------------------------------------
