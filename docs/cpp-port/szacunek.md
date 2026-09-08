> **Kosztorys — 2026-09-09.**
> Wszystkie liczby to szacunki na ten dzień, nie zobowiązania. Oznaczenia `[W]` (zweryfikowane
> pomiarem lokalnym albo potwierdzone źródłem) i `[Z]` (założenie / oszacowanie autora).
>
> Plan techniczny towarzyszący temu kosztorysowi: [`plan.md`](plan.md).
>
> Dokument jest **wyłącznie po polsku, na życzenie autora repozytorium**. Zasada równoważności
> EN/PL z `AGENTS.md` dotyczy `README.md` / `README.pl.md` oraz obu plików
> `docs/TECHNICAL_DOCUMENTATION*.md` i nie obejmuje tych dwóch dokumentów planistycznych.

# Przepisanie aplikacji na C++/Qt — szacunek kosztu

Pytanie: ile czasu i ile tokenów LLM zajęłoby przepisanie tej aplikacji w całości na C++
z czystym Qt (bez Pythona), z optymalizacjami, przy użyciu agentów Claude Code.

---

## 1. Podsumowanie

### 1.1 Trzy warianty realizacji

| Ścieżka backendu | Człowiek (senior C++/Qt) `[Z]` | Claude + user w pętli `[Z]` | Claude autonomicznie `[Z]` | Ryzyko |
|---|---|---|---|---|
| **A** — MediaPipe Tasks C API, Bazel → `libmediapipe.dll` | **11–20 tyg.** | **6,5–13,9 M tok.** / 5–9 mies. | **11–33 M tok.** (centralnie ~20 M) / 2–5 tyg. | **Bardzo wysokie** |
| **B** — LiteRT + własna implementacja grafu *(rekomendowana, jeśli port ma powstać)* | **16–29 tyg.** | **9,3–19,9 M tok.** / 7–13 mies. | **16–47 M tok.** (centralnie ~30 M) / 3–8 tyg. | **Wysokie** |
| **C** — ONNX Runtime + konwersja modeli + własny graf | **17–31 tyg.** | **10,0–21,0 M tok.** / 8–14 mies. | **17–50 M tok.** (centralnie ~32 M) / 4–9 tyg. | Wysokie (najniższe ryzyko *builda*) |
| **D** — **bez przepisywania**: celowana praca w Pythonie | **0,5–2 tyg.** | **0,2–0,6 M tok.** / 1–2 tyg. | 0,4–1,2 M tok. / 2–5 dni | Niskie |

Założenia do kolumn `[Z]`:
- **Człowiek**: jeden senior C++/Qt, pełny etat, znający Qt ale nie znający MediaPipe.
- **Claude + user w pętli**: agenty piszą, użytkownik przegląda i testuje ~10–15 h/tygodniowo
  (druga liczba kalendarzowa przy 30 h/tyg. jest w §6).
- **Claude autonomicznie**: agenty pracują ~24/7, użytkownik odblokowuje tylko to, czego
  agent zrobić nie może (§5), i robi to w ciągu godzin, nie dni.

### 1.2 Kalibracja tokenów

Punkt odniesienia to zadanie z tej samej sesji: capture worker + rozdział odczytu FPS +
poprawka znaczników czasu + dokumentacja + testy, czyli **1300 wstawionych / 127 usuniętych
linii w 12 plikach** `[W]` przy 59 testach `[W]`. Koszt: ~270 k (implementer) + 3 × 80 k
(reviewer) + 100 k (spike) ≈ **610 k tokenów**, czyli **~430 tokenów na zmienioną linię**
w Pythonie, z użytkownikiem w pętli.

Mnożniki przyjęte dla C++ `[Z]`:

| Czynnik | Mnożnik | Uzasadnienie |
|---|---|---|
| Pętle kompilacji i linkowania | **×2–4** | Każdy błąd MSVC/CMake to pełny cykl build → log → poprawka. Logi Bazela i linkera są długie |
| Brak człowieka w pętli (tryb autonomiczny) | **×1,6–2,2** | Więcej rund przeglądu (4 zamiast 3) i poprawek (3 zamiast 2), brak wczesnego „stop, to zła droga" |
| Punkty zacięcia | **+1,0–3,4 M** | Osobna pozycja, §4.3 |

---

## 2. Inwentarz — podstawa wszystkich liczb

`git ls-files` = **85 plików** `[W]`.

| Obszar | Fakt |
|---|---|
| Kod produkcyjny | `main_app.py` 454, `recognizer.py` 444, `camera.py` 313, `speaker.py` 308, `custom_landmarks.py` 96, `main.py` 30, `gui.py` 693 (generowany) `[W]` |
| Interfejs | `src/gui.ui` 2095 linii, **57 widgetów**: 18 QLabel, 11 QGroupBox, 8 QSpinBox, 5 QPushButton, 3 QProgressBar, 2 QComboBox, 2 QCheckBox, 1 QSlider, 1 QStatusBar, 5 QWidget, 1 QMainWindow, 4 QGridLayout `[W]`. **Zero promoted widgets**, `<resources/>` puste `[W]` |
| Testy | **59 funkcji testowych w 9 plikach, 1417 linii**, ~22 klasy-atrapy, `QT_QPA_PLATFORM=offscreen` w `conftest.py` `[W]` |
| Dokumentacja | README 253 + README.pl 253, TECHNICAL_DOCUMENTATION 338 + .pl 340 `[W]` |
| Skrypty | `build_patched_protobuf.ps1` 178, `build_windows_release.ps1` 174, `repack_patched_wheel.py` 101 `[W]` |
| Modele | 3 × `.task` (dwupoziomowy ZIP): `hand_detector.tflite` 2,3 MB, `hand_landmarks_detector.tflite` 5,5 MB, `gesture_embedder.tflite` 628 KB, `canned_gesture_classifier.tflite` 6,9 KB, `custom_gesture_classifier.tflite` 116 KB `[W]` |
| Klasy modelu | 25 etykiet: `none` + A–Y bez J i Z `[W]` |
| CI | 1 workflow, 29 linii, macierz Python 3.10/3.12 na `windows-latest` `[W]` |
| Dystrybucja | katalog `app/` **430 MB** (PySide6 123 + cv2 113 + mediapipe 64 + numpy.libs 36 + models 24 + matplotlib 12 + docs 11 + PIL 11), onefile `.exe` **170 MB** `[W]` |
| Sprzęt docelowy | i7-9750H 6C/12T, 16 GB RAM, GTX 1650 + Intel UHD 630, 561 GB wolne `[W]` |
| Toolchain C++ na maszynie | **żaden**: brak `cl`, `cmake`, `bazel`, `ninja`, `vcpkg`, `conan`, `C:\Qt`, `C:\opencv` `[W]` |

---

## 3. Wersje bibliotek (stan na 2026-09-09)

| Biblioteka | Wersja | Prebuilt Windows x64 | Wpływ na szacunek |
|---|---|---|---|
| **Qt 6** | **6.11.2** (2026-08-18) `[W]`; LTS open source tylko 6.8.3 `[W]` | **tak** (Qt Online Installer, build MSVC 2022) `[W]` | Neutralny. Qt Widgets ma status „Done", nie jest deprecated `[W]` |
| **Qt Multimedia** | 6.11 | tak | **Nie zastąpi OpenCV.** Domyślny backend na Windows = FFmpeg, natywny WMF **deprecated od Qt 6.10**; capture przez Media Foundation (`qwindowscamera.cpp`, `IMFSourceReader`) `[W]`. **Brak jakiegokolwiek API do property page sterownika** `[W]` |
| **Qt TextToSpeech** | 6.11 | tak | **Usuwa cały workstream COM/SAPI** (−0,5 do −1 tyg.). Lokalnie zweryfikowane: `availableEngines() == ['sapi','mock','winrt']`, `State.Ready`, `setRate`/`setVolume`/`setPitch`, `availableVoices()` `[W]`. Silnik **`mock`** rozwiązuje testy TTS bez dźwięku |
| **MediaPipe** | **1.0.1** PyPI (2026-08-14) / tag **v1.0.0** (2026-07-28) `[W]` | **NIE — nigdzie.** Brak assetów w releasach, **brak portu vcpkg, brak recipe Conan, brak oficjalnego NuGeta** `[W]` | To jest **cały koszt i całe ryzyko** ścieżki A |
| — pin `<0.10.30` | | | **Znika w C++.** Legacy `drawing_utils`/`hands_connections` wypadły z wheela w 0.10.30 (commit `51f1cbf`, zmiana `find_packages` w `setup.py`) `[W]`; w C++ i tak rysujemy sami |
| — Bazel wymagany | `.bazelversion` **7.7.0**, hybryda WORKSPACE (32 KB) + `MODULE.bazel` `[W]` | | **Pogarsza.** Bazel 7 **EOL grudzień 2026**, Bazel 9 usunął obsługę WORKSPACE całkowicie → **ten build nie ma drogi naprzód** `[W]` |
| — piny zależności | protobuf **6.31.1**, abseil **20260526.0**, oba przez `archive_override` `[W]`; OpenCV **3.4.10** w `C:\opencv\build` `[W]` | | Nie do pogodzenia z vcpkg/system. Ale **znika łatany wheel protobuf**: `third_party/protobuf/` + `third_party/wheels/` + 178-liniowy `build_patched_protobuf.ps1` `[W]` |
| — stan builda MSVC | issue **#6237 otwarte** (`C3547`), poprawka **PR #6238 niezmergowana** (community, od 2026-02-17) `[W]` | | Główne ryzyko ścieżki A |
| — target DLL | `mediapipe/tasks/c/BUILD` **ma już** `genrule` → `libmediapipe.dll` i `alias` z `select()` na Windows, w deps `gesture_recognizer_c_lib`; obecne w tagu v1.0.0 `[W]` | | **Nie trzeba pisać własnego targetu — koszt tej pozycji = 0** |
| — GPU | „Desktop GPU is currently not supported"; issue #5126 zamknięte won't-fix `[W]` | | Windows = **wyłącznie CPU** |
| **LiteRT** | **2.2.0** (2026-08-13) `[W]` | **częściowo — oficjalny `libLiteRt.dll` dla `windows_x86_64` istnieje** `[W]`, ale **bez import library**; wrapper C++ kompilujesz sam z `litert_cc_sdk.zip`, a Google pisze **„LiteRT needs `clang` to build"**, instrukcje CMake **pomijają Windows** `[W]` | **Usuwa workstream Bazela**, zostawia reimplementację grafu. **Daje GPU na Windows** (WebGPU/Direct3D 12 — GTX 1650 i UHD 630 obsługują D3D12) `[W]`. XNNPACK domyślnie ON na Windows `[W]`. Brak portu vcpkg `tensorflow-lite` `[W]` |
| **ONNX Runtime** | **1.29.0** (2026-08-12) `[W]` | **tak, w pełni** — `onnxruntime-win-x64-1.29.0.zip` z `include/*.h`, `lib/onnxruntime.{dll,lib,pdb}` `[W]`; port vcpkg 1.23.2#1 `[W]` | Najniższe ryzyko builda, ale **+konwersja 5 modeli** (`tf2onnx` **1.17.0**, pierwsze wydanie od 26 miesięcy, README z notką „looking for a new maintainer" `[W]`). DirectML obsługuje **oba** GPU (NVIDIA Kepler+, Intel Haswell+) `[W]`, ale **jest w trybie utrzymaniowym**, a Windows ML **wyklucza ten sprzęt** (TensorRT-RTX wymaga RTX 30xx+, OpenVINO GPU wymaga Intela 12. gen+) `[W]`. Alternatywa NVIDIA-only: CUDA EP, compute capability 7.5 wspierane `[W]` |
| — skrót implementacyjny | `opencv/opencv_zoo` ma `palm_detection_mediapipe_2023feb.onnx` **z demem C++ i CMakeLists** (Apache-2.0) oraz `handpose_estimation_mediapipe_2023feb.onnx` `[W]` | | Wagi to migawka z lutego 2023, **nie dają parytetu** z naszym `.task`, ale jako wzorzec dekodowania kotwic i ROI w C++ są bardzo wartościowe |
| **OpenCV** | **4.14.0** (2026-07-19) rekomendowane; 5.0.0 (2026-06-06) też żyje `[W]` | tak, ale oficjalna paczka jest budowana **VS 2019 (vc16)**, brak `vc17` `[W]` (ABI zgodne z v143) | **`CAP_DSHOW` i `CAP_PROP_SETTINGS` żyją także w gałęzi 5.x, bez znaczników deprecacji** `[W]` → property page przechodzi 1:1. 5.0 zmienia `VideoCapture::get()` na −1 dla nieobsługiwanych property, zmienia semantykę opakowania `std::vector`, przenosi `ml`/HOG/kaskady do contrib i **zmienia piksele `resize`/`putText`** → rebaseline testów obrazkowych `[W]`. Brak portu 5.x w vcpkg i Conan `[W]` |
| **MSVC** | VS 2022 **17.14 LTSC** = v143, `_MSC_VER` 1944, wsparcie do 2032-01-13 `[W]`; VS 2026 18.10 = v145 `[W]` | — | Przy VS 2026 wybrać toolset **14.50 „Long-term"** (EOL 2028), nie domyślny 14.51 (EOL luty 2027) `[W]` |
| **CMake** | **4.4.3** (2026-08-25) `[W]` | tak | `qt_generate_deploy_app_script()` od Qt 6.3, `DEPLOY_TOOL_OPTIONS` od 6.7 `[W]` |
| **vcpkg / Conan / Bazel** | rolling, snapshot **2026.07.29** `[W]` / **2.32.0** `[W]` / LTS **9.2.0** `[W]` | — | vcpkg bez `builtin-baseline` wpada w Classic mode i **ignoruje wersjonowanie** `[W]`. Conan jako jedyny ma OpenCV 4.14.0 `[W]` |
| **Testy** | Catch2 **3.16.0** `[W]`, GoogleTest **1.18.0** `[W]`, Qt Test 6.11 | — | **Qt Test obowiązkowy** — `QSignalSpy` i symulacja zdarzeń to jego wyłączność. Platforma `offscreen` działa na Windows (brak wykluczenia w `qtbase/src/plugins/platforms/CMakeLists.txt`) `[W]` |
| **CI** | `windows-latest` = **Windows Server 2025 z VS 2026** od czerwca 2026 `[W]` | — | **Przypiąć `runs-on: windows-2022`** (VS 17.14 / v143, CMake 3.31.6); `windows-latest` ma CMake 4.4.2 `[W]`. Qt **nie jest preinstalowane**; `jurplel/install-qt-action` **v4.3.1**, opakowuje `aqtinstall` **bez wydania od ~15 miesięcy** `[W]` |
| **Pakowanie** | Inno Setup **7.1.0** (2026-08-12) `[W]`, NSIS 3.12, WiX 7.0.0 `[W]` | — | Qt IFW od 4.10 **nie jest dostępny samodzielnie**, tylko przez Qt Online Installer — utrudnia CI `[W]` |
| **Licencja Qt** | LGPLv3 | — | Linkowanie **dynamiczne** = prosta zgodność (to, co produkuje `windeployqt`). Statyczne obliguje do udostępniania plików obiektowych aplikacji przy każdym wydaniu `[W]` |

**Czy najnowsze wersje zmieniają rekomendowaną ścieżkę? Tak.** Rok temu MediaPipe/Bazel byłby
jedyną sensowną opcją. Dziś **LiteRT 2.2.0 ma oficjalny prebuilt DLL dla Windows i akcelerator
D3D12**, a MediaPipe siedzi na Bazelu 7 z EOL w grudniu 2026, hybrydzie WORKSPACE+bzlmod bez
drogi na Bazel 9 i otwartym defekcie MSVC bez zmergowanej poprawki `[W]`. Dlatego w
[`plan.md`](plan.md) ścieżka **B jest główna, A fallbackiem**.

---

## 4. Rozbicie na workstreamy

### 4.1 Ścieżka B (rekomendowana), Claude + user w pętli

| # | Workstream | C++ LOC `[Z]` | dev-dni `[Z]` | tokeny `[Z]` | Uwagi oparte na faktach |
|---|---|---|---|---|---|
| 0 | Toolchain + spike backendu | — | 8–18 | 1,2–3,0 M | Na tej maszynie **nie ma żadnego toolchainu C++** `[W]` |
| 1 | GUI (Qt Widgets z `gui.ui`) | ~900 | 5–9 | 0,7–1,4 M | **Oszczędność udowodniona pomiarem**: `uic -g cpp src/gui.ui` kończy się **kodem 0** i generuje **774-liniowy `ui_MainWindow.h`** `[W]`. Motyw też przechodzi: `darkstyle.qss` 54 KB + `.qrc` + 208 plików `rc/` `[W]` |
| 2 | Kamera + wątek przechwytywania | 450–650 | 6–10 | 0,6–1,2 M | OpenCV `CAP_DSHOW` zostaje — Qt Multimedia nie otworzy property page `[W]` |
| 3 | Pipeline rozpoznawania **+ backend inferencji** | 1400–2600 | **25–45** | **3,0–7,0 M** | Tu siedzi ~90 % ryzyka. Parametry grafu są publiczne i zweryfikowane: 2016 kotwic, wejście 192×192, NMS 0.3, ROI `scale 2.6`/`shift_y −0.5`, crop 224×224, embedder `[1,21,3]`+`[1,1]`+`[1,21,3]`→`[1,128]`, klasyfikator `[1,128]`→`[1,25]` `[W]` |
| 4 | Rysowanie landmarków | 250–400 | 3–5 | 0,3–0,6 M | 21 krawędzi w `HAND_CONNECTIONS`, 7 unikalnych kolorów `[W]` — test pikselowy wykonalny (obraz referencyjny wygenerowany) |
| 5 | TTS | 350–450 | 4–7 | 0,4–0,8 M | `QTextToSpeech` skraca to o ~40 % vs surowy `ISpVoice` `[W]` |
| 6 | Metryki + integracja MainWindow | 800–1000 | 6–10 | 0,7–1,3 M | Trzy rozdzielone liczby + `dropped_frames` w tooltipie |
| 7 | Testy | 1300–2000 | 8–14 | 1,0–2,5 M | +150–300 linii **interfejsów w kodzie produkcyjnym** (`ICamera`, `IInferenceBackend`, `ISpeechEngine`) — w Pythonie testy monkeypatchują, w C++ trzeba to zaprojektować z góry `[Z]` |
| 8 | Pakowanie + CI | 200–450 | 6–12 | 0,6–1,4 M | `windeployqt` zastępuje PyInstaller |
| 9 | Dokumentacja EN+PL | ~1190 linii md | 4–7 | 0,4–0,8 M | Plus **nowe zrzuty ekranu** (`AGENTS.md`: tylko prawdziwe zrzuty) |
| 10 | Przebieg optymalizacyjny | — | 4–8 | 0,4–0,9 M | §7 |
| | **Razem** | **~5500–8000** | **79–147 dd** | **9,3–19,9 M** | |

Ścieżka A różni się workstreamem 3: **8–14 dd / 1,0–2,0 M** zamiast 25–45 dd / 3,0–7,0 M
(parytet numeryczny za darmo), ale za cenę toolchainu z §3. Razem **54–101 dd / 6,5–13,9 M**.

Ścieżka C = B + konwersja modeli i walidacja po konwersji: **84–157 dd / 10,0–21,0 M**.

**Uwaga obniżająca koszt B i C:** `hand_landmarker.task` (2 modele, 7,8 MB) jest **bajtowo
identyczny we wszystkich trzech pakietach `models/*.task`** `[W]` — różni je wyłącznie mały
`custom_gesture_classifier.tflite` (116 KB). Parytet dla części landmarkowej osiąga się **raz**.

### 4.2 Tryb autonomiczny — model kosztu

Wzorzec zaobserwowany w tej sesji (podany jako kalibracja) `[Z]`:
implementer **270–320 k** na zadanie ~1000 linii → 3 rundy przeglądu po **80–90 k** →
2 rundy poprawek po **50–100 k** → werdykt CONFIRMED.

W trybie autonomicznym zmienia się to tak `[Z]`:

| Składnik | Z użytkownikiem | Autonomicznie | Dlaczego |
|---|---|---|---|
| Implementer (C++, ~1000 linii) | 270–320 k × 2–4 = **0,55–1,3 M** | **0,6–1,4 M** | Pętle kompilacji dominują niezależnie od trybu |
| Przeglądy | 3 × 80–90 k = **0,24–0,27 M** | 4 × 90–120 k = **0,36–0,48 M** | Nikt nie powie „wystarczy"; przegląd C++ wymaga czytania logów builda |
| Poprawki | 2 × 50–100 k = **0,10–0,20 M** | 3 × 60–120 k = **0,18–0,36 M** | Brak człowieka, który wcześnie utnie złą ścieżkę |
| **Na zadanie ~1000 linii** | **0,89–1,77 M** | **1,14–2,24 M** | |
| **Mnożnik zbiorczy** | 1,0 | **×1,6–2,2** | Powyższe + zmarnowana eksploracja bez wczesnego „stop" |

Liczba zadań/sesji agentowych `[Z]`:

| Ścieżka | Zadania implementacyjne | Przeglądy | Spike'y i pętle debugowania | Razem sesji |
|---|---|---|---|---|
| A | 18–26 | 55–90 | 12–25 | **~45–70** |
| B | 26–38 | 80–130 | 20–40 | **~65–100** |
| C | 28–42 | 88–140 | 24–45 | **~70–110** |

### 4.3 Punkty zacięcia — gdzie autonomiczny przebieg stanie bez człowieka

| Klasa zacięcia | Oczekiwana liczba `[Z]` | Tokeny spalone zanim agent eskaluje `[Z]` | Dlaczego agent tego nie przejdzie |
|---|---|---|---|
| Instalatory interaktywne / z podniesieniem uprawnień (VS Build Tools, Qt Online Installer z kontem Qt, MSYS2, samorozpakowujący się OpenCV) | **3–5** | 30–80 k każde | GUI instalatora, akceptacja licencji, UAC |
| Defekt upstream Bazel/MSVC (#6237, niezmergowany #6238) — **ścieżka A** | **1–3** | **200–600 k każde** | Każdy nieudany `bazel build` zrzuca ogromny log; agent będzie próbował obejść defekt, którego nie da się obejść lokalnie |
| Wrapper LiteRT: clang vs MSVC — **ścieżka B** | **1–2** | 150–400 k każde | Brak dokumentacji Windows/MSVC `[W]` |
| Niezgodność numeryczna grafu (etap `k` z 13 ma odwróconą kolejność współrzędnych) | **3–8** | 100–300 k każde | Wynik „prawie dobry" jest najtrudniejszy do zdiagnozowania bez zrzutów tensorów pośrednich |
| Weryfikacja sprzętowa: property page sterownika, odsłuch TTS, „czy GUI wygląda dobrze" | **2–3** | 20–50 k każde | Fizycznie niewykonalne headless |
| Awarie linkowania: OOM przy `linkstatic=True` (16 GB RAM `[W]`), długie ścieżki | **1–2** | 50–150 k każde | Wymaga decyzji o przycięciu `deps` albo zmianie lokalizacji builda |
| **Budżet zacięć — ścieżka A** | | **1,0–2,6 M** | |
| **Budżet zacięć — ścieżka B** | | **1,2–3,2 M** | dominują niezgodności parytetu |
| **Budżet zacięć — ścieżka C** | | **1,3–3,4 M** | parytet + konwersja modeli |

### 4.4 Tryb autonomiczny — wynik

| Ścieżka | Tokeny (z użytkownikiem) | × mnożnik 1,6–2,2 | + budżet zacięć | **Razem autonomicznie** | Centralnie |
|---|---|---|---|---|---|
| A | 6,5–13,9 M | 10,4–30,6 M | +1,0–2,6 M | **11–33 M** | ~20 M |
| B | 9,3–19,9 M | 14,9–43,8 M | +1,2–3,2 M | **16–47 M** | ~30 M |
| C | 10,0–21,0 M | 16,0–46,2 M | +1,3–3,4 M | **17–50 M** | ~32 M |

### 4.5 Czas kalendarzowy w trybie autonomicznym (agenty 24/7)

Co może biec **równolegle**, a co jest **szeregowe**:

```
Faza 0 (BRAMKA)  ── szeregowa, ale dwa spike'y (LiteRT i MediaPipe) równolegle
      │
      ├─ Faza 1  GUI            ─┐
      ├─ Faza 2  Kamera          │  do 4 równolegle (moduły niezależne)
      ├─ Faza 4  Rysowanie       │
      ├─ Faza 5  TTS            ─┘
      │
      └─ Faza 3  Pipeline + backend  ── ŚCIEŻKA KRYTYCZNA, szeregowa
                 │
                 └─ Faza 6  Integracja  ── szeregowa (wymaga 1–5)
                            │
                            ├─ Faza 7  Pakowanie + CI  (częściowo równolegle)
                            ├─ Faza 8  Optymalizacja   ── szeregowa
                            └─ Faza 9  Dokumentacja    (równolegle z 7/8)
```

Ścieżka krytyczna = **Faza 0 → Faza 3 → Faza 6 → Faza 8 → Faza 9**.
Fazy 1, 2, 4, 5 **nie wydłużają kalendarza** — mieszczą się w cieniu Fazy 3.

Założenia czasowe `[Z]`: jedno zadanie implementacyjne 20–60 min wall-clock, runda przeglądu
10–20 min, pętla build/debug w C++ 1–4 h, **zimny build MediaPipe Bazelem 1,5–4 h na 12 wątkach**.

| Ścieżka | Faza 0 | Faza 3 | Fazy 6+8+9 | **Razem** |
|---|---|---|---|---|
| A | 3–10 dni | 2–5 dni | 3–7 dni | **8–22 dni ≈ 2–5 tyg.** |
| B | 4–12 dni | 8–20 dni | 4–8 dni | **16–40 dni ≈ 3–8 tyg.** |
| C | 4–12 dni | 10–24 dni | 4–9 dni | **18–45 dni ≈ 4–9 tyg.** |

**Te liczby zakładają, że użytkownik odblokowuje punkty z §5 w ciągu godzin.** Przy
odblokowywaniu raz dziennie kalendarz rośnie o liczbę zacięć × 1 dzień, czyli o **10–25 dni**.

---

## 5. Co i tak wymaga człowieka, nawet w trybie autonomicznym

Nieusuwalne:

1. **Instalacja toolchainu.** VS 2022 Build Tools / VS 2026 — instalator interaktywny,
   podniesienie uprawnień, akceptacja licencji. Qt Online Installer — **wymaga konta Qt**
   i akceptacji LGPL/komercyjnej `[W]`. MSYS2 + `pacman` oraz samorozpakowujący się
   OpenCV 3.4.10 (ścieżka A) `[W]`. Na tej maszynie **nie ma nic z tego** `[W]`.
2. **Nagranie ~300 klatek z dłonią prawdziwą kamerą.** W repo **nie ma ani jednego obrazu,
   na którym MediaPipe wykrywa dłoń** — sprawdziłem wszystkie 3 zdjęcia i wszystkie zrzuty
   UI, wszędzie `hands=0` `[W]`. Bez tego nie powstanie golden do testu parytetu.
3. **Fizyczny test property page sterownika DirectShow** — modalne okno sterownika,
   nieweryfikowalne headless.
4. **Odsłuch TTS**, w szczególności kilku liter pod rząd (klasa błędu, do której należała
   regresja pyttsx3 2.99).
5. **Ocena „czy GUI wygląda dobrze"** — porównanie zrzutu można zautomatyzować,
   ale werdykt jest ludzki. Plus **wykonanie nowych zrzutów** do dokumentacji
   (`AGENTS.md`: tylko prawdziwe zrzuty aplikacji).
6. **Decyzje licencyjne Qt**: linkowanie dynamiczne vs statyczne, co dokładnie dołączamy
   jako źródła, jaki tekst LGPL i gdzie `[W]`.
7. **Decyzje wokół pracy dyplomowej i podziału licencji** (`LICENSE` vs `LICENSE-docs`,
   czy `docs/Praca_Dyplomowa_Kamil_Rataj.pdf` zostaje nietknięty).
8. **Zmiana semantyki suwaków TTS** — pyttsx3 operuje w słowach/min, `QTextToSpeech`
   w zakresie −1…1 `[W]`. To widoczna dla użytkownika zmiana, wymaga jego decyzji.
9. **Zatwierdzanie `git push`, wydań i publikacji sum kontrolnych.**
10. **Ponowny pomiar spornych liczb FPS na prawdziwej kamerze** (§7).

Częściowo automatyzowalne, ale ryzykowne bez człowieka: wybór wersji OpenCV (3.4.10 dla
zgodności z MediaPipe vs 4.14 dla aplikacji), przycięcie `deps` w Bazelu, decyzja
o porzuceniu ścieżki A na rzecz B.

---

## 6. Czas kalendarzowy — wariant z użytkownikiem w pętli

| Ścieżka | 10–15 h/tydz. | 30 h/tydz. |
|---|---|---|
| A | 5–9 miesięcy | 3–5 miesięcy |
| B | 7–13 miesięcy | 4–7 miesięcy |
| C | 8–14 miesięcy | 4,5–7,5 miesiąca |
| D (bez portu) | 1–2 tygodnie | kilka dni |

Założenie `[Z]`: ~1 zadanie agentowe na 1–3 dni kalendarzowych łącznie z przeglądem
i testem po stronie użytkownika.

---

## 7. Wydajność — co naprawdę można ugrać

Pomiary wykonane 2026-09-09 na tej maszynie, model `models/gesture_recognizer_asl_0.task`,
640×480, XNNPACK:

| Pomiar | Wynik |
|---|---|
| Inferencja tryb `IMAGE`, 75 s ciągłego obciążenia | mediana **19,2–21,0 ms** `[W]` |
| Inferencja tryb `LIVE_STREAM`, jeden wątek sterujący, n=180 | mediana **25,7 ms** (p10 20,8 / p90 32,3) `[W]` — sam graf LIVE_STREAM dokłada ~5 ms |
| Narzut Pythona poza inferencją | **0,84 ms/klatkę** (maszyna bezczynna), 1,74 ms pod obciążeniem `[W]` |
| — rozkład (maszyna bezczynna) | `mp.Image` 0,475 + `draw_landmarks` 0,243 + `QImage` 0,032 + `.copy()` 0,030 + `cvtColor` 0,030 + budowa proto 0,027 + style 0,003 `[W]` |
| Start aplikacji | same importy Pythona **1,2–1,7 s** `[W]` + rozpakowanie 170 MB onefile do `%TEMP%` przy każdym uruchomieniu `[W]` |

**Sam język odbiera 0,8–1,7 ms z budżetu 20–26 ms na klatkę, czyli 4–8 %.** Inferencja
*już dziś* jest natywnym C++ (XNNPACK) pod cienką warstwą pybind11 — wheel MediaPipe zawiera
`_framework_bindings.cp310-win_amd64.pyd` (11,5 MB) ze statycznie wlinkowanym całym frameworkiem
`[W]`. Przy kamerze 30 FPS (a przy autoekspozycji 8–10 FPS, co README sam dokumentuje)
użytkownik **nie zobaczy różnicy w FPS** z przejścia na C++.

### 7.1 Sporny pomiar — hipoteza o skoku przez pętlę zdarzeń GUI

Uruchomiłem pełny pipeline aplikacji (`GestureRecognizerApp` + `CameraWorker`,
`QT_QPA_PLATFORM=offscreen`) z **syntetyczną** kamerą:

| Konfiguracja | pipeline FPS | `inference_ms` | porzucone klatki / 30 s |
|---|---|---|---|
| Obecna (`QueuedConnection` → wątek GUI) | 12–18 | 50–70 ms | 169–208 |
| Ta sama, z `DirectConnection` | 19–21 | 17,5–31 ms | 0 |

> ### ⛔ To jest hipoteza, nie wynik — i jest sprzeczna z pomiarami na żywo
>
> Powyższe liczby pochodzą z **syntetycznej kamery** (`time.sleep(1/30)` w atrapie `read()`),
> która oddawała 21,6 FPS zamiast 30. **Trzy pomiary na żywo na prawdziwej kamerze** wykonane
> na gałęzi `feature/threaded-camera-capture` dają obraz przeciwny: **pipeline 29–32 FPS przy
> kamerze 30 FPS, inferencja ~17 ms, 0–7 porzuconych klatek w ~30 s** `[W]`.
>
> Czyli na prawdziwym sprzęcie aplikacja **już dziś nadąża za kamerą**, a skok przez pętlę
> zdarzeń GUI **nie** kosztuje 30–40 ms na klatkę.
>
> Najprawdopodobniejsze wyjaśnienie rozbieżności `[Z]`: `time.sleep()` na Windows ma
> ziarnistość ~15,6 ms i w połączeniu z GIL-em zaburza szeregowanie wątków w harnessie —
> wąskim gardłem był mój test, nie aplikacja.
>
> **Status: hipoteza niepotwierdzona, wymaga ponownego pomiaru na prawdziwej kamerze.**
> Zostawiam ją w dokumencie świadomie, a nie usuwam, bo trzeba ją rozstrzygnąć przed
> jakąkolwiek decyzją o porcie. Uwaga: jeśli się **nie** potwierdzi — a pomiary na żywo na to
> wskazują — to wniosek dla portu jest **jeszcze mocniejszy**: aplikacja jest już ograniczona
> klatkowością kamery, więc **nie ma zapasu wydajności do odzyskania ani w Pythonie, ani w C++**.

### 7.2 Co C++ daje naprawdę

| Metryka | Dziś | Po porcie `[Z]` |
|---|---|---|
| Czas startu | 1,2–1,7 s samych importów + rozpakowanie 170 MB `[W]` | < 0,5 s |
| Rozmiar dystrybucji | `app/` **430 MB**, onefile **170 MB** `[W]` | 120–200 MB |
| Dostęp do GPU | **brak** — MediaPipe na Windows jest CPU-only `[W]` | LiteRT WebGPU/D3D12 albo ORT DirectML/CUDA `[W]` |
| FPS | — | **bez zmian** |
| Utrzymanie protobuf | łatany wheel + 178-liniowy skrypt builda `[W]` | znika — ale przychodzi Bazel/bzlmod (ścieżka A) |

---

## 8. Ryzyka, które mogą wysadzić szacunek

| Ryzyko | Prawd. `[Z]` | Wpływ |
|---|---|---|
| **Wrapper C++ LiteRT nie zbuduje się MSVC** — Google podaje `clang`, instrukcje CMake pomijają Windows `[W]` | wysokie | zabija ścieżkę B |
| **MediaPipe nie skompiluje się MSVC** — #6237 otwarte, #6238 niezmergowane `[W]` | wysokie | zabija ścieżkę A |
| **Bazel 7 EOL grudzień 2026**, hybryda WORKSPACE+bzlmod, brak drogi na Bazel 9 `[W]` | pewne | dług utrzymaniowy na lata |
| **Parytet numeryczny własnego grafu** — 13 etapów, gdzie odwrócona kolejność współrzędnych daje wynik „prawie dobry" | wysokie | **+2–6 tygodni** |
| **Brak klatek testowych z dłonią w repo** `[W]` | pewne | blokuje walidację parytetu |
| Link `linkstatic=True` wszystkich tasków przy 16 GB RAM `[W]` | średnie | OOM przy linkowaniu |
| Konflikt OpenCV 3.4.10 (MediaPipe) vs 4.14 (aplikacja) `[W]` | wysokie | godziny–dni |
| DirectML w trybie utrzymaniowym; Windows ML wyklucza GTX 1650 i UHD 630 `[W]` | pewne | zamyka ścieżkę GPU wariantu C w perspektywie lat |
| `windows-latest` = VS 2026 od czerwca 2026 `[W]`; `aqtinstall` bez wydania od ~15 mies. `[W]` | pewne / średnie | rozjazd CI z lokalnym buildem |
| Przepisanie dokumentacji EN+PL + nowe zrzuty; **praca dyplomowa opisuje wersję Pythonową** | pewne | PDF nie do ruszenia (`LICENSE-docs`) |
| Utrata funkcji: property page sterownika, gdyby ktoś zamienił OpenCV na Qt Multimedia `[W]` | średnie | regresja funkcjonalna |

---

## 9. Rekomendacja

### 9.1 Jeśli celem jest wydajność — nie przepisywać

Dane są jednoznaczne: sam język kosztuje **0,8–1,7 ms z ~22 ms** budżetu na klatkę (4–8 %),
a pomiary na żywo na prawdziwej kamerze pokazują **29–32 FPS przy kamerze 30 FPS** `[W]`,
czyli aplikacja **już jest ograniczona klatkowością kamery**. Nie ma zapasu, który port
mógłby odzyskać.

Kolejność działań, gdyby chodziło wyłącznie o wydajność i rozmiar:

1. **Rozstrzygnąć sporny pomiar z §7.1** ponownym testem na prawdziwej kamerze — 1 dzień.
   To jest jedyna otwarta niewiadoma po stronie wydajności.
2. **Przyciąć paczkę PyInstallera.** W dystrybucji siedzą `matplotlib` 11,6 MB, `PIL` 10,7 MB
   i `_sounddevice_data` `[W]` — bardzo prawdopodobnie niepotrzebne zależności przechodnie.
   To realny zysk na rozmiarze i czasie startu, za kilka dni pracy zamiast kilku miesięcy.
3. **Ewentualnie**: `mp.Image` 0,475 ms i `draw_landmarks` 0,243 ms to jedyne pozycje
   po stronie Pythona warte mikrooptymalizacji — łącznie ~0,7 ms/klatkę.

### 9.2 Jeśli port ma powstać z innego powodu

Praca dyplomowa, portfolio, nauka C++, chęć sięgnięcia po GPU — wtedy plan
[`plan.md`](plan.md) jest wykonalny. Kolejność:

1. **Faza 0 jako twarda bramka**, przed jakąkolwiek pracą nad GUI: dwa spike'y równolegle
   (LiteRT główny, MediaPipe/Bazel fallback), timebox 5 dni każdy. Kryterium: jedna klatka
   policzona w C++ zgodnie z Pythonem. Bez tego nie zaczynać niczego innego.
2. **Ścieżka B (LiteRT)**, nie A — mimo że A daje parytet numeryczny za darmo. Powód:
   A stoi na Bazelu 7 z EOL w grudniu 2026, hybrydzie WORKSPACE+bzlmod bez drogi na Bazel 9
   i otwartym defekcie MSVC bez zmergowanej poprawki `[W]`. Utrzymanie tego builda
   przechodzi na autora na stałe.
3. **Zachować OpenCV** dla przechwytywania i rysowania — Qt Multimedia nie otworzy property
   page sterownika, a to funkcja, którą aplikacja dziś ma `[W]`. Preferować **OpenCV 4.14.0**,
   nie 5.0.
4. **Wziąć `QTextToSpeech`** zamiast surowego COM/SAPI — usuwa cały workstream i przy okazji
   klasę błędów, do której należała regresja pyttsx3 2.99 `[W]`.
5. **Nie ruszać** `docs/Praca_Dyplomowa_Kamil_Rataj.pdf` ani podziału `LICENSE`/`LICENSE-docs`;
   port opisać jako osobną wersję.
6. **Tryb autonomiczny jest realny** (§4.4–4.5), ale kosztuje **1,6–2,2× więcej tokenów** niż
   praca z użytkownikiem w pętli i tak czy inaczej zatrzyma się **10–20 razy** na rzeczach
   z §5. Najlepszy stosunek kosztu do ryzyka daje tryb mieszany: agenty autonomicznie
   w fazach 1, 2, 4, 5, 7, 9 (moduły niezależne, dobrze zdefiniowane), a użytkownik w pętli
   w fazie 0 (toolchain) i fazie 3 (parytet numeryczny) — czyli dokładnie tam, gdzie leżą
   wszystkie punkty zacięcia.

### 9.3 Pytania, na które potrzebna jest odpowiedź przed startem

Pełna lista w [`plan.md`](plan.md) §10. Trzy najważniejsze:

1. **Jaki jest cel portu** — wydajność (wtedy: nie robić) czy praca dyplomowa / portfolio /
   GPU (wtedy: robić, ścieżką B)?
2. **Jedno repo czy dwa?** Praca dyplomowa i `LICENSE-docs` przemawiają za pozostawieniem
   wersji Pythonowej nietkniętej.
3. **Kto i kiedy nagra ~300 klatek testowych z dłonią?** Bez nich nie ma golden do parytetu
   i faza 3 nie ruszy.
