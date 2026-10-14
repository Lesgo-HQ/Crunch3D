"""Local API contract and synthetic mesh checks."""
from pathlib import Path

import numpy as np
import pytest
import trimesh
from fastapi.testclient import TestClient

from model.main import app
from model.api import routes
from model.services import file_handler
from model.engine.mesh_optimizer import decimate_mesh
from model.importance.importance_mapper import compute_importance


@pytest.fixture
def client(tmp_path, monkeypatch):
    uploads, processed = tmp_path / "uploads", tmp_path / "processed"
    uploads.mkdir()
    processed.mkdir()
    for module in (routes, file_handler):
        monkeypatch.setattr(module, "UPLOAD_DIR", uploads)
        monkeypatch.setattr(module, "PROCESSED_DIR", processed)
    routes.jobs.clear()
    with TestClient(app) as instance:
        yield instance
    routes.jobs.clear()


def test_api_surface_and_rejects_unknown_options(client):
    paths = client.get('/openapi.json').json()['paths']
    assert set(paths) == {
        '/api/upload', '/api/optimize', '/api/status/{job_id}',
        '/api/importance/{job_id}', '/api/preview/{job_id}',
        '/api/download/{job_id}', '/api/job/{job_id}', '/health',
    }
    result = client.post('/api/optimize', json={
        'job_id': 'a' * 12, 'target_faces': 100, 'unknown_option': True,
    })
    assert result.status_code == 422


def test_upload_optimize_preview_and_unlimited_download(client):
    mesh = trimesh.creation.icosphere(subdivisions=2)
    upload = client.post('/api/upload', files={'file': ('../../sphere.obj', mesh.export(file_type='obj'))})
    assert upload.status_code == 200, upload.text
    job = upload.json()['job_id']
    assert upload.json()['filename'] == 'sphere.obj'
    result = client.post('/api/optimize', json={
        'job_id': job, 'target_faces': 160, 'strict_quality': False,
    })
    assert result.status_code == 200, result.text
    data = result.json()
    assert 0 < data['optimized_stats']['face_count'] < len(mesh.faces)
    assert client.get(f'/api/preview/{job}').status_code == 200
    for _ in range(7):
        response = client.get(f'/api/download/{job}')
        assert response.status_code == 200
        assert response.content
        assert 'x-ratelimit-remaining' not in response.headers
    # Metadata restores an output without a cloud account or memory cache.
    routes.jobs.clear()
    assert client.get(f'/api/download/{job}').status_code == 200
    assert client.delete(f'/api/job/{job}').status_code == 200
    assert client.get(f'/api/download/{job}').status_code == 404


def test_invalid_mesh_and_size_limit(client, monkeypatch):
    assert client.post('/api/upload', files={'file': ('bad.exe', b'bad')}).status_code == 400
    assert client.post('/api/upload', files={'file': ('bad.obj', b'bad')}).status_code == 422
    monkeypatch.setattr(routes, 'MAX_FILE_SIZE_MB', 0.000001)
    assert client.post('/api/upload', files={'file': ('big.obj', b'v 0 0 0')}).status_code == 413
    assert list(file_handler.UPLOAD_DIR.iterdir()) == []
    assert client.get('/api/status/not-a-job').status_code == 404


def test_curvature_and_quality_guard(tmp_path):
    mesh = trimesh.creation.icosphere(subdivisions=2)
    importance = compute_importance(mesh)
    assert importance.shape == (len(mesh.vertices),)
    assert np.isfinite(importance).all()
    assert np.all((importance >= 0) & (importance <= 1))
    source, output = tmp_path/'sphere.obj', tmp_path/'result.obj'
    mesh.export(source)
    stats, meta = decimate_mesh(source, output, 40, strict_quality=True, max_deviation_percent=0.06)
    assert output.is_file() and stats.face_count > 0
    assert meta['quality_deviation_percent'] is not None
    assert meta['quality_guard_satisfied'] == (meta['quality_deviation_percent'] <= 0.06)


def test_textured_glb_export(tmp_path):
    from PIL import Image
    mesh = trimesh.creation.box()
    mesh.visual = trimesh.visual.TextureVisuals(
        uv=np.zeros((len(mesh.vertices), 2)), image=Image.new('RGB', (4, 4), 'red'),
    )
    source, output = tmp_path/'textured.glb', tmp_path/'result.glb'
    mesh.export(source)
    stats, meta = decimate_mesh(source, output, 100)
    loaded = trimesh.load(output, force='mesh')
    assert stats.face_count == len(mesh.faces)
    assert loaded.visual.kind == 'texture'
    assert meta['texture_export_info']['texture_preserved']


def test_zero_size_limit_allows_upload(client, monkeypatch):
    monkeypatch.setattr(routes, 'MAX_FILE_SIZE_MB', 0)
    # Tiny generated OBJ; no large files or real model assets are needed.
    mesh = trimesh.creation.box().export(file_type='obj')
    response = client.post('/api/upload', files={'file': ('box.obj', mesh)})
    assert response.status_code == 200, response.text
