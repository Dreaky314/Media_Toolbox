# MediaToolkit · 影音工具箱

[简体中文](README.md) | English

A clean Windows desktop toolkit that turns two tedious media-organization chores into one click each:

- **Anime Organizer** — batch-rename per-episode video folders into a tidy, zero-padded archive
- **Segment Merger** — losslessly concatenate cached `.ts` streaming segments into a single video file

Built with **PySide6 / Qt**. The business logic is fully decoupled from the UI and can be scripted on its own.

![Anime Organizer](docs/screenshot-rename.png)

![Segment Merger](docs/screenshot-merge.png)

---

## Table of Contents

- [Features](#features)
  - [Anime Organizer](#anime-organizer)
  - [Segment Merger](#segment-merger)
  - [Settings](#settings)
- [Getting Started](#getting-started)
- [Tech Stack](#tech-stack)
- [Project Layout](#project-layout)
- [Development & Testing](#development--testing)
- [Building an EXE](#building-an-exe)
- [About SmartScreen](#about-smartscreen)
- [Gotchas We Hit](#gotchas-we-hit)
- [License](#license)

---

## Features

### Anime Organizer

Put each episode in a numerically named subfolder (`1` / `02` / `12` …) and the app will:

- Scan every **digit-named** subfolder under the root directory
- Pick one video per episode folder as the main file (first by filename, or the largest by size)
- Rename it to a zero-padded episode number (`01.mp4`); padding width is derived from the highest
  episode number, or can be pinned to 2 / 3 digits
- Three processing modes:
  - **Copy** to a target directory (keeps the originals)
  - **Move** to a target directory (saves disk space)
  - **Rename in place** (creates no new files)
- Optional *"also rename the source file inside the episode folder"*, matching the original script
- Full preview table before running: episode, source file, new name, size, status
- Automatically flags **folders with no video**, **existing targets**, and
  **intra-batch name collisions** (e.g. both `1` and `01` present)
- Non-numeric folders (`SP`, `extras`, …) are skipped and listed in the log
- Double-click a row to open that episode's folder in Explorer

### Segment Merger

- Three import paths: **Add files**, **Add folder** (auto-recurses one level when no segments are found),
  and **Import from m3u8**
- Reorder with move up / move down / delete / reverse — list order is concatenation order
- Output formats **MP4 / TS / MKV**; switching format rewrites the output extension automatically
- Three encoding modes:

  | Mode | Arguments | When to use |
  | --- | --- | --- |
  | Stream copy | `-c copy` | Fastest, lossless; all segments must come from the same stream |
  | High-quality re-encode | `libx264 -crf 18` | Best compatibility, slower |
  | Target bitrate | `libx264 -b:v 8M` | When you need to control file size |

- Live progress parsed from ffmpeg stats: **percentage / processed duration / speed**
- Automatically appends `aac_adtstoasc` and `+faststart` for MP4 output
- *"View command"* shows the exact ffmpeg command line being executed
- m3u8 import warns about **encryption tags**, missing `#EXT-X-ENDLIST`, and **missing segments**

### Settings

- The ffmpeg path can be **typed or pasted directly**; click *Save path* to persist it to `config.json`
- Also supports file browsing, one-click auto-detect, and a availability check
- Lookup order: manual path → `<app>/ffmpeg/bin` → system `PATH`
- ffmpeg is **not required** if you only use the Anime Organizer

![Settings](docs/screenshot-settings.png)

---

## Getting Started

### Requirements

| Item | Requirement |
| --- | --- |
| OS | Windows 10 / 11 (64-bit) |
| Python | 3.9+ (developed on 3.14.7) |
| ffmpeg | Only needed for the Segment Merger |

### Install & Run

**Double-click `启动.bat`** — it launches `app_qt.py` through the project-local `.venv`
using `pythonw`, so it never runs the packaged `.exe` and **never triggers SmartScreen**.

Create the virtual environment once:

```bat
python -m venv --without-pip --system-site-packages .venv
.venv\Scripts\python.exe -m pip install PySide6
```

> `--without-pip --system-site-packages` works around `ensurepip` write restrictions in
> sandboxed environments and reuses the global pip. The resulting `.venv` contains only
> PySide6 and **does not touch your global Python installation**.

Start it manually afterwards:

```bat
.venv\Scripts\pythonw.exe app_qt.py
```

---

## Tech Stack

| Layer | Choice | Notes |
| --- | --- | --- |
| UI | PySide6 (Qt 6) | Vector rendering with anti-aliasing and composition; HiDPI handled by Qt |
| Styling | QSS | Centralized palette and widget styling |
| Logic | Python standard library | `core/` depends on no UI toolkit and can be scripted directly |

The UI started out on Tkinter. On Windows, almost all of Tk's resize cost went into
repainting the entire window. Measured on the same machine at 150% scaling:

| | Tkinter | Qt |
| --- | --- | --- |
| Anime Organizer resize | 231 ms/step | **17.4 ms/step** |
| Segment Merger resize | 142 ms/step | **18.7 ms/step** |
| Maximize | 266 ms | **47 ms** |

---

## Project Layout

```
media_toolkit/
├─ app_qt.py                Application entry point
├─ 启动.bat                 Double-click launcher (no .exe involved)
├─ build_exe.py             Package into an .exe
├─ core/                    Logic layer — UI-agnostic, scriptable
│  ├─ config.py             App dir, config.json, resource path resolution
│  ├─ ffmpeg.py             ffmpeg/ffprobe discovery, validation, duration probing
│  ├─ m3u8.py               m3u8 playlist parsing
│  ├─ merge.py              Concat list, command building, progress-aware runner
│  ├─ rename.py             Episode scanning, name planning, copy/move runner
│  └─ osutil.py             Open folder / reveal file (multi-level fallback)
├─ qtui/                    Qt UI layer
│  ├─ theme.py              Palette + global QSS + fonts
│  ├─ widgets.py            Cards, badges, segmented control, stat chips, icons, log panel
│  ├─ main_window.py        Main window: sidebar + page stack + shared log panel
│  ├─ page_rename.py        Anime Organizer page
│  ├─ page_merge.py         Segment Merger page
│  └─ page_settings.py      Settings page
├─ assets/                  Icon assets (app.ico / check.svg)
├─ docs/                    Screenshots
└─ tools/                   Developer scripts
   ├─ selftest.py           Logic-layer unit tests (57 checks)
   ├─ e2e_merge_test.py     End-to-end merge with a real ffmpeg
   ├─ qt_smoke.py           Qt UI smoke test + screenshots (56 checks)
   ├─ qt_perf.py            Qt resize performance benchmark
   └─ make_icon.py          Regenerate the multi-size square icon with Qt
```

---

## Development & Testing

```bat
:: Logic layer
python tools\selftest.py           :: unit tests (57 checks)
python tools\e2e_merge_test.py     :: end-to-end with a real ffmpeg

:: Qt UI
.venv\Scripts\python.exe tools\qt_smoke.py            :: smoke test (56 checks)
.venv\Scripts\python.exe tools\qt_smoke.py --shots    :: also export screenshots
.venv\Scripts\python.exe tools\qt_perf.py             :: resize performance comparison
```

- All tests are hand-rolled assertions in the `unittest` spirit — **no pytest required**.
- Test data is written to `.selftest_tmp/` inside the project and **never touches your real media**.

---

## Building an EXE

```bat
.venv\Scripts\python.exe build_exe.py
```

Output goes to `dist/影音工具箱/`, roughly **97 MB** (Qt runtime included; unused modules such as
WebEngine are excluded).

ffmpeg is large (~100 MB per binary) and is **not** bundled by default — the app looks it up on
`PATH`. To bundle it:

```bat
.venv\Scripts\python.exe build_exe.py --with-ffmpeg "D:\ffmpeg\bin\ffmpeg.exe"
```

`assets/app.ico` ships **seven sizes** (16/24/32/48/64/128/256) and can be regenerated with
`tools/make_icon.py`.

---

## About SmartScreen

The PyInstaller-built `.exe` is **not code-signed**, so Windows shows
*"Microsoft Defender SmartScreen prevented an unrecognized app from starting"* on first run.
Three options:

1. Click **"More info" → "Run anyway"** (once per newly built binary)
2. **Use `启动.bat` instead** (recommended) — it runs the source, not an executable, so the
   prompt can never appear
3. Buy a **code-signing certificate** and sign the binary (the only way to remove the prompt at the root)

If you are on Windows 11 with **Smart App Control** enabled, it is stricter than SmartScreen and
will block unsigned apps outright — adjust it under *Windows Security → App & browser control*,
or use `启动.bat` as well.

---

## Gotchas We Hit

### Qt

- **`url()` in QSS needs an absolute path with forward slashes.** Resource-style paths such as
  `:/qt/...` fail with `Cannot open file`. `theme.asset_path()` resolves absolute paths and omits
  the whole rule when the file is absent.
- **A global `QWidget { background: ... }` rule paints every child** (QLabel included). Backgrounds
  are therefore only set on containers that carry an `objectName`.
- **Custom widgets must sync their internal state when values change.** `Segmented.set()` only
  updates visuals; callers changing the value must update the control too, or UI and state drift apart.
- **Call `setBrush(Qt.NoBrush)` before drawing outlined circles**, otherwise they come out filled.
- **Cross-thread callbacks must go through signals.** `core/` callbacks run on worker threads;
  everything is marshalled onto the UI thread via `QObject` signals.
- **`QFontDatabase` requires a live `QApplication`.**
- **Resource paths change once packaged.** PyInstaller's `--add-data` lands under `_internal/` in
  onedir mode. Resolution goes through `core/config.resource_path()`, checking
  `sys._MEIPASS` → app dir → `app dir/_internal`.
- **The window icon must be set on the window itself.** Setting only
  `QApplication.setWindowIcon()` leaves an already-created window's `windowIcon()` empty.

### General

- **Never pass `CREATE_NO_WINDOW` to `explorer.exe`.** It makes Explorer fail during DLL
  initialization with *"explorer.exe - Application Error (0xc0000142)"*. That flag is only meant
  for console programs like ffmpeg. `core/osutil.py` only redirects child stdio and passes no
  creation flags.
- **Do not save Chinese text as UTF-8 inside a `.bat`.** `cmd.exe` parses batch files using the
  system ANSI codepage (GBK on Simplified Chinese Windows); UTF-8 Chinese decodes into mojibake and
  corrupts the surrounding line. `启动.bat` is therefore **ASCII-only**.
- **ffprobe cannot report a total duration for TS concat lists** — it always returns
  `duration=N/A` for MPEG-TS. Workaround: sum `#EXTINF` values for m3u8; probe and sum in parallel
  for small lists; sample and extrapolate for large ones.

---

## License

MIT License
