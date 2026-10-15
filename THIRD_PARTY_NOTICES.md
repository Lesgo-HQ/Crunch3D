# Third-party dependencies and assets

Crunch3D depends on separately licensed software. The project license does not replace those licenses or their copyright notices.

## Dependency sources

- Backend runtime dependencies: [model/requirements.txt](model/requirements.txt).
- Backend development dependencies: [model/requirements-dev.txt](model/requirements-dev.txt).
- Frontend and build dependencies: [web/package.json](web/package.json) and [web/pnpm-lock.yaml](web/pnpm-lock.yaml).

[PyMeshLab](https://github.com/cnr-isti-vclab/PyMeshLab) is GPL-licensed. Its [upstream license](https://github.com/cnr-isti-vclab/PyMeshLab/blob/main/LICENSE) contains GPL version 3. Crunch3D uses `GPL-3.0-only` for its original code and documentation. Preserve PyMeshLab's notices and check the license files in the exact installed distribution when redistributing it.

Other direct dependencies include FastAPI, python-dotenv, Uvicorn, python-multipart, Trimesh, Pillow, NumPy, SciPy, Pydantic, pytest, HTTPX, React, React DOM, Three.js, React Three Fiber, Drei, Axios, Workbox, Vite, Tailwind CSS, PostCSS, Autoprefixer, and the associated frontend plugins and type packages. Consult each installed package's license and notice files for the version being shipped.

This is a source dependency guide, not an exhaustive license inventory or a complete binary redistribution notice bundle. Python wheels and JavaScript packages can include additional native libraries, fonts, code, or other assets with separate terms. Backend dependency ranges also mean different installations can resolve to different versions.

## Before distributing a build or container

1. Record the exact dependency versions, including transitive dependencies and system packages.
2. Collect and retain their required license, copyright, and attribution notices.
3. Review bundled native libraries and any license exceptions in the installed wheels.
4. Provide corresponding source and build information wherever required by the applicable licenses. A link to the project's current main branch alone may not satisfy the requirements for the version shipped.

## Repository images and external services

The logos in `assets/branding/` were supplied for this project. The images embedded in `assets/team/` depict the four linked GitHub profiles. These assets are excluded from the project license grant; see [COPYRIGHT.md](COPYRIGHT.md).

The README uses Shields.io for badges and contrib.rocks for the contributor gallery. Those external services and the profile images retain their own rights and policies. Their presence does not imply endorsement.
