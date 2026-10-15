# Contributing to Crunch3D

Thanks for helping make local mesh optimization better. Bug reports, documentation fixes, small reproducible examples, and code improvements are all welcome.

Read our [code of conduct](CODE_OF_CONDUCT.md). For vulnerabilities, use the [security policy](SECURITY.md) instead of a public bug report. For setup help, see [SUPPORT.md](SUPPORT.md).

## Before starting

Search existing issues and pull requests. For a large algorithm change, new dependency, or new file format, open an issue first so we can agree on scope. Small fixes can go straight to a pull request.

Only share meshes, textures, screenshots, and code that you have permission to publish. Use a tiny generated mesh whenever possible. Remove credentials, private paths, and customer information from logs.

## Local setup

Follow the [README setup instructions](README.md#getting-started), then install the development dependencies from the repository root with your virtual environment active:

```sh
pip install -r model/requirements-dev.txt
pnpm --dir web install --frozen-lockfile
```

Create a branch in your fork and keep the change focused. Match the surrounding Python and JavaScript style. Avoid unrelated formatting and generated build files. Do not commit `.env`, uploads, processed meshes, virtual environments, or dependency folders.

## Checks

For backend or geometry changes, run:

```sh
python -m pytest model/tests -q
```

For frontend changes, run:

```sh
pnpm --dir web build
```

Use small synthetic fixtures for tests. Add a regression test for a behavior change where practical. UI changes should include a brief manual check and screenshots when useful. Documentation-only changes need link, spelling, and example checks, not a model run. State what you actually checked and any checks you could not run.

## Pull requests and review

Explain the problem, what changes for users, and how you verified it. Link the related issue if there is one. Call out API changes, dependency changes, output-format changes, and known limitations.

A maintainer reviews the patch before merging. Address review comments in the same pull request. The team may request a smaller scope or decline a change that does not fit the local application. There is no guaranteed review time.

## Rights and attribution

By intentionally submitting a contribution for inclusion, you agree to license your original contribution under `GPL-3.0-only`, as described in [COPYRIGHT.md](COPYRIGHT.md). You retain copyright; no copyright assignment is required.

Submit only work you created or have permission to contribute under compatible terms, including any required employer permission. Identify copied or adapted material, its source, and its license. Preserve third-party notices and update [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) when adding dependencies. Do not add assets with unclear redistribution rights.

GitHub attributes contributions using commit authorship. Use an email associated with your GitHub account, or your GitHub noreply address, if you want your commits linked to your profile.
