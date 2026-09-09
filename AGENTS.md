# Repository Guidelines

## Project scope

This repository contains a PySide6 desktop application for real-time ASL fingerspelling recognition. Runtime inference uses MediaPipe Gesture Recognizer task bundles from `models/`; model training remains in the Google Colab notebook under `notebooks/`.

## Development workflow

- Use Python 3.10 or 3.12 for local development and CI.
- Install development dependencies with `python -m pip install -r requirements-dev.txt`.
- Run the application from the repository root with `python src/main.py`.
- Run the regression suite with `python -m pytest` before committing.
- Keep MediaPipe below 0.10.30 unless the legacy landmark drawing code is migrated and all shipped models are retested.
- Preserve both locally patched protobuf wheels and their provenance. If either wheel or patch changes, rebuild with Python 3.10 using `scripts/build_patched_protobuf.ps1`, update recorded checksums and run `tests/test_protobuf_patch.py`.

## Conventions

- Name branches with a prefix and a kebab-case description: `feature/`, `fix/`, `docs/`, `spike/` or `variant/` — for example `feature/threaded-camera-capture`. `variant/*` branches are long-lived alternative versions of the application; they keep their own history and releases and are never merged into `main` or `develop`.
- Write commit subjects in English, in the imperative mood, capitalized and without a trailing period. Do not use Conventional Commits type prefixes. Add a body whenever the reason for the change is not obvious from the subject.
- Open pull requests against `develop` for features, fixes, documentation, tests and CI, and against the corresponding `variant/*` branch for work on a product variant. `main` is the release branch: the maintainer promotes `develop` to `main` and tags releases there, so pull requests do not target `main`.
- Integrate every pull request with GitHub's **rebase and merge**. History stays linear, with no merge commits and no squashing, so each commit must be self-contained and pass on its own. Keep one topic per pull request and update branches by rebasing onto the target branch, never by merging the target into them.
- Tag releases with semantic version tags `vMAJOR.MINOR.PATCH` (`v1.0.0` … `v1.1.1`). Variant releases carry a suffix, for example `v1.2.0-podtekst`, and are not marked as the Latest release.
- Write code, comments, commit messages, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md` and `THIRD_PARTY_NOTICES.md` in English. Keep `README.md` / `README.pl.md` and both technical documentation files in English and Polish.

## Contribution workflow

- External contributions follow [`CONTRIBUTING.md`](CONTRIBUTING.md): fork, add the upstream remote, branch from `upstream/develop` (or from the relevant `variant/*` branch) using the naming convention above, run the tests locally, then open a pull request against that same branch and keep it rebased.
- Two workflows guard the repository, and both cover pull requests to `main`, `develop` and `variant/*`: `.github/workflows/dependency-review.yml` and `.github/workflows/tests.yml`.
- `.github/workflows/tests.yml` also runs pytest and `pip-audit` on windows-latest with Python 3.10 and 3.12 on pushes to `main`, `develop` and `variant/*`.
- The pull request template lives in `.github/PULL_REQUEST_TEMPLATE.md`.

## Testing

- Run the regression suite from the repository root with `python -m pytest`, on Python 3.10 or 3.12 — the versions covered by CI.
- Tests must not require a physical camera, audible speech or network access.
- Run `python -m pytest tests/test_protobuf_patch.py` whenever the bundled protobuf wheels or their patches change; it verifies that the backported parser fix still rejects excessive nested `Any` data.

## Code boundaries

- Treat `src/gui.ui` as the source of truth for the interface. Regenerate `src/gui.py` with `pyside6-uic`; do not edit the generated file by hand.
- Keep camera capture, recognition, TTS and main-window coordination in their existing modules. Prefer focused fixes over broad refactors.
- Do not replace or retrain the `.task` files without documenting their source, evaluation and checksums.

## Documentation and security

- Keep `README.md` and `README.pl.md`, as well as both technical documentation files, equivalent in scope and facts.
- Use only real application screenshots. Preserve their aspect ratio and verify every local link.
- Never commit `kaggle.json`, API tokens, credentials, downloaded datasets or personal administrative forms.
- Preserve the license split: source code uses `LICENSE`, while the thesis and original documentation use `LICENSE-docs`.
- Keep `THIRD_PARTY_NOTICES.md` in sync whenever a dependency is added or removed, a version constraint changes, a bundled wheel is rebuilt, or a `.task` model is replaced or retrained.
- Report vulnerabilities according to `SECURITY.md`.
- Write GitHub release titles and descriptions in English. Describe packaging, verification and checksums neutrally; do not mention credential leaks or rewritten Git history.
