> **Dokument planistyczny — 2026-09-09.**
> Wszystkie liczby to szacunki na ten dzień, nie zobowiązania. Oznaczenia `[W]` (zweryfikowane)
> i `[Z]` (założenie) zachowane w całym tekście.
>
> Kosztorys towarzyszący temu planowi: [`szacunek.md`](szacunek.md).
>
> Dokument jest **wyłącznie po polsku, na życzenie autora repozytorium**. Zasada równoważności
> EN/PL z `AGENTS.md` dotyczy `README.md` / `README.pl.md` oraz obu plików
> `docs/TECHNICAL_DOCUMENTATION*.md` i nie obejmuje tych dwóch dokumentów planistycznych.

# Plan portu AI Sign Language Translator na C++ / Qt (Windows x64)

Dokument roboczy. **Nie jest częścią repozytorium** — leży w scratchpadzie sesji.
Powstał na bazie analizy gałęzi `fix/camera-worker-fps-split` (commit `3578836`).

Legenda znaczników:
- `[W]` — fakt zweryfikowany (uruchomiony lokalnie albo potwierdzony URL-em przez podagenta),
- `[Z]` — założenie / oszacowanie autora planu.

---

## 1. Cel i zakres

Odtworzyć w C++ **całe zachowanie zewnętrzne** aplikacji, bez Pythona w środowisku
uruchomieniowym. Trening modeli zostaje w Colabie (`notebooks/`) — zgodnie z `AGENTS.md`
to jest poza zakresem portu.

Zakres zachowań do odtworzenia 1:1 (wyprowadzony z kodu, nie z README):

| Obszar | Konkret |
|---|---|
| GUI | `src/gui.ui` — 57 widgetów `[W]`, w tym 5 `QPushButton`, 8 `QSpinBox`, 2 `QComboBox`, 2 `QCheckBox`, 1 `QSlider`, 3 `QProgressBar`, 18 `QLabel` |
| Motyw | qdarkstyle — arkusz `darkstyle.qss` (54 KB) + `darkstyle.qrc` + 208 plików `rc/` `[W]` |
| Model | wybór pliku `.task` przez `QFileDialog`, filtr `Files .task (*.task)`, katalog startowy `models/`, rollback ścieżki przy błędzie ładowania (`main_app.py:open_file_dialog`) |
| Kamera | enumeracja urządzeń (`QMediaDevices::videoInputs`), lista backendów z `cv2.videoio_registry.getCameraBackends()` + słownik 37 nazw, domyślnie DirectShow na Windows, szerokość/wysokość ze spinboxów |
| Property page | natywne okno sterownika (`CAP_PROP_SETTINGS`), z pauzą wątku przechwytywania na czas modala |
| TTS | głos / tempo / głośność, auto-wypowiadanie po `checkBox_speak`, kolejka z coalescingiem (tylko najnowszy tekst), praca na własnym wątku |
| Landmarki | 21 punktów, 3 style punktów (dłoń/palce/opuszki) i 2 style połączeń, kolory i grubości z `src/custom_landmarks.py` |
| Metryki | 3 rozdzielone liczby: pipeline FPS, camera FPS, inference ms + licznik `dropped_frames` w tooltipie |
| Wygładzanie | okno przesuwne (`horizontalSlider_range`), głosowanie większościowe + średnia score dla zwycięskiego znaku |
| Pakowanie | jeden plik `.exe` + wariant katalogowy, ZIP, `BUILD_INFO.txt`, `START_HERE.md` (EN+PL), `RUN.bat`/`RUN.ps1` |
| Testy | bez kamery, bez dźwięku, bez sieci (`AGENTS.md`) |
| Dokumentacja | README EN+PL (po 253 linie) i TECHNICAL_DOCUMENTATION EN+PL (338/340 linii) — równoważne co do zakresu i faktów |

---

## 2. Stack docelowy

Wszystkie wersje zweryfikowane 2026‑09‑09.

| Warstwa | Wybór | Wersja | Prebuilt Win x64 | Uzasadnienie |
|---|---|---|---|---|
| Język | C++20 | — | — | `std::jthread`, `std::stop_token`, `<chrono>`, `std::span`. Wymuszone też przez LiteRT/ORT |
| GUI | Qt 6 Widgets | **6.11.2** (2026‑08‑18) `[W]`; LTS open source = 6.8.3 | **tak** (Qt Online Installer, build MSVC 2022) `[W]` | lokalnie działa Qt 6.11.1; `qt_add_ui()` od Qt 6.8. Qt Widgets **nie jest deprecated** (status „Done") `[W]` |
| Motyw | qdarkstyle QSS + `rcc` | — | — | `darkstyle.qss` 54 KB + `.qrc` + 208 plików `rc/` `[W]` — kopiujemy do repo C++ |
| Kamera | OpenCV `VideoCapture` + `CAP_DSHOW` | **OpenCV 4.14.0** (2026‑07‑19) `[W]` | **tak** — ale oficjalna paczka jest zbudowana **VS 2019 (vc16)**, brak `vc17` `[W]` (ABI zgodne z v143) | jedyna droga do `CAP_PROP_SETTINGS`; w gałęzi 5.x nadal `CAP_DSHOW = 700`, `CAP_PROP_SETTINGS = 37`, bez deprecacji `[W]` |
| — dlaczego nie OpenCV 5.0.0 | | 5.0.0 (2026‑06‑06) `[W]` | | 5.x zmienia `VideoCapture::get()` na `-1` dla nieobsługiwanych property, zmienia semantykę opakowania `std::vector`, przenosi `ml`/HOG/kaskady do contrib i **zmienia piksele z `resize`/`putText`** (rebaseline testów obrazkowych) `[W]`. Brak portu 5.x w vcpkg i Conan `[W]` |
| — dlaczego nie Qt Multimedia | | | | domyślny backend na Windows to **FFmpeg**, a natywny WMF jest **deprecated od Qt 6.10**; capture idzie przez Media Foundation (`qwindowscamera.cpp`, `IMFSourceReader`) `[W]`. **Brak jakiegokolwiek API do property page sterownika** — w MSMF `CAP_PROP_SETTINGS` to jawny no‑op `[W]` |
| Rysowanie landmarków | OpenCV `cv::circle` / `cv::line` | j.w. | j.w. | 1:1 z `mp_drawing.draw_landmarks` |
| Inferencja | **LiteRT** (podst.) / MediaPipe C API (fallback) | LiteRT **2.2.0** (2026‑08‑13) `[W]` | **tak, częściowo** — oficjalny `libLiteRt.dll` dla `windows_x86_64`, ale **bez import library**; wrapper C++ kompilujesz sam (Google podaje `clang`) `[W]` | patrz §3 |
| Inferencja — awaryjnie | ONNX Runtime | **1.29.0** (2026‑08‑12) `[W]` | **tak, w pełni** — `onnxruntime-win-x64-1.29.0.zip`: `include/*.h` + `lib/onnxruntime.{dll,lib,pdb}` `[W]` | jedyna w 100 % gotowa paczka; port vcpkg `onnxruntime` 1.23.2#1 `[W]` |
| TTS | `QTextToSpeech` | Qt 6.11 `[W]` | tak (część Qt) | lokalnie: `availableEngines() == ['sapi','mock','winrt']`, `State.Ready`, `setRate/setVolume/setPitch`, `availableVoices()` `[W]`. Domyślny backend na Windows to **`winrt`** (`Windows.Media.SpeechSynthesis`, wszystkie zainstalowane głosy), `sapi` = SAPI 5.3, mniej głosów `[W]`. **Silnik `mock`** → testy headless |
| TTS fallback | SAPI5 `ISpVoice` | — | — | `Speak(..., SPF_ASYNC\|SPF_PURGEBEFORESPEAK, ...)`, `SetRate(-10..10)`, `SetVolume(0..100)` `[W]` |
| Kompilator | MSVC **v143** (VS 2022 17.14 LTSC, `_MSC_VER` 1944, wsparcie do 2032‑01‑13) `[W]` | ewent. VS 2026 18.10 / toolset **14.50 „Long‑term"** (nie 14.51 — EOL luty 2027) `[W]` | — | 17.14 LTSC to najbezpieczniejszy wybór na kilka lat |
| Build | CMake + Ninja | **CMake 4.4.3** (2026‑08‑25) `[W]`, Ninja 1.13.2 | tak | `qt_generate_deploy_app_script()` od Qt 6.3 |
| Zależności | **vcpkg** manifest + `builtin-baseline` | rolling, snapshot **2026.07.29** `[W]` | — | bez `builtin-baseline` vcpkg wpada w Classic mode i **ignoruje wersjonowanie** `[W]`. Alternatywa: Conan **2.32.0** (2026‑08‑31) `[W]`, jedyny z OpenCV 4.14.0 `[W]` |
| Testy | **Qt Test** (+ Catch2 do czystej logiki) | Catch2 **3.16.0** (2026‑08‑25) `[W]`, GoogleTest **1.18.0** (2026‑08‑10) `[W]` | — | `QSignalSpy` i symulacja zdarzeń to **wyłączność Qt Test** — bez tego nie przetestujesz sygnałów. Rejestracja obu przez `add_test()`/CTest. `offscreen` działa na Windows `[W]` |
| Pakowanie | `windeployqt` + ZIP + **Inno Setup 7.1.0** (2026‑08‑12) `[W]` | NSIS 3.12, WiX 7.0.0 jako alternatywy `[W]` | — | Qt IFW od 4.10 **nie jest już dostępny samodzielnie** (tylko przez Qt Online Installer) — utrudnia CI `[W]` |
| Licencja Qt | LGPLv3, **linkowanie dynamiczne** | — | — | dynamiczne linkowanie = prosta zgodność; statyczne obliguje do udostępniania plików obiektowych aplikacji przy każdym wydaniu `[W]` |
| CI | GitHub Actions | **przypiąć `windows-2022`** `[W]` | — | `windows-latest` = Windows Server 2025 **z VS 2026** od czerwca 2026 `[W]`; `windows-2022` ma VS 17.14 + CMake 3.31.6, `windows-latest` ma CMake 4.4.2 `[W]`. Qt **nie jest preinstalowane** — `jurplel/install-qt-action` **v4.3.1** `[W]` (uwaga: opakowuje `aqtinstall`, bez wydania od ~15 miesięcy `[W]`) |

---

## 3. Backend inferencji — wybór ścieżki

### Rekomendacja: **B (LiteRT) jako główna, A (MediaPipe/Bazel) jako fallback**, z bramką w Fazie 0

Powód odwrócenia intuicji („przecież MediaPipe daje parytet za darmo"): **build MediaPipe stoi
na toolchainie, który wygasa**. `.bazelversion` = **7.7.0**, a **Bazel 7 kończy wsparcie
w grudniu 2026** `[W]`; repo ma **hybrydę WORKSPACE + bzlmod** (32 KB `WORKSPACE` obok
`MODULE.bazel`), a Bazel 9 **usunął obsługę WORKSPACE całkowicie** — więc ten build
**nie zbuduje się na Bazelu 9/10** `[W]`. Do tego kompilacja pod MSVC ma otwarty defekt
(#6237) bez zmergowanej poprawki. Wybierając wariant A, bierzemy na siebie utrzymanie
buildu, który upstream dopiero migruje.

Po drugiej stronie stanął nowy fakt: **LiteRT 2.2.0 ma oficjalny prebuilt `libLiteRt.dll`
dla `windows_x86_64`** `[W]`, XNNPACK domyślnie włączony na Windows `[W]`, a w macierzy
wsparcia **Windows = CPU, GPU (WebGPU/Direct3D 12), Intel NPU** `[W]`. To znaczy, że
LiteRT daje na tej maszynie **ścieżkę GPU (GTX 1650 i UHD 630 obsługują D3D12), której
MediaPipe na Windows nie ma w ogóle** — „Desktop GPU is currently not supported",
issue #5126 zamknięte jako won't‑fix `[W]`.

**Wariant A (fallback): MediaPipe Tasks **C API** zbudowane Bazelem do `libmediapipe.dll`.**

Argumenty za:

- `mediapipe/tasks/c/vision/gesture_recognizer/gesture_recognizer.h` istnieje i ma
  `MpGestureRecognizerCreate/RecognizeImage/RecognizeForVideo/RecognizeAsync/Close`,
  `result_callback` dla `MP_RUNNING_MODE_LIVE_STREAM`, oraz `custom_gestures_classifier_options`
  — czyli **dokładnie ten model użycia, który ma dziś aplikacja** `[W]`.
- `mediapipe/tasks/c/BUILD` (obecny **także w tagu v1.0.0**) ma już `genrule(name="mediapipe_windows", outs=["libmediapipe.dll"])`
  i `alias(name="libmediapipe")` z `select()` na `@platforms//os:windows`; GNU-owe `linkopts`
  są schowane w `select({"@platforms//os:linux": ...})`. W deps jest `gesture_recognizer_c_lib`.
  **Nie trzeba pisać własnego targetu DLL — koszt tej pozycji = 0** `[W]`.
- Nagłówek definiuje `MP_EXPORT` jako `__declspec(dllexport)` pod `_MSC_VER` `[W]`.
- Zysk nie do przecenienia: **parytet numeryczny za darmo**. Te same `.task`, ten sam graf,
  ta sama implementacja — nie ma czego walidować.

Argumenty przeciw:

- Google **nie publikuje żadnych prebuiltów C++ dla Windows** — brak assetów w releasach,
  **brak portu vcpkg, brak recipe Conan, brak oficjalnego NuGeta** `[W]`. Windows jest
  oficjalnie „experimental" `[W]`.
- Kompilacja pod MSVC 2022 **nie jest potwierdzona jako działająca** na linii v1.0.x:
  issue #6237 (`C3547`, MSVC) otwarte, a jedyna znana poprawka — PR #6238
  (`/Zc:preprocessor`, Python 3.12, `constinit`) — **niezmergowana**, od community, od 2026‑02‑17 `[W]`.
- `.bazelversion` **7.7.0**, hybryda WORKSPACE + bzlmod; **Bazel 7 EOL grudzień 2026**,
  Bazel 9 usunął WORKSPACE → **ślepy zaułek toolchainowy** `[W]`.
- Zależności przypięte przez `archive_override`: protobuf **6.31.1**, abseil **20260526.0**
  (a na innym punkcie linii — nieotagowany SHA) `[W]`; **nie da się ich pogodzić z vcpkg/system** bez patcha.
- Windows = **wyłącznie CPU** `[W]`.
- v1.0.0 wprowadza **zmianę łamiącą dla konsumentów C**: „Enforce namespacing conventions
  for MediaPipe Tasks C and Python APIs" `[W]` → wersję trzeba przypiąć na sztywno.
- `mediapipe_source` ma `linkstatic = True` i wciąga **wszystkie** taski → duży DLL i ciężki link.
  Przy 16 GB RAM `[W]` realne ryzyko OOM; mitygacja: lokalny patch przycinający `deps`
  do `gesture_recognizer_c_lib`.
- Wymaga na Windows **OpenCV 3.4.10** w `C:\opencv\build` `[W]` — czyli w procesie mielibyśmy
  dwa OpenCV (3.4.10 wewnątrz DLL-a, 4.14 w aplikacji). Do rozstrzygnięcia.

**Wariant B (rekomendowany): własna implementacja grafu na LiteRT.**

- Zachowujemy **te same pliki `.tflite`** wyjęte z `.task` → parytet jest osiągalny, bo wagi są
  identyczne; odtwarzamy tylko pre/post‑processing. **Zero konwersji modeli.**
- Oficjalny `libLiteRt.dll` dla `windows_x86_64` `[W]`, XNNPACK domyślnie ON na Windows `[W]`.
- API `Environment` / `CompiledModel` / `TensorBuffer`, automatyczny dobór akceleratora `[W]`.
- Otwiera **ścieżkę GPU na Windows** (WebGPU/D3D12) — jedyną dostępną na tym sprzęcie.
- Koszty i zastrzeżenia: prebuilt to **tylko DLL, bez import library**; wrapper C++ trzeba
  skompilować samemu z `litert_cc_sdk.zip`, a Google pisze, że **„LiteRT needs `clang` to build"**
  — brak wskazówek dla MSVC; instrukcje CMake w repo LiteRT **pomijają Windows** `[W]`.
  **Brak portu vcpkg `tensorflow-lite`** `[W]`. ABI stabilizowane dopiero od 2.2.0 `[W]`.
- Największy koszt: ~800–1500 linii logiki grafu + harness parytetu (§6.2, §6.3).

**Wariant C (rezerwa i ścieżka do GPU): ONNX Runtime.**

- **Jedyna w pełni gotowa paczka**: `onnxruntime-win-x64-1.29.0.zip` z nagłówkami, `.lib`, `.dll`, `.pdb` `[W]`.
- DirectML EP obsługuje **oba** GPU tej maszyny: NVIDIA Kepler+ → GTX 1650 ✓, Intel Haswell+ → UHD 630 ✓ `[W]`.
- Wymaga konwersji TFLite → ONNX (`tf2onnx` **1.17.0**, pierwsze wydanie od 26 miesięcy,
  z notką „looking for a new maintainer" `[W]`) **plus** tej samej reimplementacji grafu co B.
- **Skrót, który realnie obniża koszt**: `opencv/opencv_zoo` ma gotowe
  `palm_detection_mediapipe_2023feb.onnx` **wraz z demem C++ i CMakeLists** (Apache‑2.0) oraz
  `handpose_estimation_mediapipe_2023feb.onnx` `[W]` — czyli działający, czytelny wzorzec
  dekodowania kotwic i ROI w C++. Wagi to migawka z lutego 2023, więc **nie dają parytetu
  z naszym `.task`**, ale jako referencja implementacji są bardzo wartościowe.
- Ostrzeżenie strategiczne: **DirectML jest w trybie utrzymaniowym** (NuGet DirectML stoi na
  1.24.4, `Microsoft.AI.DirectML` zamrożony na 1.15.4), a jego następca Windows ML
  **wyklucza ten sprzęt** (TensorRT‑RTX wymaga RTX 30xx+, OpenVINO GPU wymaga Intela 12. gen+) `[W]`.
  Alternatywa NVIDIA‑only: CUDA EP — buildy ORT 1.29.0 zawierają compute capability 7.5 (Turing) `[W]`.

### Bramka decyzyjna (koniec Fazy 0) — oba spike'y równolegle, timebox 5 dni każdy

| Wynik | Decyzja |
|---|---|
| Spike B: `libLiteRt.dll` ładuje się z MSVC, detektor daje bounding box zgodny z Pythonem `1e-3` | **B** — kontynuuj |
| Spike B pada (clang‑only wrapper nie do zbudowania MSVC), spike A zielony | **A** — z pełną świadomością długu toolchainowego |
| Oba padają | **C** (ORT, konwersja modeli) albo rekomendacja rezygnacji z portu |
| Oba zielone | **B** — bo daje GPU i nie stoi na Bazelu 7 |

---

## 4. Układ repozytorium (po porcie)

```
AI_sign_language_translator/
├─ CMakeLists.txt                 # top-level, C++20, Qt6, opcje backendu
├─ CMakePresets.json              # msvc-x64-release / -debug, ścieżki vcpkg
├─ vcpkg.json                     # manifest zależności
├─ AGENTS.md / CLAUDE.md          # zaktualizowane pod C++ (build/test commands)
├─ README.md / README.pl.md       # przepisane sekcje Requirements/Installation/Tests/Building
├─ LICENSE / LICENSE-docs         # BEZ ZMIAN — podział licencji zostaje
├─ SECURITY.md                    # bez zmian
├─ models/                        # BEZ ZMIAN: 3 × .task + SHA256SUMS.txt
├─ notebooks/                     # BEZ ZMIAN (Colab, Python — trening zostaje)
├─ docs/                          # BEZ ZMIAN: obrazy, PDF pracy, .ods
│  ├─ TECHNICAL_DOCUMENTATION.md      # przepisane sekcje 2,3,4,7
│  └─ TECHNICAL_DOCUMENTATION.pl.md   # j.w., równoważnie
├─ src/
│  ├─ gui.ui                      # BEZ ZMIAN — źródło prawdy interfejsu
│  ├─ assets/                     # BEZ ZMIAN (ans.ico, at.png, ki_LOGO_w.png)
│  ├─ theme/darkstyle.qss + darkstyle.qrc + rc/   # skopiowane z qdarkstyle
│  ├─ main.cpp
│  ├─ MainWindow.{h,cpp}          # ← main_app.py
│  ├─ Camera.{h,cpp}              # ← camera.py: CameraApp
│  ├─ CaptureWorker.{h,cpp}       # ← camera.py: CameraWorker + LatestFrameBuffer
│  ├─ LatestFrameBuffer.{h,cpp}
│  ├─ GestureRecognizer.{h,cpp}   # ← recognizer.py
│  ├─ IInferenceBackend.h         # interfejs; impl. MediaPipeBackend albo LiteRtBackend
│  ├─ backends/MediaPipeBackend.{h,cpp}   # wariant A
│  ├─ backends/LiteRtBackend/…            # wariant B (graf)
│  ├─ LandmarkDrawing.{h,cpp}     # ← custom_landmarks.py
│  ├─ Speaker.{h,cpp}             # ← speaker.py
│  └─ Metrics.h                   # ← PipelineMetrics
├─ tests/
│  ├─ CMakeLists.txt
│  ├─ test_latest_frame_buffer.cpp
│  ├─ test_capture_worker.cpp     # FakeCamera / BlockingCamera / ExplodingCamera
│  ├─ test_recognizer.cpp         # FakeBackend + Clock
│  ├─ test_main_window.cpp        # QTest, offscreen
│  ├─ test_speaker.cpp            # backend `mock` QTextToSpeech
│  ├─ test_models.cpp             # SHA256 modeli
│  ├─ test_security_hygiene.cpp   # brak kaggle.json itd.
│  └─ golden/                     # pliki referencyjne parytetu (wariant B)
├─ third_party/
│  └─ mediapipe/                  # wariant A: patche do MediaPipe + skrypt builda + SHA256
├─ scripts/
│  ├─ build_mediapipe_windows.ps1 # wariant A
│  ├─ build_windows_release.ps1   # zastępuje PyInstaller: cmake --build + windeployqt + ZIP + Inno
│  └─ dump_python_goldens.py      # jedyny pozostały Python — narzędzie deweloperskie (wariant B)
└─ .github/workflows/tests.yml    # MSVC + Qt + ctest
```

Co przechodzi **bez jednej zmiany**: `models/*.task` + `models/SHA256SUMS.txt`, `src/gui.ui`,
`src/assets/`, `docs/images/`, `docs/*.pdf/.ods`, `LICENSE`, `LICENSE-docs`, `SECURITY.md`,
`notebooks/`. Znika całe `third_party/protobuf/` i `third_party/wheels/` (~2 wheele + 3 patche
+ `build_patched_protobuf.ps1`, 178 linii) — problem łatanego protobufa dotyczy wyłącznie
Pythona; strona C++ MediaPipe buduje protobuf 6.31.1 ze źródeł `[W]`. **To jest realna oszczędność
utrzymaniowa**, ale w zamian przychodzi Bzlmod + nieotagowany absl.

---

## 5. Projekt modułów

Granice modułów zostają zgodnie z `AGENTS.md` („Keep camera capture, recognition, TTS and
main-window coordination in their existing modules").

### 5.1 `LatestFrameBuffer` — ← `camera.py:44-88`

```cpp
class LatestFrameBuffer {
public:
    void put(std::int64_t timestampNs, cv::Mat frame);   // nadpisuje, liczy drop
    std::optional<std::pair<std::int64_t, cv::Mat>> take();
    void clear();                                        // bez liczenia dropa
    std::uint64_t droppedFrames() const;
private:
    mutable std::mutex m_mutex;
    std::optional<std::pair<std::int64_t, cv::Mat>> m_item;
    std::uint64_t m_dropped = 0;
};
```

Semantyka „latest wins" 1:1. `cv::Mat` jest refcountowany — `put` musi wykonać `.clone()`
albo dostawać bufor na wyłączność, inaczej wątek przechwytywania nadpisze piksele czytane
przez konsumenta. **To jest pułapka, której w NumPy nie było w tej postaci** (tam
`cv2.cvtColor` zawsze alokował nowy bufor).

### 5.2 `Camera` — ← `camera.py:CameraApp`

```cpp
class Camera {
public:
    bool open(int index, int backend = cv::CAP_DSHOW);
    void configure(int width, int height, double fps = 30.0);
    void settings();                 // cap.set(cv::CAP_PROP_SETTINGS, 1)
    bool isClosed() const;
    void destroy();
    std::pair<std::int64_t, cv::Mat> read();   // (monotonic ns, RGB) lub (ns, empty)
};
```

`read()` zwraca **RGB** (`cv::cvtColor(BGR2RGB)`), znacznik z `std::chrono::steady_clock` w ns.

### 5.3 `CaptureWorker` — ← `camera.py:CameraWorker`

`QThread` (nie `std::jthread` — potrzebny `Signal`/`QueuedConnection` do GUI).

```cpp
class CaptureWorker : public QThread {
    Q_OBJECT
signals:
    void frameReady();
public:
    bool start();                                  // idempotentny, obsługuje restart po timeoucie stop()
    bool stop(std::chrono::milliseconds timeout = 2000ms);
    double cameraFps() const;                      // średnia z okna 30 interwałów
    std::uint64_t droppedFrames() const;
protected:
    void run() override;                           // pętla, wyjątek NIE ubija wątku
};
```

Zachowania do przeniesienia dosłownie:
- `run()` łapie **każdy** wyjątek, loguje i kontynuuje po `idleDelay` 50 ms (`camera.py:170-186`);
- `start()` na już biegnącym wątku z ustawionym `stop_event` czeka `CAPTURE_STOP_TIMEOUT_S` = 2 s
  i dopiero wtedy restartuje; jeśli się nie doczeka — zwraca `false` (`camera.py:129-153`);
- **stranded worker**: gdy `stop()` nie doczeka się końca `read()`, obiekt jest celowo
  „porzucany" do globalnej listy i kamera **zostaje otwarta**, bo zwolnienie `VideoCapture`,
  w którym sterownik wisi, zabija proces bez traceback (`camera.py:16-30`, `recognizer.py:close`).
  W C++ odpowiednik: `std::vector<std::unique_ptr<CaptureWorker>> g_stranded` + **brak** `destroy()`
  na kamerze. To nie jest wyciek do naprawienia — to świadoma decyzja projektowa i musi
  przejść razem z komentarzem.

### 5.4 `GestureRecognizer` — ← `recognizer.py`

```cpp
class GestureRecognizer : public QObject {
    Q_OBJECT
signals:
    void resultReady(QImage frame, QStringList text, QList<double> scores, PipelineMetrics m);
public:
    struct Config { QString modelPath; int numHands; double minHandDetection,
                    minHandPresence, minTracking, scoreThreshold; };
    bool createRecognizer();       // false = model nie do wczytania → QMessageBox w MainWindow
    bool startCapture();
    bool stopCapture(std::chrono::milliseconds timeout = 2000ms);
    PipelineMetrics metrics() const;
    bool close(std::chrono::milliseconds timeout = 2000ms);
};
```

Model wątkowy (bez zmian względem Pythona):

| Wątek | Robi |
|---|---|
| GUI | `MainWindow`, aktualizacja widgetów, `QPixmap` |
| Capture (`CaptureWorker`) | `Camera::read()` → `LatestFrameBuffer::put` → `frameReady` |
| Inference (backend) | callback `handleResult` — rysowanie landmarków, `QImage`, pomiar latencji |

Reguły do przeniesienia dosłownie (to są **wszystkie** nietrywialne lekcje z gałęzi Pythona):

1. **Gating jednej inferencji naraz.** `m_inferencePending` — klatki zebrane w trakcie
   inferencji są **porzucane**, nie kolejkowane (`recognizer.py:recognize_frame`).
2. **Watchdog.** Deadline = `max(1 s, 10 × średnia latencja)`; po jego przekroczeniu
   zawieszona inferencja jest porzucana, bo MediaPipe potrafi zgubić pakiet we flow limiterze
   i nigdy nie wywołać callbacku — bez tego aplikacja zamarza na ostatnim wyniku
   (`recognizer.py:inference_deadline_s`, `inference_expired`).
3. **Ściśle rosnące znaczniki ms.** `next_timestamp_ms`: `ts_ms = ts_ns / 1e6`; jeśli
   `<= last`, to `last + 1`. **Nie pomijać klatki** — z buforem latest-wins ta klatka jest
   najświeższą, jaką mamy (`recognizer.py:next_timestamp_ms`).
4. **Nic z Qt GUI na wątku inferencji.** `handleResult` tworzy odczepiony `QImage`
   (w Pythonie `image.copy()`; w C++ `QImage(...).copy()` albo konstrukcja z własnego bufora),
   emituje sygnał z `QueuedConnection`; `QPixmap` powstaje dopiero w `MainWindow`.
5. **Metryki rozdzielone na trzy.** `pipeline_fps` (co 5 wyników: `5/Δt`), `camera_fps`
   (średnia krocząca z 30 interwałów w workerze), `inference_ms` (średnia krocząca z 30 próbek,
   od zgłoszenia do wejścia w callback) + kumulatywny `dropped_frames`.
6. **Kolejność zamykania.** `close()`: `m_closing = true` → `stopCapture()` → rozłączenie
   `frameReady` → (jeśli nie zatrzymany: strand) → zamknięcie backendu.

### 5.5 `LandmarkDrawing` — ← `custom_landmarks.py`

Style są w kodzie stałe i muszą się zgadzać co do piksela:

| Grupa | Punkty | Kolor RGB | Promień | Grubość |
|---|---|---|---|---|
| Dłoń (`WRIST, THUMB_CMC, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP`) | 6 | `(8,180,8)` | 5 | `-1` (wypełnienie) |
| Palce (PIP/DIP/THUMB_MCP/THUMB_IP) | 10 | `(50,250,50)` | 5 | `-1` |
| Opuszki (5 × TIP) | 5 | `(255,0,0)` | 7 | `-1` |
| Połączenia dłoni | `HAND_PALM_CONNECTIONS` | `(0,0,255)` | — | 2 |
| Połączenia palców | 5 grup | `(28,140,255)` | — | 3 |

Uwaga: MediaPipe rysuje w OpenCV, gdzie kolejność kanałów to BGR, ale klatka jest w RGB —
efektywne kolory na ekranie są takie, jakie widać dziś. **Przenosić wartości liczbowe,
nie „intencję kolorystyczną"**, inaczej UI zmieni wygląd.

Tablicę połączeń `HAND_CONNECTIONS` (21 krawędzi) trzeba wpisać na stałe — w C++ nie ma
`mediapipe.python.solutions.hands_connections`.

### 5.6 `Speaker` — ← `speaker.py`

```cpp
class Speaker : public QObject {
    Q_OBJECT
public slots:
    void speak(const QString& text);   // pomija puste; coalescing: liczy się najnowszy
    void setRate(int wpmLike);         // mapowanie z 0..N spinboxa
    void setVolume(double v01);
public:
    bool stop();                       // true = wątek nie wyszedł w limicie
};
```

Rekomendacja: **`QTextToSpeech` z backendem `sapi`**. Znika cała warstwa COM
(`CoInitialize`, apartamenty, `pythoncom`), znika obsługa `finished-utterance` (jest
`QTextToSpeech::stateChanged` / `Ready`), znika problem pyttsx3 2.99 (nie ma pyttsx3).
Coalescing i kolejkowanie zostają — `QTextToSpeech::stop()` + nowy `say()`.

Mapowanie ustawień: dziś `spinBox_ttsRate` (pyttsx3 „rate" w słowach/min, domyślnie 150)
i `spinBox_volume` (0–100 → 0.0–1.0). `QTextToSpeech::setRate` przyjmuje **−1.0…1.0**,
`setVolume` **0.0…1.0**. **Trzeba zdefiniować mapowanie i opisać je w dokumentacji** —
to jest widoczna dla użytkownika zmiana semantyki suwaka. `[Z]`

Ryzyko do sprawdzenia w Fazie 0: na tej maszynie `QTextToSpeech('sapi').availableVoices()`
zwrócił **tylko `Microsoft Paulina Desktop`** `[W]`, podczas gdy `speaker.py` celuje w
`TTS_MS_EN-US_ZIRA_11.0`. Trzeba sprawdzić, czy backend `sapi` widzi ten sam zbiór głosów
co pyttsx3; jeśli nie — fallback na `ISpVoice`.

### 5.7 `MainWindow` — ← `main_app.py`

Dziedziczy po `QMainWindow` i po wygenerowanym `Ui_MainWindow`
(`ui_MainWindow.h` — **774 linie generowane przez `uic`, zweryfikowane** `[W]`).

Do przeniesienia: słownik 37 nazw backendów OpenCV, `populate_cameras` /
`populate_camera_drivers` (z domyślnym `CAP_DSHOW` na Windows), `open_file_dialog`
z rollbackiem, `pushbutton_camera_settings_click` z pauzą przechwytywania na czas modala,
`calculate_common_sign_and_average` (głosowanie + średnia), `format_rate_details`
(`"camera 28.4 FPS | inference 17.3 ms"`, `--` gdy 0), `report_capture_stopped`
(`"camera not running"`), `closeEvent` w kolejności: rozłącz sygnał → `recognizer.close()`
→ `camera.destroy()` **tylko gdy capture faktycznie stanął** → `speaker.stop()`.

---

## 6. Backend inferencji — szczegóły

### 6.1 Wariant A — recepta builda MediaPipe na Windows

Wymagania wstępne (na tej maszynie **nie ma nic z tego** — `cmake`, `bazel`, `cl`, `vcpkg`,
`C:\Qt`, `C:\opencv` wszystkie nieobecne `[W]`; wolne 561 GB, 16 GB RAM, i7‑9750H 6C/12T `[W]`):

1. Visual Studio 2022 Build Tools (C++ workload) + Windows SDK.
2. MSYS2, `C:\msys64\usr\bin` w `PATH`.
3. Python (3.12 wg PR #6238) — **tylko jako narzędzie builda**, nie w runtime.
4. Bazelisk / Bazel (wersja wg `.bazelversion` w tagu v1.0.0).
5. OpenCV **3.4.10** (`opencv-3.4.10-vc14_vc15.exe`) → `C:\opencv\build` `[W]`.
6. Zmienne: `BAZEL_VS`, `BAZEL_VC`, `BAZEL_VC_FULL_VERSION`, `BAZEL_WINSDK_FULL_VERSION` `[W]`.

Build:

```powershell
git clone https://github.com/google-ai-edge/mediapipe --branch v1.0.0
cd mediapipe
git fetch origin pull/6238/head:pr6238 ; git cherry-pick <sha z pr6238>   # obejście #6237
bazel build -c opt --define MEDIAPIPE_DISABLE_GPU=1 `
    --action_env PYTHON_BIN_PATH="C:/Python312/python.exe" `
    //mediapipe/tasks/c:libmediapipe
```

Artefakt: `bazel-bin/mediapipe/tasks/c/libmediapipe.dll`. Nagłówki bierzemy wprost z drzewa
źródeł (`mediapipe/tasks/c/vision/gesture_recognizer/gesture_recognizer.h` + `core/*.h`).

Konsumpcja z CMake — DLL i nagłówki wersjonujemy w repo jako artefakt binarny z sumą SHA-256
(analogicznie do dzisiejszego `third_party/protobuf/SHA256SUMS.txt`), bo odtworzenie builda
zajmuje godziny:

```cmake
add_library(mediapipe_tasks SHARED IMPORTED)
set_target_properties(mediapipe_tasks PROPERTIES
    IMPORTED_LOCATION       "${MP_PREBUILT}/bin/libmediapipe.dll"
    IMPORTED_IMPLIB         "${MP_PREBUILT}/lib/libmediapipe.lib"
    INTERFACE_INCLUDE_DIRECTORIES "${MP_PREBUILT}/include")
```

**Uwaga**: `genrule` produkuje tylko `.dll`; import library `.lib` trzeba wyciągnąć z
`bazel-bin` albo wygenerować z `.def` (`dumpbin /exports` + `lib /def:`). To jest znany,
mały, ale nieoczywisty krok. `[Z]`

Nagłówek `gesture_recognizer.h` używa domyślnych inicjalizatorów składowych
(`int num_hands = 1;`) — **nie jest to poprawny C, tylko C++** `[W]`. Dla projektu Qt C++
to nie problem; nie da się z tego zrobić czystego C-shimu.

### 6.2 Wariant B — reimplementacja grafu na LiteRT

Runtime: LiteRT 2.2.0, API `Environment` / `CompiledModel` / `TensorBuffer`; `CompiledModel`
sam dobiera akcelerator, **nie ma jawnych delegatów** `[W]`. Stare API `Interpreter` istnieje
tylko dla wstecznej zgodności `[W]`. XNNPACK jest na Windows domyślnie włączony `[W]`.
Pięć modeli ładujemy jako pięć niezależnych `CompiledModel` — MediaPipe robi dokładnie to samo,
tylko opakowane w kalkulatory grafu.

Etapy do napisania (parametry zweryfikowane, źródło podane przy każdym):

| # | Etap | Parametry |
|---|---|---|
| 1 | Preprocessing detektora | letterbox/resize do **192×192**, RGB float32, wejście `input_1 [1,192,192,3]` `[W]` (odczytane z `models/gesture_recognizer_asl_0.task`) |
| 2 | Kotwice SSD | `num_layers=4, min_scale=0.1484375, max_scale=0.75, input 192×192, anchor_offset_x/y=0.5, strides=[8,16,16,16], aspect_ratios=[1.0], fixed_anchor_size=true` → **2016 kotwic** `[W]` |
| 3 | Dekodowanie detekcji | `num_classes=1, num_boxes=2016, num_coords=18, keypoint_coord_offset=4, num_keypoints=7, num_values_per_keypoint=2, sigmoid_score=true, score_clipping_thresh=100.0, reverse_output_order=true, x/y/w/h_scale=192.0, min_score_thresh=0.5` `[W]`; wyjścia `Identity [1,2016,18]`, `Identity_1 [1,2016,1]` `[W]` |
| 4 | NMS | `min_suppression_threshold=0.3`, tryb WEIGHTED/IOU `[W]` |
| 5 | ROI z keypointów | `rotation_vector_start_keypoint_index=0, end=2, target_angle_degrees=90` `[W]` |
| 6 | Transformacja prostokąta | `scale_x=2.6, scale_y=2.6, shift_y=-0.5, square_long=true` `[W]` |
| 7 | Wycinek afiniczny | obrót + skala do **224×224**, wejście `input_1 [1,224,224,3]` `[W]` |
| 8 | Model landmarków | wyjścia: `Identity [1,63]` (21×3 znormalizowane), `Identity_1 [1,1]` (handedness), `Identity_2 [1,1]` (presence), `Identity_3 [1,63]` (world) `[W]`; etykiety `handedness.txt` = `Left, Right` `[W]` |
| 9 | Odrzutowanie landmarków | odwrotność transformacji z kroku 7 do współrzędnych klatki |
| 10 | Maszyna stanów detect/track | pomijaj detektor, dopóki `presence ≥ min_hand_presence_confidence`; ROI kolejnej klatki z landmarków (`hand_landmark_landmarks_to_roi.pbtxt`) |
| 11 | Gesture embedder | wejścia `hand [1,21,3]`, `handedness [1,1]`, `world_hand [1,21,3]` → `Identity [1,128]` `[W]` |
| 12 | Klasyfikator custom | `[1,128] → [1,25]` `[W]`; etykiety z `labels.txt` w metadanych: `none, A, B, C, D, E, F, G, H, I, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y` `[W]` |
| 13 | Progi | `score_threshold` = `spinBox_treshold/100`, `max_results=1`, brak allow/deny list (jak w `recognizer.py:classifier_options`) |

Uwaga: `canned_gesture_classifier.tflite` (`[1,128] → [1,8]`) też jest w pakiecie `[W]` —
obecna aplikacja go **nie** używa (podaje `custom_gesture_classifier_options`), więc port
może go pominąć, ale trzeba to udokumentować.

### 6.3 Strategia testu parytetu (wariant B, i tak warto w A jako regresja)

1. **Nagranie zbioru klatek.** `scripts/record_frames.py` (albo tryb debug w aplikacji
   Pythonowej) zapisuje N ≈ 300 surowych klatek RGB 640×480 jako `.png` + manifest z indeksem.
   **Konieczny udział użytkownika** — w repo nie ma ani jednego obrazu, na którym MediaPipe
   wykrywa dłoń (sprawdzone: wszystkie 3 zdjęcia i wszystkie screeny UI dają `hands=0`) `[W]`.
2. **Zrzut złotych wyników.** `scripts/dump_python_goldens.py` uruchamia dzisiejszy
   `GestureRecognizer` w trybie `IMAGE` na tych klatkach i serializuje do JSON:
   `gestures[0].{category_name,score,index}`, `handedness[0].{category_name,score}`,
   `hand_landmarks[0][0..20].{x,y,z}`, `hand_world_landmarks[0][0..20].{x,y,z}`
   (pola potwierdzone w `GestureRecognizerResult` `[W]`).
3. **Test C++** (`tests/test_parity.cpp`) ładuje klatki + golden i asserty:
   - kategoria gestu: **identyczna** dla ≥ 99 % klatek,
   - score gestu: `|Δ| ≤ 1e-3`,
   - landmarki znormalizowane: `max |Δ| ≤ 2e-3` (≈ 1,3 px przy 640 px),
   - world landmarks: `max |Δ| ≤ 2e-3` m,
   - handedness: identyczna kategoria.
4. Golden jest artefaktem repo (`tests/golden/`) — kilkaset KB JSON + klatki w LFS albo
   zredukowany zbiór 30 klatek, żeby nie puchło repo. `[Z]`

**To jest najdroższy pojedynczy element wariantu B**: kroki 2–9 mają dziesiątki miejsc, gdzie
off-by-one w kolejności współrzędnych daje wynik „prawie dobry", a debugowanie polega na
porównywaniu tensorów pośrednich. Zaplanować zrzut tensorów pośrednich po każdym etapie,
nie tylko wyniku końcowego.

---

## 7. Plan fazowy

Oznaczenia: **dd** = dni robocze seniora C++/Qt `[Z]`; **tok** = tokeny agentów (in+out) `[Z]`.

### Faza 0 — spike backendu (BRAMKA, przed czymkolwiek innym)

| | |
|---|---|
| Cel | Udowodnić, że da się w C++ na Windows policzyć jedną klatkę zgodnie z Pythonem |
| 0a — wspólne | Toolchain od zera (na tej maszynie **nie ma nic**: brak `cl`, `cmake`, `bazel`, `ninja`, `vcpkg`, `conan`, `C:\Qt`, `C:\opencv` `[W]`): VS 2022 Build Tools 17.14, CMake 4.4.3, Ninja, vcpkg + `builtin-baseline`, Qt 6.11.2 (MSVC 2022), OpenCV 4.14.0. **Użytkownik nagrywa ~300 klatek RGB 640×480 z dłonią** (§6.3 krok 1) i uruchamia `dump_python_goldens.py` |
| 0b — **spike B (główny)** | Pobrać `libLiteRt.dll` (`https://storage.googleapis.com/litert/binaries/2.2.0/windows_x86_64/libLiteRt.dll`) + `litert_cc_sdk.zip`; zbudować wrapper C++ **pod MSVC** (Google mówi „clang" — to jest ryzyko do zamknięcia w pierwszej kolejności); wygenerować `.lib` z `.def` (`dumpbin /exports` + `lib /def:`); rozpakować `.task` (dwupoziomowy ZIP `[W]`); uruchomić **sam `hand_detector.tflite`** na jednej klatce; zdekodować 2016 kotwic + NMS; porównać box i score z Pythonem |
| 0c — **spike A (równolegle)** | `git clone --branch v1.0.0`, cherry‑pick PR #6238, MSYS2 + OpenCV **3.4.10** w `C:\opencv\build`, `bazel build -c opt --define MEDIAPIPE_DISABLE_GPU=1 //mediapipe/tasks/c:libmediapipe`; 60‑linijkowy `main.cpp` z `MpGestureRecognizerRecognizeImage` na tej samej klatce |
| Weryfikacja | **B**: box palmy i score `\|Δ\| ≤ 1e-3` vs Python. **A**: 21 landmarków zgodnych do `1e-5` (ten sam kod → powinny być praktycznie identyczne) |
| Efekt | działający DLL + nagłówki + `.lib` + skrypt builda + notatka z listą patchy; golden files w `tests/golden/` |
| dd | 8–18 (oba spike'y łącznie, z toolchainem) |
| tok | 1.2–3.0 M |
| **Go / No-go** | wg tabeli bramki w §3 |

### Faza 1 — szkielet projektu i GUI

| | |
|---|---|
| Cel | Okno wygląda identycznie jak dzisiaj, bez logiki |
| Zakres | CMake + vcpkg manifest + presety; `uic` na `src/gui.ui`; `rcc` na `darkstyle.qrc`; `MainWindow` z pustymi slotami; enumeracja kamer i backendów w combo boxach |
| Weryfikacja | zrzut ekranu porównany z `docs/images/ui.PNG`; wszystkie 18 kontrolek wejściowych reagują |
| dd | 5–9 |
| tok | 0.7–1.4 M |

### Faza 2 — kamera i wątek przechwytywania

| | |
|---|---|
| Zakres | `Camera`, `LatestFrameBuffer`, `CaptureWorker` z pełną semantyką stop/restart/strand |
| Weryfikacja | testy z `FakeCamera`/`BlockingCamera`/`ExplodingCamera` (odpowiedniki 13 testów z `tests/test_camera.py`, 233 linie `[W]`); `camera_fps` mierzone na sztucznym zegarze |
| dd | 6–10 |
| tok | 0.6–1.2 M |

### Faza 3 — pipeline rozpoznawania

| | |
|---|---|
| Zakres | `IInferenceBackend` + wybrana implementacja, gating, watchdog, znaczniki ms, metryki, `resultReady` |
| Weryfikacja | odpowiedniki 13 testów z `tests/test_recognizer.py` (283 linie `[W]`) z `FakeBackend`; aplikacja pokazuje żywy obraz z landmarkami |
| dd | 8–14 (wariant A) / 25–45 (wariant B — tu siedzi §6.2 i §6.3) |
| tok | 1.0–2.0 M (A) / 3.0–7.0 M (B) |

### Faza 4 — rysowanie landmarków

| | |
|---|---|
| Zakres | `LandmarkDrawing` + tablica 21 krawędzi + style z tabeli §5.5 |
| Weryfikacja | test pikselowy: renderowanie ustalonego zestawu 21 landmarków na czarnym tle, porównanie z obrazem wygenerowanym dziś przez Pythona (`mp_drawing.draw_landmarks`), tolerancja 0 pikseli różnicy |
| dd | 3–5 |
| tok | 0.3–0.6 M |

### Faza 5 — TTS

| | |
|---|---|
| Zakres | `Speaker` na `QTextToSpeech`, kolejka z coalescingiem, mapowanie rate/volume, wybór głosu |
| Weryfikacja | odpowiedniki 17 testów z `tests/test_speaker.py` (565 linii `[W]`) na silniku `mock` `[W]`; ręczny odsłuch kilku liter pod rząd (regresja „tylko pierwsza litera") |
| dd | 4–7 |
| tok | 0.4–0.8 M |

### Faza 6 — integracja MainWindow + metryki

| | |
|---|---|
| Zakres | wygładzanie oknem, `format_rate_details`, tooltip z `dropped_frames`, reset kamery/rozpoznawania/TTS, wybór modelu z rollbackiem, property page z pauzą, `closeEvent` |
| Weryfikacja | odpowiedniki 12 testów z `tests/test_main_app.py` (221 linii `[W]`) na `QT_QPA_PLATFORM=offscreen` |
| dd | 6–10 |
| tok | 0.7–1.3 M |

### Faza 7 — pakowanie i CI

| | |
|---|---|
| Zakres | `windeployqt`, kopiowanie `models/` + `assets/` + `libmediapipe.dll`, ZIP, instalator jednoplikowy, `BUILD_INFO.txt`, `START_HERE.md`; workflow: MSVC + Qt + `ctest`; test sum SHA-256 modeli (odpowiednik `tests/test_artifact_checksums.py`) |
| Weryfikacja | build na czystym runnerze przechodzi; paczka uruchamia się na maszynie bez Qt i bez VC Redist (albo z jawnie dołączonym redistem) |
| dd | 6–12 |
| tok | 0.6–1.4 M |

### Faza 8 — przebieg optymalizacyjny (cele mierzalne)

Wszystkie liczby odniesienia zmierzone dziś na tej maszynie (i7‑9750H 6C/12T, 16 GB RAM,
GTX 1650 + UHD 630 `[W]`), model `models/gesture_recognizer_asl_0.task`, 640×480, XNNPACK.

| Cel | Punkt odniesienia (zmierzony) | Cel po porcie |
|---|---|---|
| Czysta inferencja, tryb `IMAGE` | mediana **19,2–21,0 ms** przez 75 s ciągłego obciążenia `[W]` | ≥ tyle samo; **nie oczekiwać poprawy** — to już jest natywny C++ pod Pythonem |
| Inferencja, tryb `LIVE_STREAM`, jeden wątek sterujący | mediana **25,7 ms** (p10 20,8 / p90 32,3, n=180) `[W]` — sam graf LIVE_STREAM dokłada ~5 ms | ≈ tyle samo |
| Narzut Pythona poza inferencją | **0,84 ms/klatkę** na bezczynnej maszynie, **1,74 ms** pod obciążeniem `[W]`. Rozkład (maszyna bezczynna): `mp.Image` 0,475 + `draw_landmarks` 0,243 + `QImage` 0,032 + `copy` 0,030 + `cvtColor` 0,030 + proto 0,027 + style 0,003 | ≤ 0,3 ms (zero‑copy `cv::Mat` → tensor, rysowanie wprost do bufora `QImage`) |
| **Latencja end‑to‑end w obecnej aplikacji** | **50–70 ms**, pipeline **12–18 FPS**, 169–208 porzuconych klatek w 35 s, przy kamerze 21,6 FPS `[W]` | < 30 ms, pipeline = pełna klatkowość kamery |
| Blokada wątku GUI | — | < 5 % czasu |
| Start aplikacji | same importy Pythona **1,2–1,7 s** `[W]` + rozpakowanie 170 MB onefile do `%TEMP%` przy każdym starcie `[W]` | < 0,5 s |
| Rozmiar dystrybucji | katalog `app/` **430 MB** (PySide6 123 + cv2 113 + mediapipe 64 + numpy.libs 36 + models 24 + …), onefile `.exe` **170 MB** `[W]` | 120–200 MB `[Z]` |
| GPU | brak — MediaPipe na Windows jest CPU‑only `[W]` | eksperyment: LiteRT WebGPU/D3D12 albo ORT DirectML na GTX 1650 |

### ⚠️ Hipoteza pomiarowa (SPRZECZNA z pomiarami na żywo — patrz ramka niżej)

Uruchomiłem **pełny pipeline obecnej aplikacji** (`GestureRecognizerApp` + `CameraWorker`,
`QT_QPA_PLATFORM=offscreen`) z syntetyczną kamerą oddającą ~21,6 FPS:

| Konfiguracja | pipeline FPS | `inference_ms` | porzucone klatki / 30 s |
|---|---|---|---|
| **Obecna** (`frame_ready` i `recognize_next_signal` przez `QueuedConnection` → wątek GUI) | **12–18** | **50–70 ms** | **169–208** |
| **Ta sama, z `DirectConnection`** (zgłoszenie kolejnej klatki bez skoku przez pętlę zdarzeń GUI) | **19–21** (= pełna klatkowość kamery) | **17,5–31 ms** | **0** |

`[W]` — oba przebiegi zmierzone, ten sam proces, ta sama klatka, ta sama maszyna.

> ### ⛔ SPRZECZNOŚĆ — ten pomiar jest hipotezą, nie wynikiem
>
> Powyższe liczby pochodzą z **syntetycznej kamery** (`time.sleep(1/30)` w atrapie `read()`),
> która oddawała 21,6 FPS zamiast 30. **Trzy pomiary na żywo na prawdziwej kamerze**
> wykonane na gałęzi `feature/threaded-camera-capture` dają obraz przeciwny:
> **pipeline 29–32 FPS przy kamerze 30 FPS, inferencja ~17 ms, 0–7 porzuconych klatek
> w ~30 s** `[W]`. Czyli na prawdziwym sprzęcie aplikacja **już dziś nadąża za kamerą**
> i skok przez pętlę zdarzeń GUI nie kosztuje 30–40 ms.
>
> Najprawdopodobniejsze wyjaśnienie rozbieżności `[Z]`: `time.sleep()` na Windows ma
> ziarnistość ~15,6 ms i w połączeniu z GIL-em zaburza szeregowanie wątków w harnessie —
> czyli wąskim gardłem był mój test, nie aplikacja.
>
> **Status: hipoteza niepotwierdzona, do ponownego pomiaru na prawdziwej kamerze.**
> Zostawiam ją w dokumencie świadomie, bo jeśli się nie potwierdzi (a wszystko na to
> wskazuje), to wniosek jest **jeszcze mocniejszy**: aplikacja jest już ograniczona
> klatkowością kamery, więc przepisanie na C++ nie ma z czego ugrać wydajności.

Hipoteza, która z tego wynikała: *~30–40 ms na klatkę traci dziś nie Python jako język,
tylko podwójny skok przez pętlę zdarzeń wątku GUI w gorącej ścieżce.* **Pomiary na
prawdziwej kamerze jej nie potwierdzają** — patrz ramka powyżej. Do rozstrzygnięcia
ponownym pomiarem; w obu scenariuszach wniosek dla portu jest ten sam.

**Zastrzeżenia, bez których ta liczba jest myląca** (`[Z]`):
- `DirectConnection` przenosi `recognize_frame()` na wątek przechwytywania i na wątek callbacku
  MediaPipe → `_inference_pending`, `_inference_started_at` i `last_timestamp_ms` przestają być
  chronione przez serializację na wątku GUI. **Wymaga to audytu wyścigów i prawdopodobnie
  muteksa/atomiku** — to nie jest gotowa łatka, tylko zweryfikowana hipoteza.
- Pomiar użył syntetycznej kamery (`time.sleep(1/30)`), nie prawdziwego sterownika.
- `inference_ms` w aplikacji to średnia krocząca — jest wrażliwa na pojedyncze zacięcia.

Uczciwe podsumowanie wydajności: **sam język odbiera najwyżej ~0,8–1,7 ms z ~20–26 ms
budżetu na klatkę (4–8 %)**. Reszta dzisiejszej straty to architektura pętli, którą można
naprawić w Pythonie. Przy kamerze 30 FPS (a przy autoekspozycji 8–10 FPS — udokumentowane
w README) użytkownik **nie zobaczy różnicy w FPS z samego przejścia na C++**. Realne,
widoczne zyski portu to **czas startu, rozmiar paczki i dostęp do GPU przez LiteRT/ORT**.

| | dd | tok |
|---|---|---|
| Faza 8 | 4–8 | 0.4–0.9 M |

### Faza 9 — dokumentacja EN + PL

| | |
|---|---|
| Zakres | README.md / README.pl.md (po 253 linie), TECHNICAL_DOCUMENTATION.md / .pl.md (338/340 linii): sekcje 2 (stack), 3 (architektura + diagramy mermaid), 4 (module reference — inne nazwy plików), 7 (running and packaging). `AGENTS.md` — nowe komendy build/test. `third_party/protobuf/` znika wraz z opisem |
| Weryfikacja | ręczny przegląd równoważności EN/PL; wszystkie linki lokalne żyją; screeny **przerobione na nowo** (wymóg `AGENTS.md`: tylko prawdziwe zrzuty) |
| Uwaga | `docs/Praca_Dyplomowa_Kamil_Rataj.pdf` **zostaje nietknięty** — opisuje wersję Pythonową i podlega `LICENSE-docs` |
| dd | 4–7 |
| tok | 0.4–0.8 M |

### Podsumowanie faz

| Wariant | Suma dd | Suma tok |
|---|---|---|
| **A** (MediaPipe C API / Bazel — parytet za darmo, dług toolchainowy) | **54–101 dd ≈ 11–20 tygodni** | **6,5–13,9 M** |
| **B** (LiteRT + własny graf — rekomendowany) | **79–147 dd ≈ 16–29 tygodni** | **9,3–19,9 M** |
| **C** (ORT + konwersja + własny graf) | **84–157 dd ≈ 17–31 tygodni** | **10,0–21,0 M** |

Uwaga do wariantów B/C: `hand_landmarker.task` (2 modele, 7,8 MB) jest **bajtowo identyczny
we wszystkich trzech pakietach `models/*.task`** `[W]` — różni je wyłącznie mały
`custom_gesture_classifier.tflite` (116 KB). Parytet trzeba więc osiągnąć **raz** dla części
landmarkowej; obsługa trzech modeli nie mnoży pracy.

---

## 8. Ryzyka i mitygacje

| # | Ryzyko | Prawd. | Wpływ | Mitygacja |
|---|---|---|---|---|
| R0 | **Wrapper C++ LiteRT nie zbuduje się MSVC** (Google: „LiteRT needs `clang` to build"; instrukcje CMake pomijają Windows) `[W]` | **wysokie** | zabija wariant B | pierwsze zadanie Fazy 0b; fallback: stary `tensorflowlite_c` przez CMake (`tensorflowlite_c.dll`, Windows 10 przetestowany) `[W]` albo binarki `ValYouW/tflite-dist` `[W]`; ostatecznie ORT (wariant C) |
| R1 | MSVC nie kompiluje MediaPipe v1.0.0 (issue #6237 otwarte, PR #6238 niezmergowany) `[W]` | **wysokie** | zabija wariant A | timebox 5 dni; alternatywnie wyciągnąć natywkę z `homuler/MediaPipeUnityPlugin` (v0.16.3, **listopad 2024**, ~22 mies. stare, ale jawnie wspiera Gesture Recognition na Windows CPU) `[W]` |
| R1b | **Bazel 7 EOL grudzień 2026**, MediaPipe = hybryda WORKSPACE+bzlmod, nie zbuduje się na Bazelu 9/10 `[W]` | pewne | dług na lata | to jest główny powód, dla którego wariant A jest fallbackiem, nie pierwszym wyborem |
| R1c | v1.0.0 zmienia nazewnictwo API C („Enforce namespacing conventions") `[W]` | pewne | mała | przypiąć wersję i zapisać ją w `third_party/mediapipe/README.md` |
| R2 | Link `linkstatic=True` wszystkich tasków przy 16 GB RAM `[W]` → OOM | średnie | dni stracone | lokalny patch przycinający `deps` w `tasks/c/BUILD` do `gesture_recognizer_c_lib` |
| R3 | Konflikt OpenCV: MediaPipe wymaga 3.4.10, aplikacja chce 4.x/5.x `[W]` | wysokie | godziny–dni | linkować MediaPipe statycznie do DLL i nie eksportować symboli OpenCV; albo zejść na 3.4.10 w całej aplikacji |
| R4 | Wariant B: parytet numeryczny grafu | **wysokie** | +2–6 tygodni | zrzut tensorów pośrednich po każdym z 13 etapów §6.2, nie tylko wyniku; golden per etap |
| R5 | Brak klatek testowych z dłonią w repo `[W]` | pewne | blokuje R4 | użytkownik nagrywa ~300 klatek w Fazie 0; bez tego nie ma czym walidować |
| R6 | Bzlmod + nieotagowany SHA absl `255c84dad…` `[W]` — build niereprodukowalny w czasie | średnie | dni | zamrozić `MODULE.bazel` w patchu, wersjonować DLL + SHA-256 w repo |
| R7 | `QTextToSpeech`/sapi widzi inny zbiór głosów niż pyttsx3 (lokalnie tylko 1 głos) `[W]` | średnie | dzień–dwa | sprawdzić w Fazie 0; fallback `ISpVoice` |
| R8 | Zmiana semantyki suwaków rate/volume (pyttsx3 wpm → Qt −1..1) | pewne | mała | udokumentować w README EN+PL, dobrać mapowanie zachowujące dzisiejsze domyślne odczucie |
| R9 | Praca dyplomowa opisuje wersję Pythonową | pewne | zależy od celu | **nie ruszać PDF-u**; port opisać jako osobną gałąź/wersję |
| R10 | Regresja funkcji: property page sterownika | średnie | funkcja znika | **zostać przy OpenCV `CAP_DSHOW`** — Qt Multimedia na Windows nie ma DirectShow `[W]` |
| R11 | Toolchain od zera na maszynie użytkownika (brak VS/CMake/Bazel/Qt/OpenCV/vcpkg) `[W]` | pewne | 1–3 dni + kilkadziesiąt GB (wolne 561 GB, OK `[W]`) | ująć w Fazie 0a; rozważyć build MediaPipe w kontenerze/na CI, a lokalnie tylko konsumpcję DLL |
| R12 | `windows-latest` na GH Actions to od czerwca 2026 **Windows Server 2025 z VS 2026** i CMake 4.4.2 `[W]` | pewne | build CI się rozjeżdża z lokalnym | **przypiąć `runs-on: windows-2022`** (VS 17.14 / v143, CMake 3.31.6) `[W]` |
| R13 | `install-qt-action` opakowuje `aqtinstall`, który **nie ma wydania od ~15 miesięcy** `[W]` | średnie | CI przestaje instalować Qt | cache'ować gotowe Qt jako artefakt GH Actions; plan B: `vcpkg install qtbase:x64-windows` (długi build) |
| R14 | Oficjalna paczka OpenCV Windows jest budowana **VS 2019 (vc16)**, nie 2022 `[W]` | pewne | mała (ABI v143 zgodne) | użyć Conan 2.32.0 (ma 4.14.0) albo zbudować OpenCV samodzielnie |
| R15 | DirectML w trybie utrzymaniowym, a Windows ML **wyklucza GTX 1650 i UHD 630** `[W]` | pewne | zamyka ścieżkę GPU w wariancie C w perspektywie lat | jeśli GPU ma znaczenie — preferować **LiteRT WebGPU/D3D12** albo ORT **CUDA EP** (compute capability 7.5 wspierane `[W]`) |
| R16 | Prebuilt LiteRT to **sam DLL, bez import library**; ABI stabilizowane dopiero od 2.2.0 `[W]` | pewne | dzień | wygenerować `.lib` z `.def` (`dumpbin /exports` → `lib /def:`); przypiąć wersję DLL + SHA‑256 w repo |

---

## 9. Zasady testowania (przeniesione z `AGENTS.md`)

Twarde reguły: **żaden test nie wolno mu dotknąć kamery, głośnika ani sieci.**
Dziś: 59 testów w 9 plikach, 1417 linii `[W]`, z `QT_QPA_PLATFORM=offscreen`
ustawionym w `tests/conftest.py` `[W]` i ~22 klasami-atrapami.

Odpowiedniki w C++:

| Co | Dziś (Python) | Po porcie |
|---|---|---|
| Kamera | `FakeCapture`, `TickingCamera`, `BlockingCamera`, `ExplodingCamera` | `ICamera` (interfejs) + te same 4 atrapy; `CaptureWorker` bierze `ICamera&` |
| Zegar | wstrzykiwany `clock=time.monotonic` | `std::function<std::chrono::nanoseconds()>` w konstruktorze `CaptureWorker`/`GestureRecognizer` |
| Backend inferencji | `StubRecognizer`, `FakeRecognizer`, `FakeResult` | `IInferenceBackend` + `FakeBackend` sterowany z testu (ręczne wywołanie callbacku) |
| TTS | `FakeEngine` + 6 wariantów awarii | silnik **`mock`** `QTextToSpeech` `[W]` + własny `ISpeechEngine` dla scenariuszy awaryjnych |
| GUI | `QApplication` offscreen | `QTest` + `QT_QPA_PLATFORM=offscreen`, `QSignalSpy` |
| Modele | SHA-256 z `models/SHA256SUMS.txt` | to samo, `ctest` |
| Higiena | brak `kaggle.json`, brak sekretów | to samo (skan drzewa) |

**Uwaga o wstrzykiwaniu zależności**: w Pythonie testy podmieniają wszystko monkeypatchem.
W C++ trzeba **z góry** zaprojektować interfejsy (`ICamera`, `IInferenceBackend`, `ISpeechEngine`)
— to jest ~150–300 dodatkowych linii kodu produkcyjnego, których dziś nie ma. Nie da się tego
dodać później bez przepisywania.

---

## 10. Pytania otwarte do użytkownika

0. **Czy jest jeszcze co poprawiać w Pythonie?** Mój syntetyczny pomiar sugerował duży zysk
   z usunięcia skoku przez pętlę zdarzeń GUI, ale **pomiary na żywo na galęzi
   `feature/threaded-camera-capture` (29–32 FPS przy kamerze 30 FPS, ~17 ms, 0–7 dropów)
   tego nie potwierdzają** `[W]` — patrz ramka w §7/Faza 8. **Pytanie do rozstrzygnięcia
   pomiarem, zanim ktokolwiek zacznie port:** czy aplikacja na prawdziwym sprzęcie jest już
   ograniczona klatkowością kamery? Jeśli tak — a na to wskazują pomiary na żywo — to
   **nie ma żadnego zapasu wydajności do odzyskania ani w Pythonie, ani w C++**.
1. **Cel portu.** Jeśli celem jest wydajność — dane w §7/Faza 8 mówią, że sam język daje
   0,8–1,7 ms na klatce i użytkownik tego nie zobaczy. Jeśli celem jest portfolio / rozdział
   pracy / nauka C++ / dostęp do GPU — wtedy plan ma sens niezależnie od zysku FPS.
   **Która to sytuacja?**
2. **Jedno repo czy dwa?** Port w tym samym repo (gałąź / katalog `cpp/`) czy osobne repo?
   Praca dyplomowa i `LICENSE-docs` przemawiają za pozostawieniem wersji Pythonowej nietkniętej.
3. **Format wydania.** Zostawiamy dzisiejszy kształt paczki (ZIP + `RUN.bat` + `START_HERE.md`
   + `BUILD_INFO.txt` + onefile `.exe`), czy przechodzimy na instalator (Inno Setup)?
4. **Property page sterownika** — czy to funkcja obowiązkowa? Jeśli tak, OpenCV `CAP_DSHOW`
   zostaje na stałe i Qt Multimedia odpada jako alternatywa.
5. **Głos TTS.** Dziś kod celuje w `TTS_MS_EN-US_ZIRA_11.0`; na tej maszynie SAPI przez Qt
   widzi tylko `Microsoft Paulina Desktop` `[W]`. Czy angielski głos ma być wymagany, czy
   wystarczy „pierwszy dostępny"?
6. **Nagranie klatek testowych** — kto i kiedy nagra ~300 klatek z dłonią? Bez tego nie
   powstanie ani golden parytetu, ani test regresji rozpoznawania.
7. **Docelowa wersja OpenCV** — czy akceptujemy zejście całej aplikacji na 3.4.10 (zgodność
   z MediaPipe), czy izolujemy DLL i używamy nowego OpenCV w aplikacji?
8. **Czy `notebooks/` (Python, Colab) zostaje?** Zakładam, że tak — trening jest poza portem.
