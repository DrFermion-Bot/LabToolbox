# LabToolbox 🧪

**Lab Toolbox** — A modular, extensible toolkit for biomedical lab data analysis, built from Ruinong Pan's research scripts (F-DLC antibacterial surfaces, bacterial adhesion, LIPSS characterization).

> **中文版 README**: [README.md](README.md) | **English**: [README_EN.md](README_EN.md)

## 📦 Modules

| Module | Function | Dependencies |
|---|---|---|
| `growth_curve` | Bacterial growth curve fitting & OD/CFU analysis (E. coli, S. aureus) | numpy, scipy, matplotlib |
| `lipss_dloa` | LIPSS period / orientation-angle analysis from SEM images (DLOA) | numpy, scipy, opencv, matplotlib |
| `xdlvo` | XDLVO theory bacterial adhesion prediction (contact angle → SFE → ΔG) | numpy, scipy |
| `livedead` | LIVE/DEAD fluorescence statistics (viability %, two-way ANOVA) | pandas, statsmodels, openpyxl |
| `livedead_cellcounter` | LIVE/DEAD fluorescence image cell counting (repeat/time/area, summary + ANOVA) | numpy, opencv, Pillow |
| `contact_angle` | Contact angle / surface free energy (OWRK) | numpy, scipy |
| `surfmetrics` | AFM/SEM height map → 3D + roughness (Sa/Sq/Sz) + surface area (Sdr) | numpy, scipy, tifffile, igor* |
| `contact_schematic` | **AFM pipeline end step**: measured geometry (period / groove depth / pillar height) → 3D bacteria-on-texture schematic + contact-geometry figure | numpy, scipy, matplotlib, igor* |
| `semtexture` | **Coupon-to-coupon consistency**: SEM period / orientation / coherence + tile-based ordered-area map + debris density + batch criteria (period CV, orientation SD, ICC) | numpy, scipy, pandas, matplotlib, Pillow |

> *`igor` (Bruker .ibw direct read) must be installed from GitHub: `pip install "igor @ git+https://github.com/wking/igor"` (the PyPI `igor` package is an empty shell — do not install).

📚 **Per-module implementation documentation** (algorithms, formulas, parameters, limitations, references — English + 中文): [docs/modules/README.md](docs/modules/README.md).

## 🖥️ GUI (tkinter, zero extra dependencies)

```
🧪 Lab Toolbox
┌──────────────────────────────────────────────────────┐
│ [📈 Growth Curve] [🔬 LIPSS/DLOA] [🧫 XDLVO] [🦠 LIVE/DEAD] [💧 Contact Angle] [🔬 Cell Count] [🏔️ Surface Morphology] │
│                                                      │
│  Each tab = one module's config panel                │
│  (pick file / fill params → click Run)               │
└──────────────────────────────────────────────────────┘
```

- **Bilingual UI**: toggle 中文 / English with the button in the top-right corner
- Launch: `python -m labtoolbox.gui`
- Results auto-save to the output directory, with a popup on completion

## 🚀 Quick Start

```bash
pip install -e .
# or with image-processing dependencies
pip install -e ".[image]"

# 🖥️ GUI (recommended)
python -m labtoolbox.gui

# Command line
labtoolbox --help
labtoolbox growth-curve --data data/growth_Ecoli.xlsx
labtoolbox lipss-dloa --folder data/sem_images/
labtoolbox xdlvo --angles '{"theta_diiodo":48.2,"theta_water":72.3,"theta_form":61.5}'
labtoolbox livedead --file data/livedead.xlsx
labtoolbox contact-angle --theta1 72.3 --theta2 48.2
labtoolbox surfmetrics --folder "AFM data dir" --output out   # batch: direct .ibw read
labtoolbox surfmetrics --file sample.ibw                     # single file
labtoolbox livedead-cellcounter examples/livedead_counter_demo --output out  # LIVE/DEAD image counting (ImageJ)
labtoolbox schematic --input "AFM data dir" --out out --label "515 nm"      # contact-geometry schematic (AFM end step)
```

## 📥 Downloads & installation

One desktop app per platform. The installer and the macOS DMGs **bundle ImageJ 1.54
and a private Java runtime**, so no Python / ImageJ / Java installation is required
and nothing is downloaded on first use.

| Platform | File | Notes |
|---|---|---|
| 🪟 Windows 10/11 (x64) | `LabToolbox-Setup-<version>.exe` | Installer (recommended): Chinese/English wizard, uninstaller |
| 🪟 Windows 10/11 (x64) | `LabToolbox-Windows-x64.zip` | Portable: unzip and run, no install |
| 🍎 macOS 11+ · Apple Silicon | `LabToolbox-macOS-AppleSilicon.dmg` | Native for M1/M2/M3/M4 |
| 🍎 macOS 11+ · Intel | `LabToolbox-macOS-Intel.dmg` | Native for Intel Macs |

> ⚠️ **These builds are unsigned** — no Windows code-signing certificate and no
> Apple Developer ID / notarization. On Windows, SmartScreen shows *"Windows
> protected your PC"* → **More info → Run anyway**. On macOS, first launch needs
> **Control-click → Open**, or run
> `xattr -dr com.apple.quarantine /Applications/LabToolbox.app`.
> Full steps, troubleshooting and how to add signing later:
> **[docs/INSTALL.md](docs/INSTALL.md)**.

Downloads: <https://github.com/DrFermion/LabToolbox/releases>

### Bundled ImageJ (nothing to install)

The LIVE/DEAD cell counter defaults to classic **ImageJ 1.54** (`Analyze Particles`).
The packaged app embeds `ij.jar`, a native **Eclipse Temurin 11 JRE** (x86_64 on
Intel, arm64 on Apple Silicon) and the read-only macro
`scripts/imagej/count_livedead.ijm` — so counting works offline and out of the box.
ImageJ 1.54 was verified to give identical counts on Java 11 and Java 8. Advanced
users can override the engine location with the `LABTOOLBOX_IMAGEJ_DIR`
environment variable. License/provenance: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 🧩 Modular Design (built for extension)

```
labtoolbox/
├── common/          # Shared IO, fitting, statistics
├── growth_curve/    # Growth curves
├── lipss_dloa/      # LIPSS/DLOA
├── xdlvo/           # XDLVO
├── livedead/        # LIVE/DEAD
├── livedead_cellcounter/  # LIVE/DEAD fluorescence image counting
├── contact_angle/   # Contact angle / SFE
├── i18n.py          # zh/en translations
├── gui.py           # tkinter GUI
└── cli.py           # Unified CLI (register new subcommands here)
```

**Adding a new module**: create a package under `labtoolbox/` (e.g. `raman/`), implement the `run(config) -> dict` interface, and register one line in `cli.py`. No changes needed to other modules.

## 🔬 Data Notes

- Raw data stays in OneDrive shared folders (not committed to the repo)
- `data/examples/` contains sanitized example data
- `examples/` holds the example tables opened by the GUI's "Open example table" buttons (growth curve / LIVE/DEAD)
- All modules accept Excel/CSV input; figures output to `output/`

## 🛠️ Building from Source

```bash
pip install -e ".[build]"        # pyinstaller + igor (Bruker .ibw direct read)
python scripts/fetch_imagej.py   # ImageJ 1.54 + native Temurin 11 JRE -> vendor/imagej
pyinstaller labtoolbox.spec --noconfirm
python scripts/verify_bundle.py  # check dist contains imagej/ij.jar, JRE, macro, igor
```

The macOS `Info.plist` version is taken from the git tag (`APP_VERSION`) or
`pyproject.toml` — it is not hardcoded. App icons are replaceable:
`assets/labtoolbox.ico` / `assets/labtoolbox.icns` (regenerate with
`python scripts/build_icons.py`).

Cross-platform builds are automated via GitHub Actions on every `v*` tag push
(and manual `workflow_dispatch` for build-only runs):

| Job | Runner | Output |
|---|---|---|
| Windows x64 | `windows-latest` | `LabToolbox-Setup-<version>.exe` + `LabToolbox-Windows-x64.zip` |
| macOS Intel | `macos-15-intel` | `LabToolbox-macOS-Intel.dmg` |
| macOS Apple Silicon | `macos-15` (arm64) | `LabToolbox-macOS-AppleSilicon.dmg` |

Builds are unsigned (no Authenticode, no Developer ID / notarization); see
[docs/INSTALL.md](docs/INSTALL.md) for the user-facing workarounds and how to add
signing to the workflow later.

## 📄 License

MIT (pending)

---

*Created by Ruinong Pan (DrFermion) — University of Dundee, Biomedical Engineering*
