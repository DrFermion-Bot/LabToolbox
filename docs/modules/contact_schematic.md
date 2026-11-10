# contact_schematic — Bacterial–texture contact schematics from measured AFM geometry / 由实测 AFM 几何生成细菌–织构接触示意图

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

`contact_schematic` is the **final step of the AFM analysis workflow**: it measures the real contact-relevant geometry of a laser-textured surface from Bruker `.ibw` height maps (LIPSS period and groove depth; nanopillar spacing and bump height), then renders publication-quality 3-D schematics of bacterial cells resting on that topography plus a contact-geometry diagram. The output is a set of figures (`fig1` LIPSS adhesion, `fig2` nanopillar adhesion, `fig3` contact geometry), a per-file measurement table and an auto-generated README that states every assumption. It is a *schematic* module: cells are rigid geometric bodies placed on measured topography — no XDLVO or mechanical deformation calculation is done here (that is [`xdlvo`](xdlvo.md)). The module is reachable from the GUI (tab **📐 Contact Schematic**), from the unified CLI (`labtoolbox schematic` / `python -m labtoolbox.contact_schematic`) and as a one-step Python API, `contact_schematic.run()`.

### Inputs and data formats

CLI (`python -m labtoolbox.contact_schematic` or the unified `labtoolbox schematic`):

| Argument | Default | Meaning |
|---|---|---|
| `--input` | required | `.ibw` file or directory (recursive `**/*.ibw` when a directory) |
| `--out` | required (CLI); `output` (unified CLI) | Output directory |
| `--label` | `515 nm` | Sample label used in titles |
| `--channel` | `zsr` | `.ibw` channel name (pixel/geometry preprocessing identical to `surfmetrics`) |
| `--lambda` / `--lam` | `515` | Laser wavelength in nm; sets the FFT period band `(0.5λ, 1.5λ)` |
| `--dpi` | `190` | Figure resolution |
| `--cell` | `2.0x0.5` | *E. coli* length × diameter in µm |
| `--coccus` | `0.9` | *S. aureus* diameter in µm |
| `--no-render` | off | Measure and write the CSV only |

The unified CLI (`labtoolbox schematic`) forwards `--input/--out/--label/--channel/--lam/--dpi/--no-render` only; it does **not** expose `--cell/--coccus` (use `python -m labtoolbox.contact_schematic` for those).

The GUI tab **📐 Contact Schematic** exposes the AFM data folder, the sample label (default `515 nm`) and the output directory; it runs the same one-step API with the remaining defaults (ZSR channel, λ = 515 nm, dpi = 190, literature cell sizes, rendering on).

Shared Python entry point (used by both CLI forms and the GUI):

```python
contact_schematic.run(folder, output_dir="output", label="515 nm", channel="zsr",
                      lam_nm=515.0, dpi=190, cell=(2.0, 0.5), coccus=0.9,
                      render=True, verbose=False)
```

It returns `{"csv", "summary", "figures", "readme", "n_files"}`; `render=False` is equivalent to the CLI `--no-render`, and `verbose=True` prints the CLI progress lines.

Surface classification is **filename-based** (`geometry.classify`): lower-case path containing `lipss` → LIPSS; containing `np` (word boundary), `nano`, `nanopillar` or `pillar` → nanopillar; otherwise `unknown` (Sa/Sq/Sz are still measured, but no feature geometry is extracted and the file is excluded from the schematic summaries).

### Outputs

| File | Content |
|---|---|
| `fig1_LIPSS_adhesion.png` / `.pdf` | 5 panels: (a) LIPSS morphology + cross-section; (b) *E. coli* parallel (0°); (c) 45°; (d) perpendicular (90°); (e) *S. aureus* cocci. Each cell panel has a top-view inset; legend + measured period/depth in the title |
| `fig2_nanopillar_adhesion.png` / `.pdf` | Same layout on the measured nanopillar lattice (spacing/height in the title) |
| `fig3_contact_geometry.png` / `.pdf` | (a) sphere above a ridge — SEI geometry `D(r) = h + R − √(R²−r²)`; (b) rod parallel to the striations — real tangency on the groove slopes; (c) rod perpendicular — touches ridge crests only (side view) |
| `geometry_measurements.csv` | Summary block (mean ± sd (n; min–max) for the four headline quantities) + per-file measured values for every file |
| `README.md` | Auto-generated bilingual (Chinese) note: measured geometry, file list, and the five assumptions that must match the paper caption |

Return value of `render_all` is the list of PNG paths actually generated. The one-step `run()` returns `{"csv": path, "summary": dict, "figures": [png paths], "readme": path, "n_files": int}`.

### End-to-end pipeline

All entry points — GUI tab, `python -m labtoolbox.contact_schematic`, `labtoolbox schematic` and the Python API — call `contact_schematic.run(folder, ...)`, which creates the output directory and executes the steps below; `__main__.py` is a thin argparse adapter over it.

1. **Discover files** (`measure_geometry`): accept a file, a glob or a directory (recursive `.ibw`); every file is measured independently and failures are recorded as `{"class": "error", "error": ...}` without aborting the batch.
2. **Measure one file** (`measure_file`): `load_heightmap(channel="zsr")` → `plane_subtract` → `despike_z` (5σ median despiking) → `surface_metrics` → `Sa`, `Sq`, `Sz`; then class-specific geometry (below).
3. **Summarise** (`summarise`): for each class and quantity compute `n`, `mean`, `sd` (ddof=1), `median`, `min`, `max`; return the dictionary used by the renderer (`lam_nm`, `lipss`, `nanopillar`, `n_files`, `n_lipss`, `n_pillar`).
4. **Write CSV** (`write_csv`): headline summary for `LIPSS.period_nm`, `LIPSS.depth_nm`, `Nanopillar.spacing_nm`, `Nanopillar.height_nm`, then a blank line and the per-file table.
5. **Render** (`render_all`): `fig1` + `fig3` when LIPSS statistics exist; `fig2` when nanopillar statistics exist (each as PNG + PDF).
6. **Write README** (`write_readme`) with the measured numbers and the fixed assumption list.
7. **Return** the artefact dict `{csv, summary, figures, readme, n_files}`.

#### Class-specific measurement

**LIPSS** (`class == "lipss"`):

* Period: `surfmetrics.stripe_orientation(z, px, py, band_nm=(0.5λ, 1.5λ))` — the same 2-D-FFT peak search used by `surfmetrics`, restricted to the physically possible period band to avoid µm-scale ZSR scan artefacts. `period_nm = 1/|f_peak|`; `stripe_deg = ridge_deg = cross_deg + 90°`. If no peak exists inside the band, the search is repeated over the full spectrum and `period_banded = False` is recorded.
* Depth: the map is rotated by `−cross_deg` so the periodicity direction becomes horizontal; the middle half of the rows is averaged along the stripes; `depth_nm = P98 − P2` of that profile (more robust than `Sz`, which is inflated by isolated spikes). `feature_nm = depth_nm`.

**Nanopillar** (`class == "nanopillar"`):

* Threshold `median(z) + 1.5·std(z)`; peaks = 7×7 local maxima above the threshold.
* If at least 5 peaks: pairwise nearest-neighbour distances via `scipy.spatial.cKDTree` (k=2), `spacing_nm = median(NN distance)`; `n_peaks`; `density_per_um2 = n_peaks / (h·px/1000)²` (assumes square pixels).
* `height_nm = P90(z) − median(z)`; `feature_nm = height_nm`.
* Fewer than 5 peaks → `spacing_nm = NaN` (height is still reported).

### Geometry and rendering details

* **Field of view** for fig1/fig2: 5.5 µm × 2.8 µm, single axes per panel, orthographic projection, cells drawn **strictly to scale** (no vertical exaggeration anywhere in this module).
* **Analytic LIPSS surface**: `z = (depth/2)·cos(2πY/period) − depth/2`, i.e. ripples vary along Y so ridges run along X. A rod at 0° is therefore parallel to the striations (the project convention).
* **Synthetic nanopillar surface** (`seed = 7`, deterministic): nominal grid `(i − 0.5)·spacing`; each pillar centre jittered by N(0, 0.02·spacing), radius `0.36·spacing·(1 + N(0, 0.10))`, height `height·(1 + N(0, 0.12))`, radial profile `h·cos²(clip(d/r, 0, 1)·π/2)`; sum over pillars, then shifted so the minimum is 0.
* **Cells**: *E. coli* as a capsule mesh (hemispherical caps + cylinder, 16 + 34 + 16 axial stations, 64 azimuth samples); *S. aureus* as a sphere mesh (56 × 56). Cells are placed at the mid-field position with their centre at `z_top + cell_half_height`, i.e. **resting on the highest surface point**, not conforming to the local topography. Surface shading uses custom normals and a directional light (`LightSource(azdeg=235, altdeg=32)`); colours: grey surface, green rods, orange cocci, red dashed dimension arrows, blue dashed top-view/cross-section frames.
* **Top-view inset** (per cell panel): schematic plan view with a fixed inset scale bar; the rod is drawn with its orientation and "predicted contact points": for LIPSS, contact dots are placed only where a sampled rod point falls in the crest band (`|band − 0.75| ≤ 0.20` of the period); for pillars every sampled rod point is marked. These dots are geometric proximity indicators, not computed contact mechanics.
* **fig3**: sinusoidal ripple `z = (depth/2)·cos(2πx/period)`; (a) sphere of radius `R = coccus/2` in nm, placed with its **minimum gap = 60 nm** above the crest, annotated with `h`, `R`, `r`, `θ`, `D(r)`, `Λ` and depth; (b) rod parallel to the striations represented by a circle of radius `R = E. coli diameter/2` at true tangency with the groove flanks (centre at 1.5 Λ on a crest; contact markers where the distance to the surface is a local minimum ≤ 1.002 R); (c) rod perpendicular: the rod is a side view across the ridges — a semi-transparent green band resting on the crest plane, red dots at every crest, and `h` annotated as the crest-to-trough depth. The generated README states explicitly that figures are schematic rigid-body constructions, that LIPSS is approximated as sinusoidal and the pillar arrangement as quasi-periodic, and that `D(r)` uses the equivalent sphere–plane (SEI) convention.

### Parameters and defaults

| Parameter | Default | Meaning |
|---|---|---|
| `--input` | required | `.ibw` file / directory |
| `--out` | required | Output directory |
| `--label` | `515 nm` | Sample label in titles |
| `--channel` | `zsr` | `.ibw` channel (ZSensor Retrace preferred) |
| `--lambda` | `515` nm | FFT physical period window `(0.5λ, 1.5λ)` |
| `--dpi` | `190` | PNG/PDF resolution |
| `--cell` | `2.0x0.5` µm | *E. coli* length × diameter (`render.ECOLI_L`, `render.ECOLI_D`) |
| `--coccus` | `0.9` µm | *S. aureus* diameter (`render.SAUREUS_D`) |
| `--no-render` | off | CSV only |
| `profile band factor` | 0.5 | `measure_file(..., profile_band=0.5)` → band `(0.5λ, 1.5λ)` |
| despiking | 5σ, 3 iterations, 3×3 median | from `surfmetrics.despike_z` defaults |
| plane subtraction | always on | `plane_subtract` applied inside `measure_file` |
| pillar peak filter | 7×7 max, `median+1.5σ` | `maximum_filter(size=7)` |
| minimum peaks | 5 | below this, no pillar spacing is reported |
| `run(folder)` | required | One-step API: `.ibw` file/dir → CSV (+ figures/README) |
| `run(output_dir)` | `"output"` | Output directory |
| `run(label)` | `"515 nm"` | Sample label in titles |
| `run(channel)` | `"zsr"` | `.ibw` channel |
| `run(lam_nm)` | `515.0` | FFT physical period window `(0.5λ, 1.5λ)` |
| `run(dpi)` | `190` | Figure resolution |
| `run(cell)` | `(2.0, 0.5)` µm | *E. coli* (length, diameter) |
| `run(coccus)` | `0.9` µm | *S. aureus* diameter |
| `run(render)` | `True` | `False` = CSV only (CLI `--no-render`) |
| `run(verbose)` | `False` | Print CLI-style progress (CLI uses `True`, GUI stays silent) |

The GUI exposes only `folder`, `output_dir` and `label`; the other `run()` parameters use their defaults.

### Implementation notes

* Package `labtoolbox/contact_schematic/`: `geometry.py` (146 lines), `render.py` (436 lines), `__init__.py` (117 lines — `README_TMPL`, `write_readme`, one-step `run`, re-exports), `__main__.py` (46 lines — thin argparse adapter over `run`). Exported names: `classify`, `measure_file`, `measure_geometry`, `summarise`, `write_csv`, `render_all`, `render_contact_geometry`, `render_surface_figure`, `run`, `write_readme`, `ECOLI_L/D`, `SAUREUS_D`.
* Dependencies: NumPy, SciPy (`ndimage`, `cKDTree`), matplotlib (Agg); imports `load_heightmap`, `plane_subtract`, `despike_z`, `stripe_orientation`, `surface_metrics` from `surfmetrics` (identical ZSR preprocessing) and `_setup_cjk_font` for Chinese labels.
* Entry points: the GUI tab **📐 接触几何示意 / "Contact Schematic"** (AFM data folder, sample label, output dir), `python -m labtoolbox.contact_schematic` (all flags, including `--cell/--coccus`), the unified CLI `labtoolbox schematic` (forwards `--input/--out/--label/--channel/--lam/--dpi/--no-render`), and the Python API `contact_schematic.run(...)`. The GUI and both CLI forms delegate to the same `run()` wrapper.
* The package is listed in `pyproject.toml`'s `packages` (since the integration PR), so `pip install` installations contain it, and the PyInstaller `[build]`/desktop app bundles it.
* `write_csv` writes a UTF-8-BOM CSV with a `parameter,value_nm,note` summary header, four summary rows (formatted `mean ± sd (n; min–max)`), a blank row, then a fixed per-file header. There is a harmless dead statement `f.write("") if False else None` in the summary loop.
* `render_all` writes both PNG and PDF for every figure; figures can be slow (dense `plot_surface` grids, ~20 in or larger canvases).

### Assumptions, limitations and known quirks

* **Classification is filename-only.** A file without `lipss`/`np`/`nano`/`nanopillar`/`pillar` in its path is measured for roughness but contributes no feature geometry; `summary` counts only classified files (`n_lipss`, `n_pillar`), while `n_files` counts everything.
* **Rigid, non-deforming cells.** Placement is horizontal at the highest surface point; no adhesion-induced deformation, no extracellular-polymer bridging, no orientation preference from fluid flow, no mechanics at all. Cell sizes are literature nominal values (2.0 × 0.5 µm for *E. coli*, 0.9 µm for *S. aureus*) — not measured for the user's strain; override via `--cell/--coccus`.
* **LIPSS approximated as a sinusoid** and nanopillars as a quasi-random lattice with jitter; real groove shapes and pillar arrangements are more irregular.
* **`D(r) = h + R − √(R² − r²)` is the flat-plane (SEI) relation.** On a sinusoidal ridge the local reference plane is the crest plane, not the curved surface. In fig3(a) the vertical segment labelled `h` is drawn from the sphere centre to the surface point below it (length ≈ `R + h_min`), and the `D` arrow is measured to the local sinusoid rather than to the crest reference plane — treat the annotations as schematic overlays; the formula itself is the flat/SEI convention.
* **Predicted contact points are geometric proximity only.** In the LIPSS top view the crest band is defined as the second half of each period (`|band − 0.75| ≤ 0.20`), which is an illustrative convention (the analytic 3-D cosine has its crest at Y ≡ 0 mod period); the inset is explanatory, not a projection of the 3-D panel.
* **Nanopillar spacing is a median nearest-neighbour distance** of local maxima — robust to a few missing peaks but biased when peaks are merged; the `density_per_um2` assumes square pixels and the whole field being sampled.
* **LIPSS depth is P98−P2 of the averaged profile** (not ISO `Sz`), so it can differ from `surfmetrics.Sz_nm` by design; the rotation/averaging window (middle 50 % of rows) also affects it.
* **The FFT band fallback** (`period_banded = False`) is recorded but the generated README does not report it; check the CSV if the measured period looks implausible.
* The top-view inset scale bar is drawn schematically (fixed 1 µm bar); treat inset dimensions as illustrative rather than metrically exact.
* **No rendering of `unknown`-class surfaces**: files that fail classification do not appear in fig1/fig2, and if no LIPSS files exist `fig3` is not rendered either (`render_all` needs the LIPSS period).

### QC and validation

* `geometry_measurements.csv` is the traceable record: every per-file measurement plus `n/mean/sd/median/min/max` per class; `period_banded` records whether the physical period window was used.
* The generated `README.md` intentionally lists the five assumptions that "must match the paper caption" — the module treats figure captions as part of the QC contract.
* Recommended checks: compare the measured `period_nm`/`depth_nm` with `surfmetrics` (3-D profile P-V) and `semtexture` (autocorrelation period) before publication; verify the classification keywords match the filenames; inspect the PDF (not just PNG) at full size because annotations are small.
* Smoke-tested for this documentation (base commit `0e0508e`, synthetic geometry dict, dpi = 80): `render_all` produced `fig1_LIPSS_adhesion.png`, `fig3_contact_geometry.png` and `fig2_nanopillar_adhesion.png` (all present, PNG + PDF) and `write_csv` produced the documented summary block and per-file table. The integration branch only wraps these unchanged functions in `run()` for the GUI/CLI, so the measurement/rendering behaviour documented here is unchanged.

### References

* Bhattacharjee S, Elimelech M. Surface element integration: a novel technique for evaluation of DLVO interaction between a particle and a flat plate. *J Colloid Interface Sci.* 1997;193(2):273–285. (sphere–plane `D(r)` geometry / SEI convention used in fig3)
* Israelachvili JN. *Intermolecular and Surface Forces.* 3rd ed. Academic Press; 2011. (sphere–plane geometry and Derjaguin relations underlying the contact diagrams)
* Madigan MT, Martinko JM, Bender KS, Buckley DH, Stahl DA. *Brock Biology of Microorganisms.* 15th ed. Pearson; 2018. (nominal cell sizes of *E. coli* and *S. aureus*)
* Bonse J, Höhm S, Kirner SV, Rosenfeld A, Krüger J. Laser-induced periodic surface structures — a scientific evergreen. *IEEE J Sel Top Quantum Electron.* 2017;23(3):9000615. (LIPSS morphology context for the sinusoidal approximation)
* ISO 25178-2:2012. *Geometrical product specifications (GPS) — Surface texture: Areal — Part 2: Terms, definitions and surface texture parameters.* ISO, Geneva. (the `Sa`/`Sz` values recorded per file by the shared `surfmetrics` routine)
* See also the LabToolbox module docs: [`surfmetrics`](surfmetrics.md) (height-map loading, plane subtraction, despiking, FFT stripe orientation, roughness metrics) and [`xdlvo`](xdlvo.md) (adhesion energetics — not used in the figures).

## 中文

### 目的与科学背景

`contact_schematic` 是 **AFM 分析流程的末端步骤**：从 Bruker `.ibw` 高度图测量与接触相关的真实几何（LIPSS 周期与沟深；纳米柱间距与凸起高度），再渲染细菌细胞搁置在该形貌上的出版级 3D 示意图与接触几何图。输出为图组（`fig1` LIPSS 黏附、`fig2` 纳米柱黏附、`fig3` 接触几何）、逐文件测量表，以及自动生成、写明全部假设的 README。它是*示意*模块：细胞是刚体几何形状，按实测形貌摆放——这里不做 XDLVO 或力学形变计算（那是 [`xdlvo`](xdlvo.md)）。模块可从 GUI（标签页 **📐 接触几何示意**）、统一 CLI（`labtoolbox schematic` / `python -m labtoolbox.contact_schematic`）以及一步式 Python API `contact_schematic.run()` 调用。

### 输入与数据格式

命令行（`python -m labtoolbox.contact_schematic` 或统一入口 `labtoolbox schematic`）：

| 参数 | 默认值 | 含义 |
|---|---|---|
| `--input` | 必填 | `.ibw` 文件或目录（目录时递归 `**/*.ibw`） |
| `--out` | CLI 必填；统一 CLI 默认 `output` | 输出目录 |
| `--label` | `515 nm` | 标题中的样品标签 |
| `--channel` | `zsr` | `.ibw` 通道名（预处理与 `surfmetrics` 相同） |
| `--lambda` / `--lam` | `515` | 激光波长（nm）；决定 FFT 周期带 `(0.5λ, 1.5λ)` |
| `--dpi` | `190` | 图分辨率 |
| `--cell` | `2.0x0.5` | *E. coli* 长 × 直径（µm） |
| `--coccus` | `0.9` | *S. aureus* 直径（µm） |
| `--no-render` | 关 | 只测量并写 CSV，不画图 |

统一 CLI（`labtoolbox schematic`）只转发 `--input/--out/--label/--channel/--lam/--dpi/--no-render`，**不暴露** `--cell/--coccus`（这两个要用 `python -m labtoolbox.contact_schematic`）。

GUI 标签页 **📐 接触几何示意 / "Contact Schematic"** 暴露 AFM 数据目录、样品标签（默认 `515 nm`）与输出目录；它用其余默认值（ZSR 通道、λ = 515 nm、dpi = 190、文献细胞尺寸、渲染开启）运行同一个一步式 API。

共享 Python 入口（两种 CLI 形式与 GUI 都调用）：

```python
contact_schematic.run(folder, output_dir="output", label="515 nm", channel="zsr",
                      lam_nm=515.0, dpi=190, cell=(2.0, 0.5), coccus=0.9,
                      render=True, verbose=False)
```

返回 `{"csv", "summary", "figures", "readme", "n_files"}`；`render=False` 等价于 CLI 的 `--no-render`，`verbose=True` 打印 CLI 式进度。

表面分类是**基于文件名**的（`geometry.classify`）：小写路径含 `lipss` → LIPSS；含 `np`（词边界）、`nano`、`nanopillar` 或 `pillar` → 纳米柱；否则为 `unknown`（仍测量 Sa/Sq/Sz，但不提取特征几何，也不进入示意图汇总）。

### 输出

| 文件 | 内容 |
|---|---|
| `fig1_LIPSS_adhesion.png` / `.pdf` | 5 面板：(a) LIPSS 形貌 + 剖面；(b) *E. coli* 平行 0°；(c) 45°；(d) 垂直 90°；(e) *S. aureus* 球菌。每个细胞面板带俯视小图；图例 + 标题中给出实测周期/纹深 |
| `fig2_nanopillar_adhesion.png` / `.pdf` | 同样版式，画在实测纳米柱阵列上（标题给出间距/高度） |
| `fig3_contact_geometry.png` / `.pdf` | (a) 脊上方球体——SEI 几何 `D(r) = h + R − √(R²−r²)`；(b) 杆菌平行条纹——与沟侧壁真实相切；(c) 杆菌垂直——只碰脊顶（侧视） |
| `geometry_measurements.csv` | 汇总区（四个主量的 mean ± sd (n; min–max)）+ 全部文件的逐文件测量值 |
| `README.md` | 自动生成（中文）说明：实测几何、文件清单，以及必须与论文图注一致的 5 条假设 |

`render_all` 的返回值是实际生成的 PNG 路径列表。一步式 `run()` 返回 `{"csv": path, "summary": dict, "figures": [png 路径], "readme": path, "n_files": int}`。

### 端到端流程

所有入口——GUI 标签页、`python -m labtoolbox.contact_schematic`、`labtoolbox schematic` 与 Python API——都调用 `contact_schematic.run(folder, ...)`：它创建输出目录并执行下列步骤；`__main__.py` 只是其上的薄 argparse 适配层。

1. **发现文件**（`measure_geometry`）：接受单个文件、glob 或目录（递归 `.ibw`）；每个文件独立测量，失败记为 `{"class": "error", "error": ...}` 而不中断整批。
2. **测量单文件**（`measure_file`）：`load_heightmap(channel="zsr")` → `plane_subtract` → `despike_z`（5σ 中值去尖峰）→ `surface_metrics` → `Sa`、`Sq`、`Sz`；随后做分类专属几何（见下）。
3. **汇总**（`summarise`）：对每个类别与量计算 `n`、`mean`、`sd`（ddof=1）、`median`、`min`、`max`；返回渲染器使用的字典（`lam_nm`、`lipss`、`nanopillar`、`n_files`、`n_lipss`、`n_pillar`）。
4. **写 CSV**（`write_csv`）：先写 `LIPSS.period_nm`、`LIPSS.depth_nm`、`Nanopillar.spacing_nm`、`Nanopillar.height_nm` 的汇总行，再空行，最后逐文件表。
5. **渲染**（`render_all`）：有 LIPSS 统计时出 `fig1` + `fig3`；有纳米柱统计时出 `fig2`（均 PNG + PDF）。
6. **写 README**（`write_readme`）：实测数值 + 固定假设清单。
7. **返回**产物 dict `{csv, summary, figures, readme, n_files}`。

#### 分类专属测量

**LIPSS**（`class == "lipss"`）：

* 周期：`surfmetrics.stripe_orientation(z, px, py, band_nm=(0.5λ, 1.5λ))`——与 `surfmetrics` 相同的二维 FFT 峰搜索，限制在物理可能的周期带内以避开 ZSR 的 µm 级扫描伪影。`period_nm = 1/|f_peak|`；`stripe_deg = ridge_deg = cross_deg + 90°`。带内无峰时改用全谱重搜，并记录 `period_banded = False`。
* 纹深：把高度图旋转 `−cross_deg`，使周期方向变为水平；沿条纹方向对中间一半行取平均；`depth_nm = P98 − P2`（比 `Sz` 稳健，后者被孤立尖峰拉大）。`feature_nm = depth_nm`。

**纳米柱**（`class == "nanopillar"`）：

* 阈值 `median(z) + 1.5·std(z)`；峰 = 高于阈值的 7×7 局部极大。
* 峰数 ≥ 5 时：用 `scipy.spatial.cKDTree`（k=2）求最近邻距离，`spacing_nm = 最近邻距离中位数`；`n_peaks`；`density_per_um2 = n_peaks / (h·px/1000)²`（假设方形像素）。
* `height_nm = P90(z) − median(z)`；`feature_nm = height_nm`。
* 峰数 < 5 → `spacing_nm = NaN`（高度仍报告）。

### 几何与渲染细节

* fig1/fig2 的**视野**：5.5 µm × 2.8 µm，每面板单坐标轴、正交投影，细胞**严格按比例**绘制（本模块任何图都不做纵向夸张）。
* **解析 LIPSS 表面**：`z = (depth/2)·cos(2πY/period) − depth/2`，即起伏沿 Y 变化、条纹沿 X 延伸。因此 0° 的杆菌平行于条纹（项目约定）。
* **合成纳米柱表面**（`seed = 7`，确定性）：名义网格 `(i − 0.5)·spacing`；每个柱心加 N(0, 0.02·spacing) 抖动，半径 `0.36·spacing·(1 + N(0, 0.10))`，高度 `height·(1 + N(0, 0.12))`，径向剖面 `h·cos²(clip(d/r, 0, 1)·π/2)`；对柱求和后平移到最小值为 0。
* **细胞**：*E. coli* 为胶囊网格（半球帽 + 圆柱，轴向 16 + 34 + 16 站、周向 64 点）；*S. aureus* 为球网格（56 × 56）。细胞放在视野中央，中心取 `z_top + 细胞半高`，即**搁在最高点**，不贴合局部形貌。表面着色用自定义法线 + 定向光（`LightSource(azdeg=235, altdeg=32)`）；配色：灰色表面、绿色杆菌、橙色球菌、红色虚线尺寸标注、蓝色虚线俯视/剖面边框。
* **俯视小图**（每个细胞面板）：示意图平面视图，带固定小比例尺；杆菌按取向画出，并标“预测接触点”：LIPSS 上只有落到脊顶带内的采样点才画点（`|band − 0.75| ≤ 0.20` 个周期）；纳米柱上每个采样点都标。这些点只表示几何接近，不是算出来的接触力学。
* **fig3**：正弦起伏 `z = (depth/2)·cos(2πx/period)`；(a) 半径 `R = coccus/2`（nm）的球，最小间隙置于脊顶上方 **60 nm**，标注 `h`、`R`、`r`、`θ`、`D(r)`、`Λ` 与纹深；(b) 平行条纹的杆菌用半径 `R = E. coli 直径/2` 的圆表示，与沟侧壁真实相切（圆心在 1.5Λ 的脊上；与表面距离为局部极小且 ≤ 1.002R 处画接触标记）；(c) 垂直杆菌：侧视表示横跨脊的杆——半透明绿色带搁在脊顶平面，每个脊顶画红点，`h` 标注为脊-谷深度。生成的 README 明确写出：图是刚性体示意图、LIPSS 按正弦近似、纳米柱按准周期阵列近似、`D(r)` 采用等效球–平面（SEI）约定。

### 参数与默认值

| 参数 | 默认值 | 含义 |
|---|---|---|
| `--input` | 必填 | `.ibw` 文件/目录 |
| `--out` | 必填 | 输出目录 |
| `--label` | `515 nm` | 标题样品标签 |
| `--channel` | `zsr` | `.ibw` 通道（优先 ZSensor Retrace） |
| `--lambda` | `515` nm | FFT 物理周期窗 `(0.5λ, 1.5λ)` |
| `--dpi` | `190` | PNG/PDF 分辨率 |
| `--cell` | `2.0x0.5` µm | *E. coli* 长 × 直径（`render.ECOLI_L`、`render.ECOLI_D`） |
| `--coccus` | `0.9` µm | *S. aureus* 直径（`render.SAUREUS_D`） |
| `--no-render` | 关 | 只出 CSV |
| 剖面带因子 | 0.5 | `measure_file(..., profile_band=0.5)` → 带 `(0.5λ, 1.5λ)` |
| 去尖峰 | 5σ、3 次迭代、3×3 中值 | 沿用 `surfmetrics.despike_z` 默认值 |
| 平面扣除 | 始终开启 | `measure_file` 内调用 `plane_subtract` |
| 柱峰过滤 | 7×7 极大、`median+1.5σ` | `maximum_filter(size=7)` |
| 最少峰数 | 5 | 低于此值不报告柱间距 |
| `run(folder)` | 必填 | 一步式 API：`.ibw` 文件/目录 → CSV（+ 图/README） |
| `run(output_dir)` | `"output"` | 输出目录 |
| `run(label)` | `"515 nm"` | 标题样品标签 |
| `run(channel)` | `"zsr"` | `.ibw` 通道 |
| `run(lam_nm)` | `515.0` | FFT 物理周期窗 `(0.5λ, 1.5λ)` |
| `run(dpi)` | `190` | 图分辨率 |
| `run(cell)` | `(2.0, 0.5)` µm | *E. coli*（长，直径） |
| `run(coccus)` | `0.9` µm | *S. aureus* 直径 |
| `run(render)` | `True` | `False` = 只出 CSV（CLI `--no-render`） |
| `run(verbose)` | `False` | 打印 CLI 式进度（CLI 用 `True`，GUI 静默） |

GUI 只暴露 `folder`、`output_dir`、`label`；其余 `run()` 参数使用默认值。

### 实现说明

* 包 `labtoolbox/contact_schematic/`：`geometry.py`（146 行）、`render.py`（436 行）、`__init__.py`（117 行——`README_TMPL`、`write_readme`、一步式 `run` 与再导出）、`__main__.py`（46 行——`run` 上的薄 argparse 适配层）。导出名：`classify`、`measure_file`、`measure_geometry`、`summarise`、`write_csv`、`render_all`、`render_contact_geometry`、`render_surface_figure`、`run`、`write_readme`、`ECOLI_L/D`、`SAUREUS_D`。
* 依赖：NumPy、SciPy（`ndimage`、`cKDTree`）、matplotlib（Agg）；从 `surfmetrics` 导入 `load_heightmap`、`plane_subtract`、`despike_z`、`stripe_orientation`、`surface_metrics`（同一套 ZSR 预处理），并导入 `_setup_cjk_font` 显示中文。
* 入口：GUI 标签页 **📐 接触几何示意 / "Contact Schematic"**（AFM 数据目录、样品标签、输出目录），`python -m labtoolbox.contact_schematic`（全部参数，含 `--cell/--coccus`），统一 CLI `labtoolbox schematic`（转发 `--input/--out/--label/--channel/--lam/--dpi/--no-render`），以及 Python API `contact_schematic.run(...)`。GUI 与两种 CLI 形式都委托给同一个 `run()` 包装。
* 该包自集成分支起列入 `pyproject.toml` 的 `packages`，因此 `pip install` 安装会包含它，PyInstaller `[build]`/桌面应用也会打包它。
* `write_csv` 写 UTF-8-BOM CSV：`parameter,value_nm,note` 汇总表头，四行汇总（格式 `mean ± sd (n; min–max)`），空行，再逐文件固定表头。汇总循环里有一句无害的死代码 `f.write("") if False else None`。
* `render_all` 每张图同时写 PNG 与 PDF；图可能较慢（密集 `plot_surface` 网格、约 20 英寸或更大的画布）。

### 假设、局限与已知怪癖

* **仅按文件名分类。** 路径中不含 `lipss`/`np`/`nano`/`nanopillar`/`pillar` 的文件只测粗糙度、不贡献特征几何；`summarise` 只统计已分类文件（`n_lipss`、`n_pillar`），而 `n_files` 统计全部。
* **刚性、不变形的细胞。** 水平放置在最高点；无黏附形变、无胞外聚合物桥接、无流场取向偏好、完全没有力学。细胞尺寸是文献标称值（*E. coli* 2.0 × 0.5 µm，*S. aureus* 0.9 µm），不是用户菌株实测值；可用 `--cell/--coccus` 覆盖。
* **LIPSS 按正弦近似**，纳米柱按带抖动的准随机阵列近似；真实沟形与柱排布更不规则。
* **`D(r) = h + R − √(R² − r²)` 是平面（SEI）关系。** 正弦脊上局部参考平面是脊顶平面而不是弯曲表面。fig3(a) 中标注为 `h` 的竖线是从球心画到其下表面点（长度约 `R + h_min`），`D` 箭头量到局部正弦面而非脊顶参考平面——请把标注当作示意叠加；公式本身是平面/SEI 约定。
* **预测接触点只是几何接近。** LIPSS 俯视图中脊顶带定义为每周期后半段（`|band − 0.75| ≤ 0.20`），这是示意约定（解析 3D 余弦的脊顶在 Y ≡ 0 mod 周期）；小图是解释性的，不是 3D 面板的投影。
* **纳米柱间距是局部极大的最近邻距离中位数**——对少量缺失峰稳健，但峰被合并时会有偏；`density_per_um2` 假设方形像素且整场被采样。
* **LIPSS 纹深是平均剖面的 P98−P2**（不是 ISO `Sz`），因此可能与 `surfmetrics.Sz_nm` 不同（设计如此）；旋转/平均窗口（中间 50 % 行）也会影响它。
* **FFT 带外回退**（`period_banded = False`）会被记录，但生成的 README 不报告它；实测周期异常时请查 CSV。
* 俯视小图的比例尺是示意性的（固定 1 µm 标尺）；小图尺寸只能当示意，不能当精确度量。
* **不渲染 `unknown` 类表面**：分类失败的文件不出现在 fig1/fig2；若没有任何 LIPSS 文件，`fig3` 也不会出（`render_all` 需要 LIPSS 周期）。

### 质控与验证

* `geometry_measurements.csv` 是可追溯记录：逐文件测量值 + 每类的 `n/mean/sd/median/min/max`；`period_banded` 记录是否用了物理周期窗。
* 生成的 `README.md` 刻意列出“必须与论文图注一致”的 5 条假设——模块把图注视为 QC 契约的一部分。
* 建议检查：发表前把实测 `period_nm`/`depth_nm` 与 `surfmetrics`（3D 剖面 P-V）及 `semtexture`（自相关周期）对比；确认分类关键词与文件名匹配；按原始尺寸查看 PDF（而不只是 PNG），因为标注较小。
* 本文档冒烟测试（基线 commit `0e0508e`，合成几何 dict，dpi = 80）：`render_all` 生成 `fig1_LIPSS_adhesion.png`、`fig3_contact_geometry.png` 与 `fig2_nanopillar_adhesion.png`（均存在，PNG + PDF），`write_csv` 生成文档所述的汇总区与逐文件表。集成分支只是把这些未改动的函数包进 `run()` 供 GUI/CLI 使用，因此这里记录的测量/渲染行为不变。

### 参考文献

* Bhattacharjee S, Elimelech M. Surface element integration: a novel technique for evaluation of DLVO interaction between a particle and a flat plate. *J Colloid Interface Sci.* 1997;193(2):273–285.（fig3 使用的球–平面 `D(r)` 几何 / SEI 约定）
* Israelachvili JN. *Intermolecular and Surface Forces.* 3rd ed. Academic Press; 2011.（接触示意图背后的球–平面几何与 Derjaguin 关系）
* Madigan MT, Martinko JM, Bender KS, Buckley DH, Stahl DA. *Brock Biology of Microorganisms.* 15th ed. Pearson; 2018.（*E. coli* 与 *S. aureus* 的标称细胞尺寸）
* Bonse J, Höhm S, Kirner SV, Rosenfeld A, Krüger J. Laser-induced periodic surface structures — a scientific evergreen. *IEEE J Sel Top Quantum Electron.* 2017;23(3):9000615.（正弦近似所用 LIPSS 形貌背景）
* ISO 25178-2:2012. *Geometrical product specifications (GPS) — Surface texture: Areal — Part 2: Terms, definitions and surface texture parameters.* ISO, Geneva.（共享 `surfmetrics` 流程为每个文件记录的 `Sa`/`Sz` 值）
* 另见 LabToolbox 模块文档：[`surfmetrics`](surfmetrics.md)（高度图读取、平面扣除、去尖峰、FFT 条纹取向、粗糙度指标）与 [`xdlvo`](xdlvo.md)（黏附能量学——不用于本模块的图）。
