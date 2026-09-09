# Third-party notices

The **source code** of AI Sign Language Translator is distributed under the GNU
General Public License v3.0 ([`LICENSE`](LICENSE)). The thesis and the original
documentation, diagrams and screenshots are distributed under CC BY-NC-ND 4.0
([`LICENSE-docs`](LICENSE-docs)). Third-party material bundled in this
repository, and the dependencies installed alongside the application, remain
governed by their own terms as listed below. Copyrights and trademarks remain
the property of their respective owners.

## Material included in this repository

### Patched protobuf 4.25.9 wheels

`third_party/wheels/protobuf-4.25.9+aislt.cve20260994.1-cp310-abi3-win_amd64.whl`
and `third_party/wheels/protobuf-4.25.9+aislt.cve20260994.1-py3-none-any.whl`
are locally rebuilt copies of the official protobuf release, produced because
the MediaPipe version constraint excludes the upstream release line that carries
the fix for CVE-2026-0994 / PYSEC-2026-1805.

| Item | Value |
|---|---|
| Base version | protobuf 4.25.9 (official PyPI sdist and Windows wheel) |
| Local version | `4.25.9+aislt.cve20260994.1` |
| Security backport | protocolbuffers/protobuf PR 25239, commit `b210265f2b4c05e396e4590feb0c38ae6ae0cca4` |
| Advisory addressed | CVE-2026-0994 / PYSEC-2026-1805 |
| License | [BSD-3-Clause](third_party/protobuf/LICENSE) (Copyright 2008 Google Inc.) |
| Provenance and rebuild procedure | [`third_party/protobuf/README.md`](third_party/protobuf/README.md) |
| Checksums | [`third_party/protobuf/SHA256SUMS.txt`](third_party/protobuf/SHA256SUMS.txt) |

The visible patches applied on top of the upstream source are
[`CVE-2026-0994.patch`](third_party/protobuf/CVE-2026-0994.patch),
[`local-version.patch`](third_party/protobuf/local-version.patch) and
[`pure-python-wheel.patch`](third_party/protobuf/pure-python-wheel.patch).
The bundled protobuf source and binaries stay subject to the BSD 3-Clause
license reproduced in [`third_party/protobuf/LICENSE`](third_party/protobuf/LICENSE).

### MediaPipe gesture recognizer bundles

`models/gesture_recognizer_asl_0.task`, `models/gesture_recognizer_asl_1.task`
and `models/gesture_recognizer_asl_mp.task` are original work of the repository
author. They were trained with **MediaPipe Model Maker**
([Apache-2.0](https://spdx.org/licenses/Apache-2.0.html)) in Google Colab; the
reproducible pipeline is in
[`notebooks/Custom_gesture_recognizer.ipynb`](notebooks/Custom_gesture_recognizer.ipynb).
Each bundle embeds the stock MediaPipe hand detector and hand landmarker
(Apache-2.0) together with the custom classification head trained here.

The training data is the Kaggle dataset
[**ASL Alphabet** (`grassknoted/asl-alphabet`)](https://www.kaggle.com/datasets/grassknoted/asl-alphabet),
published by Akash Nagaraj under the license shown on that dataset page,
recorded there as **GPL 2** (DOI `10.34740/KAGGLE/DSV/29550`). **The dataset
itself is not redistributed in this repository** — it is downloaded through the
Kaggle API during training only.

The `.task` bundles ship with the source and are distributed under
[`LICENSE`](LICENSE). Their bytes are pinned in
[`models/SHA256SUMS.txt`](models/SHA256SUMS.txt) and verified by the regression
suite; provenance and held-out evaluation figures per model are documented in
[`docs/TECHNICAL_DOCUMENTATION.md`](docs/TECHNICAL_DOCUMENTATION.md#54-shipped-models)
· [wersja polska](docs/TECHNICAL_DOCUMENTATION.pl.md#54-modele-dołączone-do-repozytorium).

### Bundled fonts (JetBrains Mono)

`src/assets/fonts/JetBrainsMono-Regular.ttf` and
`src/assets/fonts/JetBrainsMono-ExtraBold.ttf` are unmodified copies of the
JetBrains Mono typeface, used by the PodTeksT theme.

| Item | Value |
|---|---|
| Files | `src/assets/fonts/JetBrainsMono-Regular.ttf`, `src/assets/fonts/JetBrainsMono-ExtraBold.ttf` |
| Copyright | Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono) |
| License | [SIL Open Font License 1.1](src/assets/fonts/OFL.txt) |
| License text | shipped alongside the fonts in [`src/assets/fonts/OFL.txt`](src/assets/fonts/OFL.txt) |

[`src/main.py`](src/main.py) registers every `.ttf` in that directory with the
font database at start-up; a font file that cannot be registered only produces a
warning and the interface falls back to the system fonts.

## Python dependencies

Where a version constraint exists in the requirements files, the Version column
quotes it verbatim; the patched protobuf build is pinned as local wheel paths
with environment markers, and transitive packages are resolved by pip. No
dependency source is vendored except the protobuf wheels above.

### Runtime dependencies (`src/requirements.txt`)

| Package | Version | License |
|---|---|---|
| protobuf (locally patched, bundled wheels) | `4.25.9+aislt.cve20260994.1` | [BSD-3-Clause](third_party/protobuf/LICENSE) |
| mediapipe | `>=0.10.14,<0.10.30` | [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html) |
| pyttsx3 | `>=2.98` | [MPL-2.0](https://spdx.org/licenses/MPL-2.0.html) |
| PySide6 | `>=6.7.3` | [LGPL-3.0-only](https://spdx.org/licenses/LGPL-3.0-only.html) OR [GPL-2.0-only](https://spdx.org/licenses/GPL-2.0-only.html) OR [GPL-3.0-only](https://spdx.org/licenses/GPL-3.0-only.html), or a commercial Qt license; this GPLv3 application uses Qt for Python under the GPL terms |
| symspellpy | `>=6.10.0,<7` | [MIT](https://spdx.org/licenses/MIT.html) (Copyright 2025 mmb L, the Python port; Copyright 2021 Wolf Garbe for the original SymSpell C# implementation, also MIT) |

The Windows release build passes `--collect-data symspellpy`, so the English
frequency dictionaries shipped inside that package
(`frequency_dictionary_en_82_765.txt` and
`frequency_bigramdictionary_en_243_342.txt`, taken from the SymSpell project and
covered by the same MIT license) are packaged into both executables. `symspellpy`
itself declares no runtime dependencies, so it adds nothing to the transitive
list below.

### Transitive runtime dependencies

These packages are not pinned by this repository. They are resolved by pip from
`mediapipe`, and are listed because the application imports them directly.

| Package | Version | License |
|---|---|---|
| opencv-contrib-python | resolved by pip from `mediapipe` (no local constraint) | [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html); the OpenCV packaging scripts are [MIT](https://spdx.org/licenses/MIT.html) |
| numpy | resolved by pip from `mediapipe` (`numpy<2`, no local constraint) | [BSD-3-Clause](https://spdx.org/licenses/BSD-3-Clause.html) |

MediaPipe additionally pulls `absl-py`, `attrs`, `flatbuffers`, `jax`,
`jaxlib`, `matplotlib`, `sounddevice` and `sentencepiece`. They are not
enumerated here, are not imported by this application, and retain their own
upstream licenses.

### Development and build tools (`requirements-dev.txt`)

These are not shipped with the application or with a release build.

| Package | Version | License |
|---|---|---|
| pytest | `>=9.0.3,<10` | [MIT](https://spdx.org/licenses/MIT.html) |
| pyinstaller | `>=6.11,<7` | [GPL-2.0-or-later with the PyInstaller bootloader exception](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt), which permits distributing applications built with it under any license |
| pip-audit | `>=2.9,<3` | [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html) |

## System components used at runtime

The application calls two system-provided components. Neither is redistributed
with the source or with a release build.

- **Microsoft Speech API (SAPI5)** — driven through `pyttsx3` on Windows for
  offline speech synthesis. It is a component of the operating system and is
  covered by the user's Windows license.
- **Operating-system camera stack** — reached through OpenCV
  (`cv2.VideoCapture`) using DirectShow or Media Foundation on Windows and V4L2
  or GStreamer on Linux. The drivers and capture frameworks belong to the
  operating system or to the camera vendor.

## Externally loaded assets and trademarks

The status badges at the top of [`README.md`](README.md) and
[`README.pl.md`](README.pl.md) are images loaded at display time from
[shields.io](https://shields.io/); they are not stored in this repository. The
READMEs also link to GitHub-hosted release assets. GitHub and the GitHub logo
are trademarks of GitHub, Inc.

`src/assets/podtekst-logo.png` is the **PodTeksT** wordmark, shown in the window
header (see [`src/gui.py`](src/gui.py)). It was contributed by Michał Wiencek
(PodTeksT) in pull request 13 of this repository. The PodTeksT name and wordmark
remain the property of their owner and are **not** covered by the GPL-3.0 license
of the source code.

The names, logos and marks of **Qt**, **MediaPipe**, **OpenCV**, **Kaggle**,
**Google Colab**, **TensorFlow** and **PyCharm** belong to their respective
owners and are used here only to identify the technologies involved. Their
appearance does not imply any endorsement of this repository or of its author.
The same reservation is made in [`LICENSE-docs`](LICENSE-docs) for marks that
appear in the documentation.

## Verification note

Checked on **2026-09-09** against the constraints recorded in
[`src/requirements.txt`](src/requirements.txt) and
[`requirements-dev.txt`](requirements-dev.txt): **10 packages** are enumerated
above — 5 direct runtime dependencies, 2 transitive runtime dependencies and 3
development or build tools. The complete resolved dependency graph is larger
than this list; it is scanned for known advisories by the `pip-audit` steps of
the [Tests workflow](.github/workflows/tests.yml), and the metadata and license
file shipped inside each installed distribution remain authoritative.

This file must be updated whenever a dependency is added or removed, a version
constraint changes, a bundled wheel is rebuilt, a bundled asset is added or
replaced, or a `.task` model is replaced or retrained. The repository guidelines
in [`AGENTS.md`](AGENTS.md) apply to this branch as well.
