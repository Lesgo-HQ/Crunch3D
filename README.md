# Crunch3D Community

A local 3D mesh optimizer with curvature-weighted quadric error decimation.
Run it on your own hardware, inspect the result, and export without an account,
watermark, daily download quota, telemetry or automatic training on your assets.

## Included

- Static mesh upload and inspection; target presets and a custom face budget.
- Curvature-weighted QEM with boundary and normal preservation options.
- Sampled quality guard with retries and an explicit pass/fail report.
- Before/after viewer, wireframe, curvature heatmap and optimization statistics.
- Single-result exports and a documented local API at `/docs`.
- Basic UV/material handling. Textured results use self-contained GLB output.

Crunch3D-Pro is maintained separately for advanced optimization and hosted workflows.
The marketing website is not part of this repository.

## Run locally

Use Python 3.11 and Node.js 18+ with pnpm. From the repository root:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r model/requirements.txt
cp .env.example .env
uvicorn model.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd web
pnpm install --frozen-lockfile
pnpm dev
```

Open http://localhost:5173. The development server proxies `/api` to the local backend.
On Linux, PyMeshLab may need OpenGL system libraries; the supplied Dockerfile includes them.

## Local data and limits

Uploads and results stay in `model/uploads/` and `model/processed/` until deleted.
`DELETE /api/job/{job_id}` removes a job and its files. These folders are ignored by Git.
The default 50 MB upload ceiling is a local resource safeguard; adjust
`MAX_FILE_SIZE_MB` in `.env` to suit your hardware. There are no per-day usage limits.
Bind the API to localhost: this edition has no multi-user authentication or tenant isolation.

## Supported files and limitations

OBJ, STL, PLY, GLB, GLTF, FBX and OFF are accepted for analysis, subject to loader support.
Prefer self-contained GLB for textures. Uploading external GLTF buffers or OBJ texture
sidecars together is not supported. OFF has no browser preview; FBX support depends on
installed loaders. Rigging and animations are not preserved. Multi-material/component
exports can lose material detail; inspect outputs before production use.

The quality guard measures sampled nearest-vertex deviation, not a guaranteed maximum
surface error. It may report that the requested threshold was not met even after retries.
The viewer's curvature heatmap is approximate when file loaders reorder vertices.

## Checks

```sh
pip install -r model/requirements-dev.txt
python -m pytest model/tests -q
pnpm --dir web build
```

## API

Upload with `POST /api/upload`, then use the returned `job_id` with
`POST /api/optimize` and `GET /api/download/{job_id}`. Inspect the generated
OpenAPI documentation at http://localhost:8000/docs for the complete schema.
Only community operations are implemented; unknown optimization options are rejected.
