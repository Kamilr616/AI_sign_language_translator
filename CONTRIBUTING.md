# Contributing

Thank you for considering a contribution to **AI Sign Language Translator**.
This document describes how to set up the project, how the branches and pull
requests are organized, and what a change has to satisfy before it can be
merged.

[`AGENTS.md`](AGENTS.md) holds the full list of repository guidelines. This file
covers the contributor workflow; it does not repeat every rule from there.

## Before you start

- **Scope.** The repository contains a PySide6 desktop application for real-time
  ASL fingerspelling recognition. Runtime inference uses MediaPipe Gesture
  Recognizer `.task` bundles from `models/`; model training lives in the Google
  Colab notebook under `notebooks/`. Changes that fit that scope are welcome;
  broad rewrites of the existing modules are not.
- **Security issues are not public issues.** Report a suspected vulnerability
  privately as described in [`SECURITY.md`](SECURITY.md).
- **Talk first for anything larger than a fix.** Open an issue describing the
  problem or the feature before writing code, so the approach can be agreed
  before you invest time in it. Small, self-contained bug fixes can go straight
  to a pull request.

## Development setup

Use **Python 3.10 or 3.12** (64-bit) — those are the versions covered by CI.

Clone your own fork (after forking, see the [workflow](#workflow) below):

```bash
git clone https://github.com/<your-user>/AI_sign_language_translator.git
cd AI_sign_language_translator

python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` includes the runtime requirements, so this single install
covers both running the application and running the tests.

```bash
python src/main.py     # run the application (from the repository root)
python -m pytest       # run the regression suite
```

Tests must not require a physical camera, audible speech or network access. If a
change needs one of those, isolate it behind a fake or a fixture instead.

## Workflow

1. **Fork** the repository on GitHub and clone your fork, as in
   [Development setup](#development-setup) above.
2. **Add the upstream remote** pointing at this repository:
   ```bash
   git remote add upstream https://github.com/Kamilr616/AI_sign_language_translator.git
   git fetch upstream
   ```
3. **Branch from the right base.** Regular work starts from `upstream/develop`:
   ```bash
   git switch -c fix/camera-backend-fallback upstream/develop
   ```
   Work on a product variant starts from that variant's branch instead — see
   [Where a pull request goes](#where-a-pull-request-goes) below.
4. **Make the change**, keeping it focused on one topic.
5. **Run the tests locally** with `python -m pytest`, and run the application if
   the change is visible in the GUI.
6. **Commit** using the message convention below.
7. **Push to your fork** and open a pull request against the correct target
   branch, filling in the pull request template.
8. **Address review comments** with additional commits or by rebasing, and keep
   the branch up to date by rebasing onto the target branch.

### Where a pull request goes

| Kind of change | Target branch |
|---|---|
| Features, fixes, documentation, tests, CI | `develop` |
| Work on an alternative version of the application (product variant, e.g. `variant/podtekst`) | that same `variant/*` branch |
| Release preparation and tagging | maintainer only, on `main` |

`main` is the release branch: the maintainer promotes `develop` to `main` and
tags the release there. Do not open pull requests against `main`.

`variant/*` branches are long-lived alternative versions of the application.
They are **not** merged back into `main` (or into `develop`); each keeps its own
history and its own releases, so a change meant for a variant must target that
variant's branch directly.

### Rebase and merge

Every pull request is integrated with GitHub's **rebase and merge**, which keeps
the history linear — there are no merge commits and no squashing. Two
consequences for contributors:

- **Every commit in the pull request lands separately on the target branch**, so
  each one must be self-contained, build, and pass the tests on its own. Split
  unrelated work into separate commits; fold fix-ups into the commit they
  correct rather than appending "fix typo" commits.
- **Update the branch by rebasing, never by merging the target into it:**
  ```bash
  git fetch upstream
  git rebase upstream/develop
  git push --force-with-lease
  ```
  Use `--force-with-lease` (not plain `--force`) so a push is refused if someone
  else has updated the branch in the meantime.

### Continuous integration

- [`dependency-review.yml`](.github/workflows/dependency-review.yml) runs on pull
  requests targeting `main`, `develop` and `variant/*`, and flags dependency
  changes that introduce known-vulnerable versions.
- [`tests.yml`](.github/workflows/tests.yml) runs pytest and `pip-audit` on
  Windows with Python 3.10 and 3.12. Like `dependency-review.yml`, it runs on
  pull requests targeting `main`, `develop` and `variant/*`, and it also runs
  on pushes to those same branches — run `python -m pytest` locally before
  opening a pull request regardless.

## Branch naming and commit messages

Branch names are a prefix plus a kebab-case description:

| Prefix | Used for |
|---|---|
| `feature/` | new functionality |
| `fix/` | bug fixes |
| `docs/` | documentation-only changes |
| `spike/` | throwaway experiments and investigations |
| `variant/` | long-lived alternative versions of the application (maintainer-managed, never merged into `main`) |

Examples: `feature/threaded-camera-capture`, `fix/tts-single-utterance`,
`docs/contributing-guidelines`.

Commit messages are written in **English**, using the **imperative mood**, with
a **capitalized** subject line and **no trailing period**. Do not use
Conventional Commits type prefixes (`feat:`, `chore:` and similar). Add a body
whenever the reason for the change is not obvious from the subject.

```
Drive pyttsx3 through its external loop to fix single-utterance TTS

pyttsx3 2.99 stops after the first utterance when say() is paired with
runAndWait(), because the SAPI driver never leaves the internal loop.
Driving the loop externally restores repeated playback.
```

```
Add Dependency Review workflow for PRs
```

```
Harden legacy release dependencies and packaging
```

## Pull request checklist

Before requesting a review, confirm that:

- [ ] `python -m pytest` passes locally on Python 3.10 or 3.12.
- [ ] The pull request targets `develop` (or the relevant `variant/*` branch),
      not `main`.
- [ ] Every commit in the branch is self-contained and passes on its own.
- [ ] [`README.md`](README.md) and [`README.pl.md`](README.pl.md) stay
      equivalent in scope and facts if either was touched.
- [ ] [`docs/TECHNICAL_DOCUMENTATION.md`](docs/TECHNICAL_DOCUMENTATION.md) and
      [`docs/TECHNICAL_DOCUMENTATION.pl.md`](docs/TECHNICAL_DOCUMENTATION.pl.md)
      stay equivalent if either was touched.
- [ ] Every local link in the changed documentation resolves, and any screenshot
      added is a real application screenshot with its aspect ratio preserved.
- [ ] `src/gui.py` was regenerated from `src/gui.ui` with `pyside6-uic` and not
      edited by hand.
- [ ] No `.task` model was replaced or retrained without documenting its source
      and evaluation and updating [`models/SHA256SUMS.txt`](models/SHA256SUMS.txt).
- [ ] [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) was updated if a
      dependency, a version constraint, a bundled wheel or a model changed.
- [ ] No credentials (`kaggle.json`, API tokens), datasets or personal
      administrative forms are included in the diff.

## Licensing of contributions

By opening a pull request you confirm that you wrote the contribution yourself
or otherwise have the right to submit it, and that it may be distributed under
the licenses used by this repository:

- **Source code, tests, scripts and models** — GNU General Public License v3.0,
  see [`LICENSE`](LICENSE).
- **Thesis text and original documentation, diagrams and screenshots** —
  CC BY-NC-ND 4.0, see [`LICENSE-docs`](LICENSE-docs).

Do not add third-party code, assets or data without checking that its license is
compatible with the above and recording it in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Reporting bugs

Open an issue and include:

- the application version or the commit you ran,
- your operating system and Python version,
- the camera and capture backend in use, and the `.task` model selected, if the
  problem is related to recognition,
- exact reproduction steps and what you expected to happen instead,
- the relevant console output or traceback.

Do not include real credentials, personal data or other secrets in an issue — a
report that would require them belongs in a private security report instead, as
described in [`SECURITY.md`](SECURITY.md).
