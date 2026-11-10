# livedead_cellcounter — Automated LIVE/DEAD fluorescence counting / LIVE/DEAD 荧光图像细胞计数

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

This module automates counting of LIVE/DEAD fluorescence micrographs organised in a **replicate → time point → area** folder hierarchy and turns the counts into viability statistics. Each field is imaged in two channels: green (`g`, SYTO 9 → live, membrane-intact cells) and red (`r`, propidium iodide → dead, membrane-damaged cells); the module pairs the two files of the same field and reports live/dead counts, pooled viability, a stacked bar chart and a two-way ANOVA. It replaces manual ImageJ clicking and is the image-side front end of the [`livedead`](livedead.md) statistics module. It is available from the GUI (tab **🔬 LIVE/DEAD Cell Count**), the unified CLI (`labtoolbox livedead-cellcounter`) and the Python API.

Two counting engines exist:

* **`ImageJ` (default, reference methodology)** — classic ImageJ 1.54 headless batch with a project macro: adaptive threshold = histogram-mode background + 40, optional brightest-channel fallback, `Analyze Particles` size filter. The packaged desktop app bundles ImageJ 1.54 + a native Temurin 11 JRE (nothing to install); a source checkout discovers a local ImageJ automatically (see *Bundled vs source-checkout ImageJ* below).
* **`opencv` (legacy, troubleshooting only)** — the original Python/OpenCV fixed-threshold + watershed engine, kept for regression comparison. The project has standardised methodology on the ImageJ engine (README, 2026-09-11) and no longer runs dual-engine cross-validation.

### Input folder structure and filenames

```
<root>/
├── repeat1/            # biological replicate (regex: ^repeat\s*\d+$, case-insensitive)
│   ├── 1h/             # time point (regex: \d+h$)
│   │   ├── 1-g1.tif    # area 1, green = live, field 1
│   │   ├── 1-r1.tif    # area 1, red   = dead, field 1
│   │   ├── c-g1.tif    # control area, green
│   │   └── c-r1.tif    # control area, red
│   └── 3h/
├── repeat2/
└── repeat3/
```

* Filename grammar: `{area}-{channel}{number}.{ext}`, parsed by `AREA_PATTERN = ^([0-9]+|c)[-_]?([rg])(\d+)$` (case-insensitive). Separators may be `-` or `_` or absent; `c` (any case) means control, other integers are test areas; `g`/`r` are the channels; `number` is the field index.
* Accepted extensions by the scanner: `.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg`, `.bmp`. **The ImageJ macro itself only processes `.tif`** — non-TIFF files get count 0 from the ImageJ engine (see limitations).
* A g/r pair is matched on `(area, number)`; the green file supplies `live`, the red file supplies `dead`. A missing channel yields 0 for that count.
* Bundled demo: `examples/livedead_counter_demo/` (3 repeats × 1h/3h × Control/Area1 × 2 fields, synthetic 200×200 images) with `examples/README_livedead_counter.md`.
* `skip_repeats=("repeat2",)` removes whole replicate folders before counting (for incomplete/invalid repeats).

### Entry points

| Entry point | How it is used |
|---|---|
| GUI tab **🔬 LIVE/DEAD Cell Count** | Image root folder, counting-engine selector (`imagej` / `opencv`) with an ImageJ status line, minimum particle size, output directory; the roundness/green/red entries are sent **only** when `opencv` is selected |
| CLI `labtoolbox livedead-cellcounter FOLDER` | `--output`, `--backend imagej\|opencv`, `--min-size`, `--skip-repeats`, `--qc-dir` |
| Python API | `labtoolbox.livedead_cellcounter.run(folder, output_dir, area_um2, backend, skip_repeats, **engine_kwargs)`; `LiveDeadCellCounter(engine=...).report(...)` for finer control |

```bash
labtoolbox livedead-cellcounter path/to/root --output results \
    --backend imagej --min-size 3 --qc-dir results/qc
```

Option notes: `--min-size` falls back to the engine default when omitted (ImageJ 3 px², OpenCV 10 px); `--qc-dir` is honoured only by the ImageJ engine (the CLI prints a warning and ignores it for `opencv`); errors surface through the unified CLI as a non-zero exit with a message. The GUI status line shows the discovered ImageJ directory or *“not found (set LABTOOLBOX_IMAGEJ_DIR)”*.

### Outputs

`LiveDeadCellCounter.report(root, output_dir="output", verbose=True, skip_repeats=())` writes:

| Output | Content |
|---|---|
| `livedead_raw_counts.csv` | One row per image pair: `repeat`, `time`, `area`, `num`, `g_image`, `r_image`, `live`, `dead`, `total`, `dead_rate` (plus `error` for failed pairs) |
| `livedead_summary.csv` | Per `area_label` × `time`: `live_mean/sd`, `dead_mean/sd`, `total_mean/sd`, `dead_rate_mean`, `n`, `live_pooled`, `dead_pooled`, `viability_pct` |
| `livedead_anova.csv` | Two-way ANOVA table (`factor`, `sum_sq`, `df`, `F`, `PR(>F)`) or the per-time one-way fallback |
| `livedead_cell_count.png` | Stacked bar chart: dead (red) below, live (green) above, per area × time, with SD error bars |

`run(folder, output_dir="output", area_um2=None, backend="imagej", skip_repeats=(), **engine_kwargs)` returns the dict `{"raw", "raw_csv", "summary", "summary_csv", "anova", "anova_csv", "figure"}`. The `area_um2` parameter is accepted but **never used** — no CFU/cm² or density conversion is performed anywhere.

### End-to-end pipeline

0. **Select the engine** — `backend="imagej"` (default) builds an `ImageJEngine`; `backend="opencv"` builds the legacy `CellCounterEngine`. `run()` filters the engine kwargs: only `imagej_dir`, `min_size`, `max_size`, `bg_offset`, `qc_dir` reach `ImageJEngine`; the OpenCV engine accepts its full parameter set. If the ImageJ runtime or macro cannot be found, the ImageJ engine raises `FileNotFoundError` listing the candidates — there is **no automatic fallback**; pass `backend="opencv"` explicitly.
1. `scan_structure(root)` — list `repeat*` folders (numeric sort), time folders matching `\d+h$`, matching image files; warn if fewer than 3 repeats; apply `skip_repeats`; raise if nothing is found.
2. `count_all(structure)` — for each repeat/time: group images by `(area, number)`, call `engine.count_live_dead(g_img)` → `live = counts["green"]` and `engine.count_live_dead(r_img)` → `dead = counts["red"]`; accumulate rows (failures become NaN + `error`), print progress every 20 pairs; compute `dead_rate = dead/total`.
3. `summarize(df)` — relabel `c → Control`, `n → Area n`; aggregate mean/SD per area×time and add the **pooled** `Σlive/Σtotal × 100` viability.
4. `anova(df, value_col="live", log10=True)` — two-way ANOVA on log10-transformed live counts.
5. `plot(df)` — stacked bars + SD error bars + ANOVA annotation (see quirks).
6. Save raw counts, summary, ANOVA and figure.

### Counting algorithms

#### ImageJ engine (default): macro `count_livedead.ijm`

The engine writes a 5-line UTF-8 argument file (input directory, output CSV, QC directory, min particle size, max particle size) and runs classic ImageJ headless:

```
java -cp <ImageJ>/ij.jar ij.ImageJ -batch <macro> <argsfile>
```

with `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8` (so Chinese paths work; ImageJ CLI arguments themselves cannot carry them). The whole directory is processed in one batch and the per-file counts are cached, so one JVM start serves all images of a folder; subprocess timeout is 1800 s.

Per image the macro:

1. Opens the TIFF and resets the spatial calibration (`Set Scale... distance=0`), which strips bogus Image-Pro calibration (e.g. inch/px) that would otherwise break the particle-size filter.
2. For RGB images: splits channels, reads each channel's maximum (`chanMax`); decides the *named* channel from the filename (`-g` → green, otherwise red). **Channel-trap rule:** if the named channel's maximum is `< 30` (no real signal), it counts the brightest channel instead and records `chan_used = auto-bright`.
3. Threshold = background histogram mode + 40 (`bgMode` + 40) applied to 255, `Convert to Mask`.
4. `Analyze Particles size=<min>-<max> px show=Nothing add`; count = number of results. Defaults: 3–500 px² (settable through `ImageJEngine(min_size, max_size)`), `bg_offset` is stored but the macro hard-codes +40.
5. Optional QC mode (`qc_dir`): saves `<stem>_qc.png` with every counted particle circled in blue/magenta and numbered, for troubleshooting under-/over-counting.
6. Back in Python, the per-file count is assigned to `green` or `red` from the filename (`[-_]?([rg])[_-]?\d+`); `count_live_dead_pair(g_img, r_img)` is available for explicit pairing when names are ambiguous.

#### Bundled vs source-checkout ImageJ

`ImageJEngine` locates its runtime in this order (`imagej_dir_candidates()`, `find_imagej()`, `find_macro()`):

1. **Environment override** `LABTOOLBOX_IMAGEJ_DIR` — may point at an ImageJ folder containing `ij.jar`, or at a bundle root containing `imagej/` and `scripts/`.
2. **Packaged bundle roots** (only when frozen): `<bundle>/imagej`, where `<bundle>` is `sys._MEIPASS` (PyInstaller 6 Windows onedir `_internal`; macOS `.app` `Contents/Frameworks`), the executable directory / its `_internal`, and the `.app` `Contents/Resources|Frameworks` variants.
3. **Repository bundle**: `<repo>/imagej`, `<repo>/vendor/imagej`.
4. **Legacy local installs**: `E:/ImageJ/ImageJ`, `F:/ImageJ/ImageJ`, `C:/Users/PC/Downloads/ImageJ`.

Java is taken from the ImageJ folder when present — Windows: `jre/bin/java.exe`, `jre/bin/java`, `jre/Contents/Home/bin/java`, `bin/java.exe`, `bin/java`; macOS: `jre/Contents/Home/bin/java` first, then the other layouts. The `java` on `PATH` is a development fallback only (a packaged build always carries its own JRE).

The macro is **read-only referenced, never copied** (packaged apps live in read-only locations such as `Program Files` or a mounted `.app`): search order is the `LABTOOLBOX_IMAGEJ_DIR` variants (`macros/`, `imagej/macros/`, `scripts/imagej/`), then the bundle `scripts/imagej/count_livedead.ijm` and `imagej/macros/`, then the repository `scripts/imagej/` (and `imagej/macros`, `vendor/imagej/macros`), then `<ImageJ>/macros/`. `imagej_status()` returns `{dir, jar, java, macro, found, searched}` and drives the GUI status line.

#### Bundled ImageJ 1.54 + Temurin 11 JRE (packaged app)

The Windows installer/portable zip and the macOS DMGs embed ImageJ 1.54 (unmodified `ij.jar`, from `wsr.imagej.net`) and a **platform-native Eclipse Temurin 11 JRE**, assembled by `scripts/fetch_imagej.py` and bundled by `labtoolbox.spec`:

| Platform | Bundled paths (read-only) |
|---|---|
| Windows | `…\LabToolbox\_internal\imagej\ij.jar`, `…\_internal\imagej\jre\bin\java.exe` |
| macOS | `LabToolbox.app/Contents/Frameworks/imagej/ij.jar`, `…/imagej/jre/Contents/Home/bin/java` |

The counting macro is bundled read-only at `…/scripts/imagej/count_livedead.ijm` (never copied at run time). No system Java/ImageJ/Fiji/Python is required and nothing is downloaded at first use; ImageJ 1.54 `Analyze Particles` was verified to give the same counts on the bundled Java 11 as on Java 8. Advanced users can override the bundled installation with `LABTOOLBOX_IMAGEJ_DIR`. Release CI checks the bundle with `scripts/verify_bundle.py` (ij.jar, JRE architecture, macro, igor). Install/unsigned-build details: [docs/INSTALL.md](../INSTALL.md).

#### OpenCV engine (legacy): fixed threshold + watershed

`CellCounterEngine.count_live_dead(image)` counts both channels of the image:

1. Split BGR → RGB; green = channel 1, red = channel 0.
2. Fixed threshold (`green_thresh = 20`, `red_thresh = 30`), 3×3 morphological close then open.
3. Watershed split of touching cells: `sure_bg = dilate(binary, iter=2)`; distance transform (`DIST_L2`, 5); `sure_fg = distance > 0.1·max`; markers from connected components; `cv2.watershed`; foreground = labels > 1.
4. Connected components (8-connectivity); per-object filters: area `min_size <= A <= max_size` (default 10–1000 px), roundness `4πA/P² >= min_roundness` (0.6), aspect ratio `max(w,h)/min(w,h) <= 3`.
5. Cross-talk correction: mean signal in the object mask in its own channel vs the other channel must satisfy `own/other >= min_channel_ratio` (1.2); otherwise the object is rejected.
6. Count of surviving objects. The analyzer then uses only the channel belonging to the file name (green file → green count).

### Statistics

Summary (per area × time, all repeats pooled):

```
live_mean/sd, dead_mean/sd, total_mean/sd   (ddof = 1; SD set to 0 when n = 1)
viability_pct = 100 · Σlive / Σ(live + dead)      (NaN when Σtotal = 0)
n = number of image pairs in the cell
```

ANOVA (`anova`, default `value_col="live"`, `log10=True`):

```
value' = log10( max(live, 1) + 1 )
value' ~ C(area_label) * C(time)      # OLS, Type II sums of squares
```

If statsmodels fails, the fallback runs a one-way ANOVA across areas **at each time point** (`scipy.stats.f_oneway`) and returns a table with columns `time`, `F`, `p`.

### Parameters and defaults

| Engine / function | Parameter | Default | Meaning |
|---|---|---|---|
| `run` | `backend` | `"imagej"` | `"imagej"` or `"opencv"` |
| `run` | `area_um2` | `None` | unused (CFU/cm² conversion not implemented) |
| `run` | `skip_repeats` | `()` | replicate folder names to drop |
| `ImageJEngine` | `imagej_dir` | auto-probe | ImageJ installation root |
| `ImageJEngine` | `min_size`, `max_size` | `3`, `500` | Analyze Particles size limits (px²) |
| `ImageJEngine` | `bg_offset` | `40` | stored only; macro uses +40 |
| `ImageJEngine` | `qc_dir` | `None` | write per-image QC overlays when set |
| `CellCounterEngine` | `min_size`, `max_size` | `10`, `1000` | object area filter (px) |
| `CellCounterEngine` | `green_thresh`, `red_thresh` | `20`, `30` | fixed intensity thresholds (0–255) |
| `CellCounterEngine` | `kernel_size` | `3` | morphology kernel |
| `CellCounterEngine` | `min_roundness` | `0.6` | `4πA/P²` lower bound |
| `CellCounterEngine` | `min_channel_ratio` | `1.2` | own/other channel mean ratio |
| `CellCounterEngine` | `split_thresh` | `0.1` | watershed foreground fraction of max distance |
| `LiveDeadCellCounter` | `area_um2` | `None` | unused |

CLI options map 1:1 onto `run()`'s parameters (`--min-size` → `min_size`, `--skip-repeats` → `skip_repeats`, `--qc-dir` → `qc_dir`); `--min-size` defaults to the engine default when omitted. The GUI exposes backend + ImageJ status + minimum size + output folder, plus roundness/thresholds for the OpenCV engine only.

### Implementation notes

* Package `labtoolbox/livedead_cellcounter/cellcounter.py` (727 lines after the integration PR); dependencies NumPy, pandas, matplotlib (Agg); ImageJ backend additionally uses only the Java subprocess + `csv`; OpenCV backend needs `opencv-python`.
* Classes/functions: `_dedupe`, `_bundle_roots`, `imagej_dir_candidates`, `find_imagej_jar`, `find_java`, `find_imagej`, `find_imagej_dir`, `_macro_candidates`, `find_macro`, `imagej_status`, `ImageJEngine` (`_macro_path`, `_batch_dir`, `count_live_dead`, `count_live_dead_pair`), `CellCounterEngine` (`extract_channel`, `count_cells_in_channel`, `count_live_dead`), `parse_filename`, `LiveDeadCellCounter` (`scan_structure`, `count_all`, `summarize`, `anova`, `plot`, `report`), `run`.
* Registered in the unified CLI as **`livedead-cellcounter`** (integration PR) and listed in `pyproject.toml`'s `packages`; the `[build]` extra/desktop app bundles it. Entry points: GUI tab, CLI, Python API.
* `run()` forwards `**engine_kwargs` to the selected engine; `verbose` is **not** an accepted argument of `run()` (passing it raises `TypeError`), only of `report()`.
* The macro file must stay pure ASCII (ImageJ does not read macro files as UTF-8); its header documents the 5-line argument protocol.
* Figure fonts are resolved by `labtoolbox.common.fonts` (`setup_matplotlib_cjk()`, called on import): Windows Microsoft YaHei/SimHei, macOS PingFang/Hiragino, Linux Noto/WenQuanYi; the `LABTOOLBOX_CJK_FONT` environment variable overrides the family. The figure title/labels are hard-coded English.
* The discovery helpers are plain functions (no state); `imagej_status()` is also called by the GUI. The bundled ImageJ/JRE layout is documented in `docs/INSTALL.md` and asserted by `scripts/verify_bundle.py` in release CI.

### Assumptions, limitations and known quirks

* **Strict folder/filename contract.** Any deviation (extra separators, different naming, missing number) makes the file invisible to the scanner; `area` may only be `c` or an integer.
* **ImageJ engine only counts `.tif`.** The scanner accepts `.png/.jpg/.bmp` but the macro skips them, so such files silently contribute 0 counts when `backend="imagej"`.
* **Pixel-only particle-size filter.** The macro resets spatial calibration, so `min_size/max_size` are in pixels (3–500 px² defaults were tuned for the group's 3 k micrographs); no µm² calibration is applied.
* **The bar-chart ANOVA annotation usually does not appear.** The plotting code looks for an `"p"` column, but the statsmodels branch returns `factor/sum_sq/df/F/PR(>F)`; only the fallback branch has `p`. Consequently the annotation is effectively limited to the fallback path (`aov["p"].iloc[0]` is then the first time point's p-value).
* **Time ordering is lexicographic.** Times are sorted as strings (`"10h"` sorts before `"2h"`); rename to zero-padded labels if order matters.
* **ANOVA is on log10(live+1) counts**, not viability; `log10=True` is the default, Type II SS, unbalanced cells are not modelled explicitly, no post-hoc tests, no multiplicity correction, no random effect for repeat.
* **GUI parameter routing (fixed in the integration PR).** The GUI now sends `min_roundness`/`green_thresh`/`red_thresh` **only** when `backend="opencv"` is selected; previously they were passed in ImageJ mode as well and silently dropped by `run()`'s kwarg filter. In ImageJ mode only `min_size` (and optionally `qc_dir` via the API/CLI) is adjustable.
* **No automatic engine fallback.** If the ImageJ installation, JRE or macro cannot be found, the ImageJ engine raises `FileNotFoundError` listing the searched candidates instead of silently switching engines; pass `--backend opencv` explicitly to use the legacy engine. The GUI shows the discovery status before you run.
* **`area_um2` is dead code**; no area-normalised density is computed. The Python API still accepts it for backward compatibility, but the unified CLI no longer exposes a flag for it.
* **Channel-trap heuristic** (brightest channel when named channel is dim) is a pragmatic fix, not a physical measurement; review QC overlays when counts look surprising.
* `skip_repeats` matches folder names exactly (case-sensitive); pass the names as they appear on disk.
* **OpenCV backend is retained only for regression/troubleshooting.** Its fixed thresholds and watershed parameters were superseded by the ImageJ method (project decision, 2026-09-11); historical comparison on the 515 nm series (160 paired fields) attributed most ImageJ-vs-OpenCV differences to the old engine lacking the channel-trap correction.

### QC and validation

* Optional per-image QC overlays (`qc_dir` → `<stem>_qc.png`) show each counted particle with number, the channel actually used and the threshold; this is the primary visual QC.
* Raw CSV keeps `g_image`, `r_image` and per-pair errors, so every count is traceable to a file.
* Cross-engine historical comparison is reproducible with `scripts/compare_count_backends.py` (outputs not committed); the project has standardised on ImageJ, so the OpenCV engine is not a validation oracle.
* Release CI verifies the packaged engine with `scripts/verify_bundle.py` (bundled `imagej/ij.jar`, platform-native JRE architecture, bundled macro, igor), so a broken/missing bundle fails the build instead of failing at the user's bench.
* Verified demo run for this documentation (commit `0e0508e`, Python 3.11, OpenCV 4.13, `backend="opencv"`): `examples/livedead_counter_demo` → 24 pairs; e.g. repeat1/1h/Area1: live 13, dead 12; pooled summary Area1 1h = 48.2 % viability (n = 6 pairs); ANOVA table as described (Type II, log10 live counts). The ImageJ backend could not be executed on the documentation machine (no ImageJ installation available); its behaviour is documented from the macro source.

### References

* Schneider CA, Rasband WS, Eliceiri KW. NIH Image to ImageJ: 25 years of image analysis. *Nat Methods.* 2012;9:671–675. doi:10.1038/nmeth.2089.
* Ferreira T, Rasband W. *ImageJ User Guide IJ 1.46r.* National Institutes of Health; 2012. (ImageJ command reference: `Set Scale`, `Split Channels`, thresholding, `Analyze Particles`; https://imagej.nih.gov/ij/docs/guide/)
* Bradski G. The OpenCV Library. *Dr. Dobb's Journal of Software Tools.* 2000. (OpenCV functions used by the legacy engine: `threshold`, morphology, `distanceTransform`, `watershed`, `connectedComponentsWithStats`)
* Thermo Fisher Scientific. *LIVE/DEAD™ BacLight™ Bacterial Viability Kit (L7012) — product manual.* (staining chemistry and interpretation)
* Berney M, Hammes F, Bosshard F, Weilenmann HU, Egli T. Assessment and interpretation of bacterial viability by using the LIVE/DEAD BacLight Kit in combination with flow cytometry. *Appl Environ Microbiol.* 2007;73(10):3283–3290. doi:10.1128/AEM.02750-06.
* Seabold S, Perktold J. statsmodels: econometric and statistical modeling with Python. *Proc 9th Python in Science Conf.* 2010:92–96. (two-way ANOVA)
* Project macro: `scripts/imagej/count_livedead.ijm` in this repository (the exact counting procedure used by the default engine).

## 中文

### 目的与科学背景

本模块自动计数按 **重复 → 时间点 → 区域** 文件夹层级组织的 LIVE/DEAD 荧光显微图，并把计数转成存活率统计。每个视野成对拍摄两个通道：绿色（`g`，SYTO 9 → 活菌、膜完整）与红色（`r`，碘化丙啶 → 死菌、膜受损）；模块把同一视野的两张图配对，输出活/死计数、合并存活率、堆叠柱状图与双因素 ANOVA。它替代手工 ImageJ 点选，是 [`livedead`](livedead.md) 统计模块的图像侧前端。可用入口：GUI 标签页 **🔬 LIVE/DEAD 细胞计数**、统一 CLI（`labtoolbox livedead-cellcounter`）与 Python API。

存在两个计数引擎：

* **`ImageJ`（默认，方法学基准）**——经典 ImageJ 1.54 headless 批处理 + 项目宏：自适应阈值 = 直方图众数背景 + 40，可选最亮通道回退，`Analyze Particles` 面积过滤。打包桌面版内置 ImageJ 1.54 + 平台原生 Temurin 11 JRE（无需安装）；源码运行时自动探测本地 ImageJ（见下文 *内置 vs 源码运行时的 ImageJ*）。
* **`opencv`（旧引擎，仅排障）**——最初的 Python/OpenCV 固定阈值 + 分水岭引擎，保留用于回归对比。项目已于 2026-09-11 把方法学统一到 ImageJ 引擎（见 README），不再做双引擎交叉验证。

### 输入文件夹结构与文件名

```
<root>/
├── repeat1/            # 生物学重复（正则 ^repeat\s*\d+$，不区分大小写）
│   ├── 1h/             # 时间点（正则 \d+h$）
│   │   ├── 1-g1.tif    # 区域 1，绿 = 活菌，视野 1
│   │   ├── 1-r1.tif    # 区域 1，红 = 死菌，视野 1
│   │   ├── c-g1.tif    # 对照区，绿
│   │   └── c-r1.tif    # 对照区，红
│   └── 3h/
├── repeat2/
└── repeat3/
```

* 文件名语法：`{区域}-{通道}{编号}.{扩展名}`，由 `AREA_PATTERN = ^([0-9]+|c)[-_]?([rg])(\d+)$` 解析（不区分大小写）。分隔符可为 `-`、`_` 或不写；`c`（任意大小写）为对照，其他整数为测试区域；`g`/`r` 为通道；`编号` 为视野序号。
* 扫描器接受的扩展名：`.tif`、`.tiff`、`.png`、`.jpg`、`.jpeg`、`.bmp`。**但 ImageJ 宏本身只处理 `.tif`**——非 TIFF 文件在 ImageJ 引擎下计为 0（见局限）。
* g/r 按 `(区域, 编号)` 配对；绿图提供 `live`，红图提供 `dead`。缺一个通道时该计数为 0。
* 自带演示：`examples/livedead_counter_demo/`（3 重复 × 1h/3h × Control/Area1 × 2 视野，合成 200×200 图像）及说明 `examples/README_livedead_counter.md`。
* `skip_repeats=("repeat2",)` 在计数前整组剔除重复文件夹（用于数据不全/无效的重复）。

### 入口

| 入口 | 用法 |
|---|---|
| GUI 标签页 **🔬 LIVE/DEAD 细胞计数** | 图像根文件夹、计数引擎选择（`imagej` / `opencv`，带 ImageJ 状态行）、最小粒子面积、输出目录；圆形度/绿/红阈值**只在**选 `opencv` 时发送 |
| CLI `labtoolbox livedead-cellcounter FOLDER` | `--output`、`--backend imagej\|opencv`、`--min-size`、`--skip-repeats`、`--qc-dir` |
| Python API | `labtoolbox.livedead_cellcounter.run(folder, output_dir, area_um2, backend, skip_repeats, **engine_kwargs)`；更细控制可用 `LiveDeadCellCounter(engine=...).report(...)` |

```bash
labtoolbox livedead-cellcounter path/to/root --output results \
    --backend imagej --min-size 3 --qc-dir results/qc
```

选项说明：省略 `--min-size` 时用引擎默认值（ImageJ 3 px²、OpenCV 10 px）；`--qc-dir` 只对 ImageJ 引擎有效（CLI 对 `opencv` 会打印警告并忽略）；错误经统一 CLI 以非零退出码和报错信息暴露。GUI 状态行显示探测到的 ImageJ 目录，或 *“未找到 (可设 LABTOOLBOX_IMAGEJ_DIR)”*。

### 输出

`LiveDeadCellCounter.report(root, output_dir="output", verbose=True, skip_repeats=())` 写出：

| 输出 | 内容 |
|---|---|
| `livedead_raw_counts.csv` | 每对图一行：`repeat`、`time`、`area`、`num`、`g_image`、`r_image`、`live`、`dead`、`total`、`dead_rate`（失败对另有 `error`） |
| `livedead_summary.csv` | 按 `area_label` × `time`：`live_mean/sd`、`dead_mean/sd`、`total_mean/sd`、`dead_rate_mean`、`n`、`live_pooled`、`dead_pooled`、`viability_pct` |
| `livedead_anova.csv` | 双因素 ANOVA 表（`factor`、`sum_sq`、`df`、`F`、`PR(>F)`）或逐时间点单因素回退表 |
| `livedead_cell_count.png` | 堆叠柱状图：死菌（红）在下、活菌（绿）在上，按区域 × 时间分组，带 SD 误差棒 |

`run(folder, output_dir="output", area_um2=None, backend="imagej", skip_repeats=(), **engine_kwargs)` 返回 dict `{"raw", "raw_csv", "summary", "summary_csv", "anova", "anova_csv", "figure"}`。`area_um2` 参数被接受但**从未使用**——模块内没有任何 CFU/cm² 或密度换算。

### 端到端流程

0. **选择引擎**——`backend="imagej"`（默认）构造 `ImageJEngine`；`backend="opencv"` 构造旧的 `CellCounterEngine`。`run()` 会过滤引擎参数：只有 `imagej_dir`、`min_size`、`max_size`、`bg_offset`、`qc_dir` 会传给 `ImageJEngine`；OpenCV 引擎接受其完整参数集。找不到 ImageJ 运行时或宏时，ImageJ 引擎会抛 `FileNotFoundError` 并列出搜索候选——**不会自动回退**；请显式传 `backend="opencv"`。
1. `scan_structure(root)`——列出 `repeat*` 文件夹（按数字排序）、匹配 `\d+h$` 的时间文件夹与匹配的图像文件；重复数少于 3 时告警；应用 `skip_repeats`；什么都没找到时抛错。
2. `count_all(structure)`——对每个重复/时间：按 `(区域, 编号)` 分组图像，调 `engine.count_live_dead(g_img)` → `live = counts["green"]`，`engine.count_live_dead(r_img)` → `dead = counts["red"]`；累积行（失败行记 NaN + `error`），每 20 对打印进度；算 `dead_rate = dead/total`。
3. `summarize(df)`——把 `c → Control`、`n → Area n` 重命名；按区域×时间聚合均值/SD，并加入**合并计数**的 `Σlive/Σtotal × 100` 存活率。
4. `anova(df, value_col="live", log10=True)`——对 log10 变换后的活菌计数做双因素 ANOVA。
5. `plot(df)`——堆叠柱 + SD 误差棒 + ANOVA 标注（见怪癖）。
6. 保存原始计数、汇总、ANOVA 与图。

### 计数算法

#### ImageJ 引擎（默认）：宏 `count_livedead.ijm`

引擎写一个 5 行 UTF-8 参数文件（输入目录、输出 CSV、QC 目录、最小粒子面积、最大粒子面积），以 headless 方式运行经典 ImageJ：

```
java -cp <ImageJ>/ij.jar ij.ImageJ -batch <宏> <参数文件>
```

并设置 `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8`（因此中文路径可用；ImageJ 命令行参数本身不能带中文）。整个目录一次批处理，逐文件计数进缓存，一个 JVM 启动可服务该文件夹所有图像；子进程超时 1800 s。

宏对每张图：

1. 打开 TIFF 并重置空间标定（`Set Scale... distance=0`），清除 Image-Pro 的假标定（如 inch/px）——否则粒子面积过滤会失效。
2. RGB 图：分离通道，读取各通道最大值（`chanMax`）；按文件名确定*命名*通道（含 `-g` → 绿，否则红）。**通道陷阱规则：** 命名通道最大值 `< 30`（无真实信号）时改数最亮通道，并记录 `chan_used = auto-bright`。
3. 阈值 = 背景直方图众数 + 40（`bgMode` + 40）作用于 0–255，`Convert to Mask`。
4. `Analyze Particles size=<min>-<max> px show=Nothing add`；计数 = 结果数。默认 3–500 px²（可通过 `ImageJEngine(min_size, max_size)` 改），`bg_offset` 仅存储，宏里硬编码 +40。
5. 可选 QC 模式（`qc_dir`）：保存 `<stem>_qc.png`，把每个被计数粒子圈出并编号，便于排查漏数/多圈。
6. 回到 Python 后，按文件名（`[-_]?([rg])[_-]?\d+`）把逐文件计数分派为 `green` 或 `red`；文件名有歧义时可用 `count_live_dead_pair(g_img, r_img)` 显式配对。

#### 内置 vs 源码运行时的 ImageJ

`ImageJEngine` 按以下顺序定位运行时（`imagej_dir_candidates()`、`find_imagej()`、`find_macro()`）：

1. **环境变量覆盖** `LABTOOLBOX_IMAGEJ_DIR`——可指向含 `ij.jar` 的 ImageJ 目录，或指向含 `imagej/` 与 `scripts/` 的 bundle 根。
2. **打包 bundle 根**（仅冻结版）：`<bundle>/imagej`，其中 `<bundle>` 为 `sys._MEIPASS`（PyInstaller 6 Windows onedir 的 `_internal`；macOS `.app` 的 `Contents/Frameworks`）、可执行文件目录及其 `_internal`、`.app` 的 `Contents/Resources|Frameworks` 变体。
3. **仓库随包**：`<repo>/imagej`、`<repo>/vendor/imagej`。
4. **旧本地安装**：`E:/ImageJ/ImageJ`、`F:/ImageJ/ImageJ`、`C:/Users/PC/Downloads/ImageJ`。

Java 优先取自 ImageJ 目录——Windows：`jre/bin/java.exe`、`jre/bin/java`、`jre/Contents/Home/bin/java`、`bin/java.exe`、`bin/java`；macOS：先 `jre/Contents/Home/bin/java`，再其他布局。`PATH` 里的 `java` 只是开发回退（打包版总是自带 JRE）。

宏文件**只读引用、从不复制**（打包版位于 `Program Files` 或挂载的 `.app` 等只读位置）：搜索顺序为 `LABTOOLBOX_IMAGEJ_DIR` 变体（`macros/`、`imagej/macros/`、`scripts/imagej/`）→ bundle 的 `scripts/imagej/count_livedead.ijm` 与 `imagej/macros/` → 仓库 `scripts/imagej/`（及 `imagej/macros`、`vendor/imagej/macros`）→ `<ImageJ>/macros/`。`imagej_status()` 返回 `{dir, jar, java, macro, found, searched}`，并驱动 GUI 状态行。

#### 内置 ImageJ 1.54 + Temurin 11 JRE（打包应用）

Windows 安装包/便携 zip 与 macOS DMG 内置 ImageJ 1.54（未修改的 `ij.jar`，来自 `wsr.imagej.net`）与**平台原生 Eclipse Temurin 11 JRE**，由 `scripts/fetch_imagej.py` 组装、`labtoolbox.spec` 打包：

| 平台 | 内置路径（只读） |
|---|---|
| Windows | `…\LabToolbox\_internal\imagej\ij.jar`、`…\_internal\imagej\jre\bin\java.exe` |
| macOS | `LabToolbox.app/Contents/Frameworks/imagej/ij.jar`、`…/imagej/jre/Contents/Home/bin/java` |

计数宏以只读方式随包分发于 `…/scripts/imagej/count_livedead.ijm`（运行时从不复制）。无需系统 Java/ImageJ/Fiji/Python，首次使用不联网下载；已验证 ImageJ 1.54 的 `Analyze Particles` 在内置 Java 11 与 Java 8 上给出相同计数。高级用户可用 `LABTOOLBOX_IMAGEJ_DIR` 覆盖内置安装。发布 CI 用 `scripts/verify_bundle.py` 校验（ij.jar、JRE 架构、宏、igor）。安装/未签名版本说明见 [docs/INSTALL.md](../INSTALL.md)。

#### OpenCV 引擎（旧）：固定阈值 + 分水岭

`CellCounterEngine.count_live_dead(image)` 对图像的两个通道都计数：

1. BGR → RGB；绿 = 通道 1，红 = 通道 0。
2. 固定阈值（`green_thresh = 20`、`red_thresh = 30`），3×3 形态学闭运算再开运算。
3. 粘连细胞分水岭：`sure_bg = dilate(binary, iter=2)`；距离变换（`DIST_L2`, 5）；`sure_fg = 距离 > 0.1·max`；连通域作标记；`cv2.watershed`；前景 = 标签 > 1。
4. 连通域（8 连通）逐对象过滤：面积 `min_size <= A <= max_size`（默认 10–1000 px）、圆度 `4πA/P² >= min_roundness`（0.6）、长宽比 `max(w,h)/min(w,h) <= 3`。
5. 串色校正：对象掩膜内自身通道均值与另一通道均值之比须 `own/other >= min_channel_ratio`（1.2），否则剔除。
6. 返回存活对象数。随后分析器只取文件名所属通道的计数（绿图 → 绿通道计数）。

### 统计

汇总（按区域 × 时间，所有重复合并）：

```
live_mean/sd, dead_mean/sd, total_mean/sd   （ddof = 1；n = 1 时 SD 记 0）
viability_pct = 100 · Σlive / Σ(live + dead)      （Σtotal = 0 时为 NaN）
n = 该单元内的图像对数
```

ANOVA（`anova`，默认 `value_col="live"`、`log10=True`）：

```
value' = log10( max(live, 1) + 1 )
value' ~ C(area_label) * C(time)      # OLS，Type II 平方和
```

若 statsmodels 失败，回退为**逐时间点**跨区域单因素 ANOVA（`scipy.stats.f_oneway`），返回 `time`、`F`、`p` 三列表。

### 参数与默认值

| 引擎 / 函数 | 参数 | 默认值 | 含义 |
|---|---|---|---|
| `run` | `backend` | `"imagej"` | `"imagej"` 或 `"opencv"` |
| `run` | `area_um2` | `None` | 未使用（未实现 CFU/cm² 换算） |
| `run` | `skip_repeats` | `()` | 要剔除的重复文件夹名 |
| `ImageJEngine` | `imagej_dir` | 自动探测 | ImageJ 安装根目录 |
| `ImageJEngine` | `min_size`、`max_size` | `3`、`500` | Analyze Particles 面积上下限（px²） |
| `ImageJEngine` | `bg_offset` | `40` | 仅存储；宏用 +40 |
| `ImageJEngine` | `qc_dir` | `None` | 设置后输出逐图 QC 叠加图 |
| `CellCounterEngine` | `min_size`、`max_size` | `10`、`1000` | 对象面积过滤（px） |
| `CellCounterEngine` | `green_thresh`、`red_thresh` | `20`、`30` | 固定强度阈值（0–255） |
| `CellCounterEngine` | `kernel_size` | `3` | 形态学核尺寸 |
| `CellCounterEngine` | `min_roundness` | `0.6` | `4πA/P²` 下限 |
| `CellCounterEngine` | `min_channel_ratio` | `1.2` | 自身/另一通道均值比 |
| `CellCounterEngine` | `split_thresh` | `0.1` | 分水岭前景占最大距离的比例 |
| `LiveDeadCellCounter` | `area_um2` | `None` | 未使用 |

CLI 选项与 `run()` 参数一一对应（`--min-size` → `min_size`、`--skip-repeats` → `skip_repeats`、`--qc-dir` → `qc_dir`）；省略 `--min-size` 时用引擎默认值。GUI 暴露引擎选择 + ImageJ 状态 + 最小面积 + 输出目录，圆形度/阈值只对 OpenCV 引擎生效。

### 实现说明

* 包 `labtoolbox/livedead_cellcounter/cellcounter.py`（集成 PR 后 727 行）；依赖 NumPy、pandas、matplotlib（Agg）；ImageJ 后端额外只用 Java 子进程 + `csv`；OpenCV 后端需要 `opencv-python`。
* 类/函数：`_dedupe`、`_bundle_roots`、`imagej_dir_candidates`、`find_imagej_jar`、`find_java`、`find_imagej`、`find_imagej_dir`、`_macro_candidates`、`find_macro`、`imagej_status`、`ImageJEngine`（`_macro_path`、`_batch_dir`、`count_live_dead`、`count_live_dead_pair`）、`CellCounterEngine`（`extract_channel`、`count_cells_in_channel`、`count_live_dead`）、`parse_filename`、`LiveDeadCellCounter`（`scan_structure`、`count_all`、`summarize`、`anova`、`plot`、`report`）、`run`。
* 集成 PR 起已注册进统一 CLI（**`livedead-cellcounter`**），并列入 `pyproject.toml` 的 `packages`；`[build]` extra/桌面应用会打包它。入口：GUI 标签页、CLI、Python API。
* `run()` 把 `**engine_kwargs` 转给所选引擎；`verbose` **不是** `run()` 的参数（传入会 `TypeError`），只有 `report()` 有。
* 宏文件必须保持纯 ASCII（ImageJ 不以 UTF-8 读宏文件）；其头部注释记录了 5 行参数协议。
* 图字体由 `labtoolbox.common.fonts` 解析（导入时调用 `setup_matplotlib_cjk()`）：Windows 微软雅黑/SimHei、macOS PingFang/Hiragino、Linux Noto/WenQuanYi；环境变量 `LABTOOLBOX_CJK_FONT` 可覆盖字体家族。图的标题/轴标签为硬编码英文。
* 探测辅助函数都是无状态普通函数；`imagej_status()` 也被 GUI 调用。内置 ImageJ/JRE 布局记录于 `docs/INSTALL.md`，发布 CI 用 `scripts/verify_bundle.py` 断言。

### 假设、局限与已知怪癖

* **严格的文件夹/文件名契约。** 任何偏差（多余分隔符、不同命名、缺编号）都会让文件对扫描器不可见；`area` 只能是 `c` 或整数。
* **ImageJ 引擎只数 `.tif`。** 扫描器接受 `.png/.jpg/.bmp`，但宏会跳过它们，因此在 `backend="imagej"` 下这些文件静默贡献 0 计数。
* **粒子面积过滤只有像素单位。** 宏重置了空间标定，因此 `min_size/max_size` 是像素（默认 3–500 px² 按本组 3k 显微图调校）；没有 µm² 标定。
* **柱状图的 ANOVA 标注通常不出现。** 绘图代码找 `"p"` 列，但 statsmodels 分支返回的是 `factor/sum_sq/df/F/PR(>F)`；只有回退分支有 `p`。因此标注实际只限于回退路径（此时 `aov["p"].iloc[0]` 是第一个时间点的 p 值）。
* **时间排序按字典序。** 时间按字符串排序（`"10h"` 排在 `"2h"` 前）；若顺序重要请改成补零标签。
* **ANOVA 作用于 log10(live+1) 计数**，不是存活率；`log10=True` 是默认，Type II 平方和，不显式建模不平衡单元，无事后检验、无多重比较校正、不把重复当随机效应。
* **GUI 参数传递（集成 PR 已修复）。** GUI 现在**只在**选择 `backend="opencv"` 时发送 `min_roundness`/`green_thresh`/`red_thresh`；此前它们在 ImageJ 模式下也会传入，随后被 `run()` 的参数过滤静默丢弃。ImageJ 模式下只有 `min_size`（以及 API/CLI 的可选 `qc_dir`）可调。
* **没有自动引擎回退。** 找不到 ImageJ 安装、JRE 或宏时，ImageJ 引擎抛出 `FileNotFoundError` 并列出搜索候选，而不是静默切换引擎；要用旧引擎请显式传 `--backend opencv`。GUI 会在运行前显示探测状态。
* **`area_um2` 是死代码**；不计算任何面积归一化密度。Python API 仍接受该参数以保持兼容，但统一 CLI 不再暴露对应选项。
* **通道陷阱启发式**（命名通道很暗时改数最亮通道）是务实的修正，不是物理测量；计数异常时请查看 QC 叠加图。
* `skip_repeats` 精确匹配文件夹名（区分大小写）；请按磁盘上的实际名称传入。
* **OpenCV 后端只为回归/排障保留。** 其固定阈值与分水岭参数已被 ImageJ 方法取代（项目决定，2026-09-11）；515 nm 系列 160 对视野的历史对比显示 ImageJ 与 OpenCV 的差异主要来自旧引擎缺少通道陷阱修正。

### 质控与验证

* 可选的逐图 QC 叠加图（`qc_dir` → `<stem>_qc.png`）显示每个被计数粒子的编号、实际使用的通道与阈值；这是主要的目视 QC。
* 原始 CSV 保留 `g_image`、`r_image` 与逐对错误信息，每个计数都可追溯到文件。
* 跨引擎历史对比可用 `scripts/compare_count_backends.py` 复现（输出不入库）；项目已统一到 ImageJ，因此 OpenCV 引擎不是验证基准。
* 发布 CI 用 `scripts/verify_bundle.py` 校验打包引擎（内置 `imagej/ij.jar`、平台原生 JRE 架构、随包宏、igor），因此 bundle 损坏会在构建期失败，而不是在用户实验台上失败。
* 本文档核对演示（commit `0e0508e`，Python 3.11、OpenCV 4.13、`backend="opencv"`）：`examples/livedead_counter_demo` → 24 对；例如 repeat1/1h/Area1：live 13、dead 12；汇总 Area1 1h = 48.2 % 存活率（n = 6 对）；ANOVA 表如上（Type II、log10 活菌计数）。ImageJ 后端在文档编写机器上无法运行（无 ImageJ 安装），其行为依据宏源码描述。

### 参考文献

* Schneider CA, Rasband WS, Eliceiri KW. NIH Image to ImageJ: 25 years of image analysis. *Nat Methods.* 2012;9:671–675. doi:10.1038/nmeth.2089.
* Ferreira T, Rasband W. *ImageJ User Guide IJ 1.46r.* National Institutes of Health; 2012.（ImageJ 命令参考：`Set Scale`、`Split Channels`、阈值化、`Analyze Particles`；https://imagej.nih.gov/ij/docs/guide/）
* Bradski G. The OpenCV Library. *Dr. Dobb's Journal of Software Tools.* 2000.（旧引擎使用的 OpenCV 函数：`threshold`、形态学、`distanceTransform`、`watershed`、`connectedComponentsWithStats`）
* Thermo Fisher Scientific. *LIVE/DEAD™ BacLight™ Bacterial Viability Kit (L7012) — product manual.*（染色化学与判读）
* Berney M, Hammes F, Bosshard F, Weilenmann HU, Egli T. Assessment and interpretation of bacterial viability by using the LIVE/DEAD BacLight Kit in combination with flow cytometry. *Appl Environ Microbiol.* 2007;73(10):3283–3290. doi:10.1128/AEM.02750-06.
* Seabold S, Perktold J. statsmodels: econometric and statistical modeling with Python. *Proc 9th Python in Science Conf.* 2010:92–96.（双因素 ANOVA）
* 本仓库宏文件 `scripts/imagej/count_livedead.ijm`（默认引擎使用的确切计数流程）。
