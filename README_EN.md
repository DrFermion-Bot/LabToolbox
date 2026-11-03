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
| `semtexture` | **Coupon-to-coupon consistency**: SEM period / orientation / coherence + tile-based ordered-area map + debris density + batch criteria (period CV, orientation SD, ICC) | numpy, scipy, pandas, matplotlib, Pillow |

> *`igor` (Bruker .ibw direct read) must be installed from GitHub: `pip install "igor @ git+https://github.com/wking/igor"` (the PyPI `igor` package is an empty shell — do not install).

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
```

## 📦 Releases (one-click install)

Pre-built binaries for **Windows** and **macOS** are available in [Releases](https://github.com/DrFermion/LabToolbox/releases) — no Python environment needed:

| Platform | Package | Usage |
|---|---|---|
| 🪟 Windows | `LabToolbox-Windows.zip` | Unzip → double-click `LabToolbox.exe` |
| 🍎 macOS | `LabToolbox-macOS.zip` | Unzip → drag `LabToolbox.app` into Applications |

> Note: macOS may warn "unidentified developer" (free-signed builds) — right-click → Open to launch.

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
pip install pyinstaller numpy scipy matplotlib pandas openpyxl statsmodels opencv-python Pillow
pyinstaller labtoolbox.spec --noconfirm
```

Cross-platform builds (Windows + macOS) are automated via GitHub Actions on every `v*` tag push.

## 📄 License

MIT (pending)

---

*Created by Ruinong Pan (DrFermion) — University of Dundee, Biomedical Engineering*
