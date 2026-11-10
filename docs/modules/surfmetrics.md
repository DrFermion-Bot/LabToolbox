# surfmetrics — AFM/SEM height maps: 3-D views, ISO areal roughness and area ratio / AFM/SEM 高度图：3D 图、ISO 面积粗糙度与表面积比

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

`surfmetrics` is the AFM/SEM surface-morphology engine of LabToolbox. It reads height maps (Bruker/Igor `.ibw`, TIFF/PNG, or plain numeric matrices), removes form/faults where requested, computes **ISO 25178-2 areal amplitude parameters** (`Sa`, `Sq`, `Sz`) and the **developed interfacial area ratio** `Sdr`, renders a true-scale 3-D surface, and adds reference-line depth profiles (H/V or one line crossing the ripples). It is used to characterise laser-textured stainless steel (LIPSS, nanopillars), coatings and other topographic surfaces; its loaders/geometry helpers are also the foundation of [`contact_schematic`](contact_schematic.md) and are re-used by the SEM consistency module conceptually.

A second `gwyddion` backend can delegate leveling and statistics to the open-source Gwyddion 2.67 kernel running inside WSL (pygwy), for reviewer-facing cross-checks.

### Inputs and data formats

| Format | Loader | Notes |
|---|---|---|
| `.ibw` (Bruker/Igor binary wave) | `igor.binarywave.load` | Direct read; channel auto-selection, unit auto-conversion and `ScanSize` calibration (see below) |
| `.tif` / `.tiff` / `.png` | `tifffile.imread` | Treated as a height matrix; first plane used if 3-D; **pixel size must be supplied** (`--px`) |
| `.txt` / `.csv` / `.xyz` | `numpy.loadtxt(ndmin=2)` | Either a raw height matrix, or 3 columns `x, y, z` reshaped to a matrix via unique x/y values |

`.ibw` handling details (`load_heightmap`):

* Channel labels are taken from the wave `labels`; if empty, `channel_names()` falls back to the `ChannelNDataType` entries in the wave note. Name aliases: `zsr`, `zsensor`, `zs`, `zsensorretrace` → ZSensor Retrace; `height`, `heightretrace` → Height Retrace; integers are used as raw indices.
* **Automatic channel priority: ZSensor Retrace (`zsensor`) > Height Retrace (`height`) > first channel with `std > 1e-9`** (a warning is printed in the last case). Rationale in the source: ZSR is the raw piezo-sensor feedback (unfiltered/unlevelled) and is the correct channel for roughness; Height Retrace is software-smoothed and underestimates relief. Use `--channel height` to reproduce the old convention.
* Unit heuristic: if the channel's standard deviation lies in `1e-12 < std < 1e-4`, the data are assumed to be in **metres** and multiplied by `1e9` to nm; otherwise they are taken as nm/relative units. A converted channel with `std < 1e-3` is rejected as "no valid height data".
* Calibration: `ScanSize: <value>` (metres) is parsed from the wave note; `px = py = ScanSize·1e9 / max(shape)` (nm/px). No note → pixel size unknown.
* Folder batch mode (`folder=`/`--folder`) globs `*.ibw` first and falls back to `*.tif`; non-recursive, sorted.

### Outputs

| Output | Content |
|---|---|
| `output/<name>_3D.png` | 3-D surface (viridis), true z/XY scaling by default, colour bar `Height (nm)`, title with `Sa/Sq/Sz/Sdr` |
| `output/<name>_profile.png` | Left: 3-D view with reference line(s) drawn on the surface; right: depth profile(s), `P-V` per line, mean lines |
| `output/all_3D_grid.png` | Multi-panel 3-D grid when more than one file is processed (max 9 panels, 3 columns) |
| `output/surface_metrics_summary.csv` | One row per file with roughness, Sdr and profile-direction diagnostics |
| return dict | `{"results": [dicts], "csv": path, "figures": [paths], "grid": path or None}` |

Per-file result dicts (Python backend): `file`, `path`, `Sa_nm`, `Sq_nm`, `Sz_nm`, `S3d_um2`, `Sproj_um2`, `Sdr_pct`, plus `profile_mode`, `line_count`, `stripe_cross_deg`, `stripe_ridge_deg`, `stripe_period_nm`, `stripe_strength`, `stripe_band_nm` (the latter only when a stripe direction was estimated). The Gwyddion backend additionally reports `backend = "gwyddion"`, `level`, `skew`, `kurt` (from Gwyddion) while `S3d/Sproj/Sdr` still come from the Python triangulation.

### End-to-end pipeline

1. **Resolve input files** (`folder` → glob, or `file` → one path/list; raise if neither/empty).
2. **Channel resolution** (for `.ibw`): read channel names of the first file; if `channel` is a name, resolve it on every file and require the same index; if no explicit channel and a ZSensor channel exists, select it automatically. `auto_zs = (selected channel == zsensor index)`.
3. **Default preprocessing:** when `plane`/`despike` are `None`, they default to `auto_zs` (ZSR → 2-D plane subtraction + 5σ median despiking **on**; Height/other → off). Explicit `True`/`False` override.
4. **Load height map** per file; optionally `plane_subtract(z)` and `despike_z(z)`.
5. **Pixel size** per file: explicit `px`/`py`, else from `.ibw` calibration; `py` defaults to `px`. The Python backend raises if the pixel size is still unknown.
6. **Metrics** via `surface_metrics(z, px, py)`; append row.
7. **Figures**: `plot3d` for every file and, when `profiles=True`, `plot_profiles` with reference lines chosen by `profile_lines_for(profile_mode, stripe_angle, row, col, stripe_band)`.
8. **CSV** (`surface_metrics_summary.csv`, UTF-8 BOM) and, if more than one file, the **3-D grid**.
9. **Gwyddion backend instead of steps 4–7** (`backend="gwyddion"`): call `wsl -d Ubuntu -u root -- bash -lc "/usr/local/bin/gwy_batch.py <file> --level|--raw [--channel N] -o /root/<tmp>.csv"`, copy the output back, parse `file, channel, mean_nm, Sa_nm, Sq_nm, Sz_nm, skew, kurt`; still do the Python-side load/plane/despike and triangulated Sdr for the figures/CSV.

### Algorithms and formulas

#### ISO areal roughness (`surface_metrics`)

```
z_c(x,y) = z(x,y) − mean(z)
Sa = (1/A) ∬ |z_c| dA        →  mean(|z_c|)          [nm]
Sq = sqrt( (1/A) ∬ z_c² dA ) →  sqrt(mean(z_c²))     [nm]
Sz = max(z) − min(z)                                  [nm]
```

#### Developed area ratio `Sdr` (triangulation, ISO 25178-2 style)

For every elementary cell of the height grid two triangles are formed:

```
a1 = (px, 0,  z[i+1,j]   − z[i,j])     b1 = (px, py, z[i+1,j+1] − z[i,j])
a2 = (0,  py, z[i,j+1]   − z[i,j])     b2 = (px, py, z[i+1,j+1] − z[i,j])
A_tri = ½ |a × b|
S3d   = Σ A_tri over all cells                       [nm²]
S_proj = (h − 1)(w − 1) · px · py                    [nm²]
Sdr   = (S3d / S_proj − 1) · 100                     [%]
```

`S3d`/`S_proj` are reported in µm². For a sinusoidal surface this reproduces the expected `Sdr ≈ mean(√(1 + (dz/dx)² + (dz/dy)²)) − 1`.

#### Plane subtraction and despiking

```
plane:  z = a·x + b·y + c  fitted by least squares on normalised x,y ∈ [0,1] (lstsq), then subtracted
despike: repeat up to 3 times:
    med  = median_filter(z, size=3, mode=nearest)
    σ    = std(z − med)
    z[ |z − med| > 5σ ] = med
```

`despike_z` returns the number of replaced pixels (discarded by `run`). It removes **single-pixel/small spikes only**; extended particles or inclusions survive and must be handled by manual QC.

#### Stripe orientation from the 2-D FFT (`stripe_orientation`)

```
1. remove tilt: fit z = a·x + b·y + c (normalised coords) and subtract
2. F = fftshift( fft2( z_detilted · Hann(h)×Hann(w) ) )
3. mag = |F|; zero the 5×5 DC block; keep one half-plane (rows ≥ h/2 zeroed)
4. optional band filter: keep only frequencies whose period 1/|f| ∈ [lo, hi] nm
5. peak → fx = (px_peak − cx)/(w·px), fy = (py_peak − cy)/(h·py)   [cycles/nm]
   f = hypot(fx, fy);  period = 1/f;  angle = atan2(fy, fx)
   cross_deg = angle folded into [−90, 90)       (direction crossing the ripples)
   ridge_deg = cross_deg + 90                    (stripe direction)
   strength  = peak magnitude / median magnitude (relative measure, can be large)
```

`profile_lines_for` uses this only in `cross`/`auto` modes; `auto` switches to a single cross-line when `strength ≥ 8.0`. **Project convention (2026-09-15):** in `cross` mode the drawn ruler is always at **90° (along +Y)** unless `stripe_angle` is given explicitly — the FFT-derived angle and period are still written into the CSV for traceability. This assumes the ripples run along X, which is the project's LIPSS standard orientation.

#### Reference-line sampling (`_sample_line`)

`row` → ruler along X at a pixel row; `col` → ruler along Y at a pixel column; `angle` → straight line through the image centre in direction θ, extending to the borders minus a 2 % margin, sampled at ≈1 sample/px (max 4000 points) with bilinear interpolation. Distances are returned in µm (measured from the ruler start); the `(x, y)` coordinates are reused to draw the ruler on the 3-D surface.

#### 3-D rendering and z scaling

`plot3d`/`plot_profiles` use `z_mode`:

* `"real"` (default): physical aspect `box_aspect = (x_extent_µm, y_extent_µm, z_extent_µm)` — no vertical exaggeration.
* `"auto"`: `k = max(0.25·mean(x,y extent)/(z extent), 1)` — z displayed at ≈25 % of the XY scale so shallow relief is visible.
* numeric: manual magnification `k`.

When the on-screen z/XY ratio `k·z_extent/mean(x,y)` is `< 0.10`, z tick labels are hidden (the colour bar carries the scale); for `< 0.5` only 3 ticks are drawn. In addition a **z scale bar** can be drawn at the "screen-left" corner from 0 to the maximum height (auto-enabled when ticks are hidden), and the title states the scale mode (`[z and XY at the same scale]` or `[z ×k]`).

#### Gwyddion backend

The Python side builds a WSL command per file (`_win2wsl` maps `F:\x` → `/mnt/f/x`), the WSL kernel script `gwy_batch.py` performs Gwyddion leveling (`--level`) or not (`--raw`), optional fixed channel (`--channel`), and returns a CSV with `mean_nm, Sa_nm, Sq_nm, Sz_nm, skew, kurt`. The script is copied out of the WSL `/root` directory with a second WSL `cp` call and parsed; a per-file failure raises `RuntimeError("gwy_batch 无输出")`.

### Parameters and defaults

| `run()` parameter | Default | Meaning |
|---|---|---|
| `file` | `None` | One path or a list of paths |
| `folder` | `None` | Batch folder; `*.ibw`, else `*.tif` |
| `channel` | `None` | `.ibw` channel index or name (`zsr`/`height`/…); `None` = auto (ZSR preferred) |
| `px`, `py` | `None` | Pixel size (nm); `py` defaults to `px`; read from `.ibw` calibration when available |
| `output_dir` | `"output"` | Output directory |
| `z_mode` | `"real"` | 3-D z scaling: `"real"` / `"auto"` / numeric factor |
| `backend` | `"python"` | `"python"` or `"gwyddion"` |
| `level` | `True` | Gwyddion backend: plane leveling on/off |
| `profiles` | `True` | Also output reference-line profile figures |
| `profile_row`, `profile_col` | `None` | H/V line positions (defaults: image centre) |
| `profile_mode` | `"hv"` | `"hv"` (H+V), `"cross"` (single line across ripples), `"auto"` |
| `stripe_angle` | `None` | Manual cross-line angle (deg); otherwise FFT-derived info + 90° convention |
| `stripe_band` | `None` | `(lo, hi)` nm physical period band for the stripe search (recommended for ZSR data: `(0.5λ, 1.5λ)`) |
| `plane`, `despike` | `None` | Force plane subtraction / despiking on or off; `None` = follow `auto_zs` |

CLI `labtoolbox surfmetrics --file … | --folder … [--channel …] [--px …] [--py …] [--z-mode real|auto|<k>] [--no-profiles] [--profile-row …] [--profile-col …] [--backend python|gwyddion] [--no-level]` (note: `profile_mode`, `stripe_angle`, `stripe_band`, `plane`, `despike` are **not** exposed on the CLI). GUI tab **🏔️ 表面形貌** exposes file/folder, channel index, `px` and output dir (defaults: `channel=None`, `px=None`, `py=None`, `z_mode="real"`, `profiles=True`).

### Implementation notes

* Package `labtoolbox/surfmetrics/surfmetrics.py` (872 lines). Dependencies: NumPy, SciPy, matplotlib (Agg), `tifffile`; `igor` from `https://github.com/wking/igor` for `.ibw`; optional WSL + Gwyddion for the Gwyddion backend.
* Functions: `load_heightmap`, `surface_metrics`, `_setup_cjk_font`, `_apply_z_ticks`, `_cbar`, `_z_scale_bar`, `plot3d`, `_norm_dir`, `stripe_orientation`, `_sample_line`, `plot_profiles`, `profile_lines_for`, `plot_grid`, `_win2wsl`, `gwy_batch_wsl`, `_profile_cells`, `channel_names`, `resolve_channel`, `plane_subtract`, `despike_z`, `run`.
* Figure fonts are resolved by `labtoolbox.common.fonts` (`setup_matplotlib_cjk`, wrapped by the module's cached `_setup_cjk_font`): Windows Microsoft YaHei/SimHei, macOS PingFang/Hiragino, Linux Noto/WenQuanYi, with `LABTOOLBOX_CJK_FONT` as an override; figure text otherwise falls back to DejaVu Sans.
* Figure titles and CSV headers are English; warnings (channel choice, unit conversion) are printed to stdout in Chinese.
* The unified CLI registers `surfmetrics` in `labtoolbox/cli.py`; `labtoolbox/surfmetrics/__init__` exports `load_heightmap`, `surface_metrics`, `plot3d`, `plot_grid`, `run`. `contact_schematic/geometry.py` imports `despike_z`, `load_heightmap`, `plane_subtract`, `stripe_orientation`, `surface_metrics` from this module.

### Assumptions, limitations and known quirks

* **Only mean removal is applied by `surface_metrics`.** `Sa`/`Sq` are relative to the mean plane of the loaded matrix; tilt/form is **not** removed unless `plane=True` (or the auto-ZSR path is active). For raw Height Retrace data the tilt inflates Sa/Sq/Sz substantially (verified example: a 0.05 slope gave Sa = 33.4 nm raw vs 12.1 nm after plane subtraction on the same synthetic surface).
* **Sz is max−min, not a robust amplitude.** Isolated spikes and scan faults dominate `Sz`; despiking only removes single-pixel spikes.
* **Unit auto-detection can fail silently.** A genuinely flat surface whose metre-scale standard deviation is below `1e-12` would be taken as already in nm (error ≈1e9); a surface stored in nm with std > `1e-4` is kept (correct), but intermediate formats are ambiguous. Always check the printed `std=…` line.
* **`.ibw` channel selection is name/substring based**; channel names can be missing (fallback via wave note) and index consistency across files is enforced — mixed files raise.
* **Pixel-size requirement.** TIFF/PNG/TXT inputs carry no calibration: the Python backend refuses to produce metrics without `px`, and the Gwyddion backend quietly skips figures/metrics (`Sdr = None`) when no pixel size is available.
* **`Sdr` is a triangulation of the sampled grid** — it depends on pixel size and sampling; at very coarse sampling the true roughness is underrepresented, and noise inflates it (each pixel contributes its local slope).
* **Height maps in folder mode are limited to `.ibw`/`.tif`**; `.txt/.csv/.xyz` must be passed via `file` (single file or list).
* **`profile_mode="cross"` draws a 90° ruler by project convention**, not the measured FFT angle; the measured angle is only in the CSV/report fields. Use `stripe_angle` when the ripples are not X-aligned.
* **`stripe_orientation` half-plane masking** keeps rows above the FFT centre; the angle is folded to `[−90, 90)`. The `strength` is a ratio to the median spectral magnitude and is not comparable across images with different noise/contrast (it can be enormous for clean synthetic patterns).
* **Gwyddion results are hybrid:** `Sa/Sq/Sz/skew/kurt` come from the Gwyddion kernel (with its own leveling), while `S3d/Sproj/Sdr` are computed in Python from the separately pre-processed matrix — the row mixes two pipelines, so cross-backend comparisons must compare like-for-like columns.
* **Gwyddion backend requires WSL Ubuntu + `/usr/local/bin/gwy_batch.py`**; it is Windows-specific (WSL paths) and fails on macOS/Linux builds. The `igor` package must be installed from GitHub (PyPI `igor` is an empty placeholder).
* `z_mode="auto"` exaggerates z visually; the title tags it, but the quantitative metrics are unaffected. `z_bar`/`_z_scale_bar` are cosmetic; `zlim` is restored after drawing so the physical box ratio is preserved.
* The 3-D grid assumes square pixels (`py = px`) and caps the panel count implicitly at 9 for the intended layout.

### QC and validation

* **Visual QC**: every processed file gets a 3-D view and a reference-line profile; the title/scale tag documents the vertical scaling, and `.ibw` channel/unit decisions are printed to stdout.
* **Backend cross-check**: `scripts/compare_surf_515.py` and `compare_surf_515_zs.py` compare the Python and Gwyddion kernels; the project README records 100 % point-wise agreement on raw data for 20 `.ibw` files of the 515 nm sample, and demonstrates that ZS-channel leveling flattens an unlevelled file (Sa 16.1 → 3.8 nm).
* **Dimension/algorithm sanity**: the Sdr triangulation was verified here on a synthetic sinusoid (period 80 nm, amplitude 20 nm, px = 10 nm): `Sdr = 44.47 %` matches the analytic mean-slope value (`mean√(1+(dz/dx)²) − 1 ≈ 44.5 %`); raw vs plane-subtracted Sa (33.37 vs 12.14 nm) behaves as expected for the added 0.05 slope. `stripe_orientation` returned `period = 79.96 nm`, `cross_deg ≈ 1.79°` for the same map.
* The repository has no automated versioned test-suite for this module; validation scripts live in `scripts/` and their outputs are not committed.

### References

* ISO 25178-2:2012. *Geometrical product specifications (GPS) — Surface texture: Areal — Part 2: Terms, definitions and surface texture parameters.* International Organization for Standardization, Geneva. (definitions of Sa, Sq, Sz, Sdr and areal filtering/leveling context)
* ASME B46.1-2019. *Surface Texture (Surface Roughness, Waviness, and Lay).* ASME. (profile/areal surface texture terminology in engineering practice)
* Leach R (ed.). *Characterisation of Areal Surface Texture.* Springer; 2013. (areal parameters, leveling and sampling practice)
* Nečas D, Klapetek P. Gwyddion: an open-source software for SPM data analysis. *Cent Eur J Phys.* 2012;10(1):181–188. doi:10.2478/s11534-011-0096-2. (Gwyddion kernel used by the optional backend)
* `igor` Python package for Bruker/Igor binary wave files: https://github.com/wking/igor (the PyPI `igor` package is an empty placeholder — install from GitHub).
* Whitehouse DJ. *Surfaces and Their Measurement.* Hermes Penton; 2002. (roughness parameter definitions and instrumentation)

## 中文

### 目的与科学背景

`surfmetrics` 是 LabToolbox 的 AFM/SEM 表面形貌引擎。它读取高度图（Bruker/Igor `.ibw`、TIFF/PNG 或纯数值矩阵），按需去除形状/坡度，计算 **ISO 25178-2 面积幅度参数**（`Sa`、`Sq`、`Sz`）与**展开界面面积比** `Sdr`，以真实比例渲染 3D 表面，并附带参考线深度剖面（横/纵两条，或跨条纹的一条线）。用于表征激光织构不锈钢（LIPSS、纳米柱）、涂层及其他形貌表面；其读取器/几何助手也是 [`contact_schematic`](contact_schematic.md) 的基础，并在概念上被 SEM 一致性模块复用。

可选的 `gwyddion` 后端把调平与统计交给运行在 WSL 内的开源 Gwyddion 2.67 内核（pygwy），便于做审稿人可见的交叉核对。

### 输入与数据格式

| 格式 | 读取器 | 说明 |
|---|---|---|
| `.ibw`（Bruker/Igor binary wave） | `igor.binarywave.load` | 直读；自动选通道、自动单位换算、从 `ScanSize` 自动标定（见下） |
| `.tif` / `.tiff` / `.png` | `tifffile.imread` | 视为高度矩阵；3D 时取第一层；**必须提供像素尺寸**（`--px`） |
| `.txt` / `.csv` / `.xyz` | `numpy.loadtxt(ndmin=2)` | 纯高度矩阵，或 `x, y, z` 三列按 x/y 唯一值重排成矩阵 |

`.ibw` 处理细节（`load_heightmap`）：

* 通道标签取自 wave 的 `labels`；为空时 `channel_names()` 回退到 wave note 中的 `ChannelNDataType` 条目。名称别名：`zsr`、`zsensor`、`zs`、`zsensorretrace` → ZSensor Retrace；`height`、`heightretrace` → Height Retrace；整数直接作为通道索引。
* **自动通道优先级：ZSensor Retrace（`zsensor`）> Height Retrace（`height`）> 第一个 `std > 1e-9` 的通道**（最后一种会打印警告）。源码中的理由：ZSR 是压电传感器原始反馈（未滤波、未调平），才是粗糙度分析应使用的通道；Height Retrace 被软件平滑过，会低估起伏。要复现旧口径用 `--channel height`。
* 单位启发式：若通道标准差落在 `1e-12 < std < 1e-4`，按**米**处理并乘 `1e9` 转 nm；否则视为 nm/相对单位。换算后 `std < 1e-3` 的通道按“无有效高度数据”拒绝。
* 标定：从 wave note 解析 `ScanSize: <值>`（米）；`px = py = ScanSize·1e9 / max(shape)`（nm/px）。没有该字段则像素尺寸未知。
* 批量模式（`folder=`/`--folder`）先 glob `*.ibw`，没有再 glob `*.tif`；不递归、按名称排序。

### 输出

| 输出 | 内容 |
|---|---|
| `output/<name>_3D.png` | 3D 表面（viridis），默认真实 z/XY 比例，色标 `Height (nm)`，标题含 `Sa/Sq/Sz/Sdr` |
| `output/<name>_profile.png` | 左：3D 图并叠加参考线；右：深度剖面、每条线的 `P-V` 与均值线 |
| `output/all_3D_grid.png` | 多个文件时的多面板 3D 网格（最多 9 面板，3 列） |
| `output/surface_metrics_summary.csv` | 每文件一行，含粗糙度、Sdr 与剖面方向诊断量 |
| 返回 dict | `{"results": [dict], "csv": path, "figures": [path], "grid": path 或 None}` |

Python 后端的逐文件结果：`file`、`path`、`Sa_nm`、`Sq_nm`、`Sz_nm`、`S3d_um2`、`Sproj_um2`、`Sdr_pct`，另加 `profile_mode`、`line_count`、`stripe_cross_deg`、`stripe_ridge_deg`、`stripe_period_nm`、`stripe_strength`、`stripe_band_nm`（仅当估计了条纹方向时）。Gwyddion 后端额外给出 `backend = "gwyddion"`、`level`、`skew`、`kurt`（来自 Gwyddion），而 `S3d/Sproj/Sdr` 仍由 Python 三角剖分计算。

### 端到端流程

1. **解析输入文件**（`folder` → glob，或 `file` → 单路径/列表；两者都缺/为空则报错）。
2. **通道解析**（`.ibw`）：读第一个文件的通道名；`channel` 为名称时在每个文件上解析并要求索引一致；未显式给 channel 且存在 ZSensor 通道时自动选它。`auto_zs = (所选通道 == zsensor 索引)`。
3. **默认预处理：** `plane`/`despike` 为 `None` 时取 `auto_zs`（ZSR → 开启 2D 平面扣除 + 5σ 中值去尖峰；Height/其他 → 关闭）。显式 `True`/`False` 可覆盖。
4. **逐文件载入高度图**；按需 `plane_subtract(z)` 与 `despike_z(z)`。
5. **逐文件像素尺寸**：显式 `px`/`py`，否则用 `.ibw` 标定；`py` 默认等于 `px`。Python 后端在仍未知时抛错。
6. **算指标** `surface_metrics(z, px, py)` 并追加一行。
7. **作图**：每个文件 `plot3d`；`profiles=True` 时用 `profile_lines_for(profile_mode, stripe_angle, row, col, stripe_band)` 选参考线并画 `plot_profiles`。
8. **CSV**（`surface_metrics_summary.csv`，UTF-8 BOM）；文件多于一个时再出 **3D 网格图**。
9. **Gwyddion 后端替代步骤 4–7**（`backend="gwyddion"`）：执行 `wsl -d Ubuntu -u root -- bash -lc "/usr/local/bin/gwy_batch.py <文件> --level|--raw [--channel N] -o /root/<tmp>.csv"`，再拷回输出并解析 `file, channel, mean_nm, Sa_nm, Sq_nm, Sz_nm, skew, kurt`；Python 侧仍做载入/平面扣除/去尖峰以及三角剖分 Sdr，用于作图与 CSV。

### 算法与公式

#### ISO 面积粗糙度（`surface_metrics`）

```
z_c(x,y) = z(x,y) − mean(z)
Sa = (1/A) ∬ |z_c| dA        →  mean(|z_c|)          [nm]
Sq = sqrt( (1/A) ∬ z_c² dA ) →  sqrt(mean(z_c²))     [nm]
Sz = max(z) − min(z)                                  [nm]
```

#### 展开面积比 `Sdr`（三角剖分，ISO 25178-2 风格）

对高度网格的每个单元构造两个三角形：

```
a1 = (px, 0,  z[i+1,j]   − z[i,j])     b1 = (px, py, z[i+1,j+1] − z[i,j])
a2 = (0,  py, z[i,j+1]   − z[i,j])     b2 = (px, py, z[i+1,j+1] − z[i,j])
A_tri = ½ |a × b|
S3d    = 所有单元 A_tri 之和                          [nm²]
S_proj = (h − 1)(w − 1) · px · py                     [nm²]
Sdr    = (S3d / S_proj − 1) · 100                     [%]
```

`S3d`/`S_proj` 以 µm² 报告。对正弦表面，该式可复现期望的 `Sdr ≈ mean(√(1 + (dz/dx)² + (dz/dy)²)) − 1`。

#### 平面扣除与去尖峰

```
平面:  z = a·x + b·y + c  用归一化 x,y ∈ [0,1] 做最小二乘拟合（lstsq），再减去
去尖峰: 最多重复 3 次：
    med  = median_filter(z, size=3, mode=nearest)
    σ    = std(z − med)
    z[ |z − med| > 5σ ] = med
```

`despike_z` 返回被替换的像素数（`run` 会丢弃）。它**只去单像素/小面积尖峰**；大块颗粒或夹杂会保留，需人工 QC 处理。

#### 由二维 FFT 估计条纹取向（`stripe_orientation`）

```
1. 去倾斜：拟合 z = a·x + b·y + c（归一化坐标）并减去
2. F = fftshift( fft2( 去倾斜后的 z · Hann(h)×Hann(w) ) )
3. mag = |F|；把 5×5 DC 块置零；只保留半平面（行 ≥ h/2 置零）
4. 可选带通：只保留周期 1/|f| ∈ [lo, hi] nm 的频率
5. 取峰 → fx = (px_peak − cx)/(w·px)，fy = (py_peak − cy)/(h·py)   [cycles/nm]
   f = hypot(fx, fy)；period = 1/f；angle = atan2(fy, fx)
   cross_deg = 折入 [−90, 90) 的角度       （横跨条纹的方向）
   ridge_deg = cross_deg + 90              （条纹方向）
   strength  = 峰值幅度 / 中位幅度（相对量，可能很大）
```

`profile_lines_for` 只在 `cross`/`auto` 模式使用它；`auto` 在 `strength ≥ 8.0` 时切换为单条跨纹线。**项目约定（2026-09-15）：** `cross` 模式下实际画的标尺固定为 **90°（沿 +Y）**，除非显式给 `stripe_angle`——FFT 得到的方向与周期仍写进 CSV 以便追溯。这假设条纹沿 X 排列，即本项目 LIPSS 的标准取向。

#### 参考线采样（`_sample_line`）

`row` → 在指定像素行沿 X 的标尺；`col` → 在指定像素列沿 Y 的标尺；`angle` → 过图像中心、沿 θ 方向到边界（留 2 % 余量）的直线，按约每像素 1 点（最多 4000 点）双线性插值采样。返回沿标尺起点计的 µm 距离；`(x, y)` 坐标用于在 3D 表面画出该标尺。

#### 3D 渲染与 z 比例

`plot3d`/`plot_profiles` 使用 `z_mode`：

* `"real"`（默认）：真实比例 `box_aspect = (x 跨度µm, y 跨度µm, z 跨度µm)`——不做纵向夸张。
* `"auto"`：`k = max(0.25·XY 平均跨度/(z 跨度), 1)`——z 显示为 XY 尺度的约 25 %，便于观察浅起伏。
* 数值：手动放大系数 `k`。

当屏幕上的 z/XY 比 `k·z跨度/XY平均跨度` `< 0.10` 时隐藏 z 刻度数字（高度由色标给出）；`< 0.5` 时只画 3 个刻度。另外可在“屏幕最左”角画一条 **z 标尺**（0 → 最大高度，刻度被隐藏时自动开启），标题会注明比例模式（`[z and XY at the same scale]` 或 `[z ×k]`）。

#### Gwyddion 后端

Python 侧逐文件构造 WSL 命令（`_win2wsl` 把 `F:\x` → `/mnt/f/x`），WSL 内脚本 `gwy_batch.py` 执行 Gwyddion 调平（`--level`）或不调平（`--raw`）、可选固定通道（`--channel`），返回含 `mean_nm, Sa_nm, Sq_nm, Sz_nm, skew, kurt` 的 CSV。脚本先用第二次 WSL `cp` 从 `/root` 拷回 Windows 临时目录再解析；某个文件失败会抛 `RuntimeError("gwy_batch 无输出")`。

### 参数与默认值

| `run()` 参数 | 默认值 | 含义 |
|---|---|---|
| `file` | `None` | 单个路径或路径列表 |
| `folder` | `None` | 批量目录；先 `*.ibw` 再 `*.tif` |
| `channel` | `None` | `.ibw` 通道索引或名称（`zsr`/`height`/…）；`None` = 自动（优先 ZSR） |
| `px`、`py` | `None` | 像素尺寸（nm）；`py` 默认等于 `px`；`.ibw` 有标定时自动读取 |
| `output_dir` | `"output"` | 输出目录 |
| `z_mode` | `"real"` | 3D z 比例：`"real"` / `"auto"` / 数值放大系数 |
| `backend` | `"python"` | `"python"` 或 `"gwyddion"` |
| `level` | `True` | Gwyddion 后端是否做平面调平 |
| `profiles` | `True` | 是否额外输出参考线剖面图 |
| `profile_row`、`profile_col` | `None` | 横/纵参考线位置（默认图像中心） |
| `profile_mode` | `"hv"` | `"hv"`（横+纵）、`"cross"`（单条跨纹线）、`"auto"` |
| `stripe_angle` | `None` | 手动跨纹线角度（度）；否则用 FFT 信息 + 90° 约定 |
| `stripe_band` | `None` | 条纹搜索的物理周期带 `(lo, hi)` nm（ZSR 数据建议给 `(0.5λ, 1.5λ)`） |
| `plane`、`despike` | `None` | 强制开启/关闭平面扣除、去尖峰；`None` 跟随 `auto_zs` |

命令行 `labtoolbox surfmetrics --file … | --folder … [--channel …] [--px …] [--py …] [--z-mode real|auto|<k>] [--no-profiles] [--profile-row …] [--profile-col …] [--backend python|gwyddion] [--no-level]`（注意：`profile_mode`、`stripe_angle`、`stripe_band`、`plane`、`despike` **不在** CLI 暴露）。GUI 标签页 **🏔️ 表面形貌** 暴露文件/文件夹、通道索引、`px` 与输出目录（默认 `channel=None`、`px=None`、`py=None`、`z_mode="real"`、`profiles=True`）。

### 实现说明

* 包 `labtoolbox/surfmetrics/surfmetrics.py`（872 行）。依赖 NumPy、SciPy、matplotlib（Agg）、`tifffile`；`.ibw` 需要来自 `https://github.com/wking/igor` 的 `igor`；Gwyddion 后端另需 WSL + Gwyddion。
* 函数：`load_heightmap`、`surface_metrics`、`_setup_cjk_font`、`_apply_z_ticks`、`_cbar`、`_z_scale_bar`、`plot3d`、`_norm_dir`、`stripe_orientation`、`_sample_line`、`plot_profiles`、`profile_lines_for`、`plot_grid`、`_win2wsl`、`gwy_batch_wsl`、`_profile_cells`、`channel_names`、`resolve_channel`、`plane_subtract`、`despike_z`、`run`。
* 图字体由 `labtoolbox.common.fonts` 解析（模块内的 `_setup_cjk_font` 只是其带缓存的包装）：Windows 微软雅黑/SimHei、macOS PingFang/Hiragino、Linux Noto/WenQuanYi，可用 `LABTOOLBOX_CJK_FONT` 覆盖；都不可用时回退 DejaVu Sans。
* 图标题与 CSV 表头为英文；通道选择、单位换算等警告以中文打印到 stdout。
* 统一 CLI 在 `labtoolbox/cli.py` 注册 `surfmetrics`；`labtoolbox/surfmetrics/__init__` 导出 `load_heightmap`、`surface_metrics`、`plot3d`、`plot_grid`、`run`。`contact_schematic/geometry.py` 从本模块导入 `despike_z`、`load_heightmap`、`plane_subtract`、`stripe_orientation`、`surface_metrics`。

### 假设、局限与已知怪癖

* **`surface_metrics` 只减均值。** `Sa`/`Sq` 相对载入矩阵的均值平面；除非 `plane=True`（或自动 ZSR 路径生效），否则**不**去倾斜/形状。对原始 Height Retrace 数据，倾斜会显著放大 Sa/Sq/Sz（核对示例：同一合成表面上叠加 0.05 坡度后原始 Sa = 33.4 nm，平面扣除后 12.1 nm）。
* **Sz 是 max−min，不是稳健幅度。** 孤立尖峰与扫描故障会主导 `Sz`；去尖峰只处理单像素尖峰。
* **单位自动识别可能静默出错。** 真正平坦、米制标准差低于 `1e-12` 的表面会被当作已是 nm（误差约 1e9 倍）；以 nm 存储且 std > `1e-4` 的数据保持正确，但中间量纲有歧义。务必查看打印出的 `std=…` 行。
* **`.ibw` 通道选择基于名称/子串**；通道名可能缺失（回退 wave note），并且要求跨文件索引一致——混合文件会报错。
* **像素尺寸必需。** TIFF/PNG/TXT 无标定：Python 后端缺 `px` 时拒绝出指标；Gwyddion 后端在无像素尺寸时静默跳过图/指标（`Sdr = None`）。
* **`Sdr` 是采样网格的三角剖分**——依赖像素尺寸与采样率；采样过粗会低估真实粗糙度，而噪声会放大它（每个像素都贡献局部坡度）。
* **批量模式的高度图只支持 `.ibw`/`.tif`**；`.txt/.csv/.xyz` 必须通过 `file`（单文件或列表）传入。
* **`profile_mode="cross"` 按项目约定画 90° 标尺**，不是实测 FFT 角度；实测角度只在 CSV/报告字段里。条纹不沿 X 时请显式给 `stripe_angle`。
* **`stripe_orientation` 的半平面掩蔽**保留 FFT 中心以上的行；角度折入 `[−90, 90)`。`strength` 是相对谱中位幅度的比值，不同噪声/对比度的图像之间不可直接比较（对干净的合成图案可能极大）。
* **Gwyddion 结果是混合的：** `Sa/Sq/Sz/skew/kurt` 来自 Gwyddion 内核（用其自己的调平），而 `S3d/Sproj/Sdr` 由 Python 从另行预处理过的矩阵计算——同一行混了两条流程，跨后端比较时须只比较同类列。
* **Gwyddion 后端需要 WSL Ubuntu + `/usr/local/bin/gwy_batch.py`**；它依赖 WSL 路径，因此在 macOS/Linux 构建上不可用。`igor` 包必须从 GitHub 安装（PyPI 的 `igor` 是空壳）。
* `z_mode="auto"` 只做视觉夸张（标题会标注），定量指标不受影响。`z_bar`/`_z_scale_bar` 只是装饰；画完会把 `zlim` 复位，保持物理盒比例。
* 3D 网格假设方形像素（`py = px`），按目标版式实际最多 9 个面板。

### 质控与验证

* **目视 QC**：每个处理的文件都有 3D 图与参考线剖面；标题/比例标记注明纵向缩放，`.ibw` 的通道/单位决策打印到 stdout。
* **后端交叉核对**：`scripts/compare_surf_515.py` 与 `compare_surf_515_zs.py` 对比 Python 与 Gwyddion 内核；项目 README 记录 515 nm 样品 20 个 `.ibw` 原始数据逐点 100 % 一致，并展示 ZS 通道调平能把未调平文件的 Sa 从 16.1 nm 降到 3.8 nm。
* **量纲/算法自检**：本文档在合成正弦面（周期 80 nm、幅度 20 nm、px = 10 nm）上核对了 Sdr 三角剖分：`Sdr = 44.47 %` 与解析均坡度值（`mean√(1+(dz/dx)²) − 1 ≈ 44.5 %`）一致；叠加 0.05 坡度后原始 Sa（33.37 nm）与平面扣除后（12.14 nm）符合预期。同一图 `stripe_orientation` 返回 `period = 79.96 nm`、`cross_deg ≈ 1.79°`。
* 仓库没有针对本模块的自动化版本化测试；验证脚本在 `scripts/` 中，且其输出不入库。

### 参考文献

* ISO 25178-2:2012. *Geometrical product specifications (GPS) — Surface texture: Areal — Part 2: Terms, definitions and surface texture parameters.* International Organization for Standardization, Geneva.（Sa、Sq、Sz、Sdr 定义与面积滤波/调平语境）
* ASME B46.1-2019. *Surface Texture (Surface Roughness, Waviness, and Lay).* ASME.（工程实践中的轮廓/面积表面纹理术语）
* Leach R (ed.). *Characterisation of Areal Surface Texture.* Springer; 2013.（面积参数、调平与采样实践）
* Nečas D, Klapetek P. Gwyddion: an open-source software for SPM data analysis. *Cent Eur J Phys.* 2012;10(1):181–188. doi:10.2478/s11534-011-0096-2.（可选后端使用的 Gwyddion 内核）
* `igor` Python 包（Bruker/Igor binary wave 读取）：https://github.com/wking/igor（PyPI 上的 `igor` 是空壳，需从 GitHub 安装）。
* Whitehouse DJ. *Surfaces and Their Measurement.* Hermes Penton; 2002.（粗糙度参数定义与仪器）
