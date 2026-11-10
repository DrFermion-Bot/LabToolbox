# Third-party notices / 第三方组件声明

LabToolbox itself is MIT-licensed (see [README.md](README.md)). The packaged
Windows installer and macOS DMGs also distribute the components below. This file
is a human-readable summary; the authoritative license **texts** for the binary
runtime payloads are bundled inside the app itself:

| Bundled location | Files |
|---|---|
| `imagej/` (Windows: `_internal/imagej/`, macOS: `Contents/Frameworks/imagej/`) | `LICENSE-ImageJ.txt`, `LICENSE-OpenJDK.txt`, `NOTICE-OpenJDK.txt`, `NOTICE.txt`, `JRE-release.txt` |
| `third_party/` | `COPYING` (GPL-3.0), `COPYING.LESSER` (LGPL-3.0) — license texts for the `igor` package |

No bundled third-party component was modified; the only normalization is that
ImageJ's `ij.jar` and a separately downloaded Java runtime are placed together in
`imagej/` and that the Java 8 runtime shipped by ImageJ is replaced by Java 11
(Eclipse Temurin).

## Runtime payloads shipped in the installer / DMG

### ImageJ 1.54 — `imagej/ij.jar`

- Author/upstream: Wayne Rasband, US National Institutes of Health —
  <https://imagej.net/>, official distros at <https://wsr.imagej.net/>.
- ImageJ 1.x has historically been distributed as public-domain software;
  see <https://imagej.net/learn/> for the current licensing statement. The
  `ij.jar` is included **unmodified** from
  `https://wsr.imagej.net/distros/win/ij154-win-java8.zip` (the same jar is in the
  macOS distribution).
- In this project ImageJ is used as an optional external counting engine for the
  `livedead_cellcounter` module (ImageJ `-batch` macro mode on the desktop JVM,
  not JVM-headless mode - ImageJ 1.x cannot execute `run()` commands without a
  desktop toolkit - using `Analyze Particles`; macro
  `scripts/imagej/count_livedead.ijm`).
- Please cite: Schneider CA, Rasband WS, Eliceiri KW. *NIH Image to ImageJ: 25
  years of image analysis.* Nature Methods 9, 671–675 (2012).
  <https://doi.org/10.1038/nmeth.2089>
- Exact download URLs and SHA-256 hashes of the archives used for each build are
  recorded in the generated `imagej/NOTICE.txt` inside the app.

### Eclipse Temurin 11 JRE — `imagej/jre/`

- Upstream: Eclipse Adoptium / AdoptOpenJDK — <https://adoptium.net/>.
- License: GNU General Public License version 2, with the Classpath Exception
  (GPLv2 + CPE). Full text: `imagej/LICENSE-OpenJDK.txt`; notices:
  `imagej/NOTICE-OpenJDK.txt`.
- The runtime is downloaded at **build time** by `scripts/fetch_imagej.py` from
  the official Adoptium API (Windows x64, macOS x64, macOS arm64) and embedded.
  The packaged app never downloads Java at run time.
- The macOS build uses a platform-native runtime for each architecture
  (x86_64 for Intel, arm64 for Apple Silicon); the JRE shipped inside the
  official ImageJ macOS zip is x86_64-only and would not run natively on Apple
  Silicon.

### `igor` 0.3 — Bruker `.ibw` reader (Python)

- Upstream: <https://github.com/wking/igor> (installed by the build from
  `git+https://github.com/wking/igor`; the PyPI package named `igor` is unrelated
  and empty — do not use it).
- License: GNU Lesser General Public License, version 3 or later (LGPL-3.0+).
  License texts are bundled at `third_party/COPYING` and
  `third_party/COPYING.LESSER`.
- Bundled unmodified as pure Python. Because it is distributed as source-level
  Python inside the application, users may replace it with a modified version
  (the files live inside the installed app directory); sources are available at
  the upstream URL.

## Python dependencies (bundled into the application)

The release bundles a CPython 3.11 runtime and the project's dependencies; the
build workflow installs them from PyPI. License identifiers as declared by the
installed distributions:

| Package | License | Upstream |
|---|---|---|
| Python / CPython | PSF-2.0 | <https://www.python.org/> |
| Tcl/Tk (tkinter) | BSD-style | <https://www.tcl.tk/> |
| numpy | BSD-3-Clause (plus 0BSD, MIT, Zlib, CC0-1.0 components) | <https://numpy.org/> |
| scipy | BSD-3-Clause | <https://scipy.org/> |
| matplotlib | PSF-based (bundles fonts/libraries under OFL, Apache-2.0, MIT, BSD, FTL; full notice inside the package) | <https://matplotlib.org/> |
| pandas | BSD-3-Clause | <https://pandas.pydata.org/> |
| openpyxl | MIT | <https://openpyxl.readthedocs.io/> |
| statsmodels | BSD-3-Clause | <https://www.statsmodels.org/> |
| opencv-python (OpenCV) | Apache-2.0 (official wheels also include an FFmpeg build under LGPL for video I/O) | <https://opencv.org/> |
| Pillow | MIT-CMU (HPND) | <https://python-pillow.org/> |
| tifffile | BSD-3-Clause | <https://github.com/cgohlke/tifffile> |
| PyYAML | MIT | <https://pyyaml.org/> |
| lxml | BSD-3-Clause | <https://lxml.de/> |
| psutil | BSD-3-Clause | <https://github.com/giampaolo/psutil> |
| python-dateutil | Apache-2.0 / BSD-3-Clause | <https://dateutil.readthedocs.io/> |
| tzdata | Apache-2.0 | <https://github.com/python/tzdata> |
| certifi | MPL-2.0 | <https://certifi.io/> |
| igor | LGPL-3.0+ | see above |

Full license texts for the Python packages are available from each upstream
project and from the packages' metadata (PyPI / GitHub).

## Build-time tools

- **PyInstaller 6.x** — GPL-2.0-or-later with a special exception that allows
  building and distributing non-free programs, including the bootloader embedded
  in this application. <https://pyinstaller.org/>
- **Inno Setup 6** — freeware installer builder by Jordan Russell / Martijn
  Laan. The generated Windows installer includes the Inno Setup runtime, which
  the Inno Setup license permits; see <https://jrsoftware.org/isinfo.php>.
- **Inno Setup Chinese (Simplified) messages** — user-contributed translation by
  Zhenghan Yang (Kira), `installer/languages/ChineseSimplified.isl`, based on
  <https://github.com/kira-96/Inno-Setup-Chinese-Simplified-Translation>. The
  translation file retains the upstream header and attribution.
- **GitHub Actions runner images** (build environment only, not distributed).

## Application assets

- `assets/labtoolbox.png|ico|icns` — placeholder application icons generated by
  `scripts/build_icons.py` for this project; replace them with your own artwork
  (they are only used as the app/installer icon). MIT, same as the project.
- The app does not bundle stock photography or third-party fonts beyond those
  already shipped by matplotlib/tk.