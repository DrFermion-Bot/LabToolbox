# livedead_cellcounter — Automated LIVE/DEAD fluorescence counting / LIVE/DEAD 荧光图像细胞计数

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

This module automates counting of LIVE/DEAD fluorescence micrographs organised in a **replicate → time point → area** folder hierarchy and turns the counts into viability statistics. Each field is imaged in two channels: green (`g`, SYTO 9 → live, membrane-intact cells) and red (`r`, propidium iodide → dead, membrane-damaged cells); the module pairs the two files of the same field and reports live/dead counts, pooled viability, a stacked bar chart and a two-way ANOVA. It replaces manual ImageJ clicking and is the image-side front end of the [`livedead`](livedead.md) statistics module.

Two counting engines exist:

* **`ImageJ` (default, reference methodology)** — classic ImageJ 1.54 headless batch with a project macro: adaptive threshold = histogram-mode background + 40, optional brightest-channel fallback, `Analyze Particles` size filter. Installed ImageJ is required.
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

`ImageJEngine` requires an ImageJ installation with `ij.jar` and `jre/bin/java.exe`; it probes `E:/ImageJ/ImageJ`, `F:/ImageJ/ImageJ`, `C:/Users/PC/Downloads/ImageJ` in that order (`find_imagej_dir()`). The macro is looked up at `<ImageJ>/macros/count_livedead.ijm`; if absent, the repository copy `scripts/imagej/count_livedead.ijm` is copied there automatically (or read in place if the copy fails).

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

### Implementation notes

* Package `labtoolbox/livedead_cellcounter/cellcounter.py` (581 lines); dependencies NumPy, pandas, matplotlib (Agg); ImageJ backend additionally uses only the Java subprocess + `csv`; OpenCV backend needs `opencv-python`.
* Classes/functions: `find_imagej_dir`, `ImageJEngine` (`_macro_path`, `_batch_dir`, `count_live_dead`, `count_live_dead_pair`), `CellCounterEngine` (`extract_channel`, `count_cells_in_channel`, `count_live_dead`), `parse_filename`, `LiveDeadCellCounter` (`scan_structure`, `count_all`, `summarize`, `anova`, `plot`, `report`), `run`.
* At commit `0e0508e` the module is **not registered in the unified CLI** (`labtoolbox/cli.py` has no cell-counter subcommand) and pyproject's package list does not include it; the supported entry points are the Python API and the GUI tab **🔬 LIVE/DEAD 细胞计数**.
* `run()` forwards `**engine_kwargs` to the selected engine; `verbose` is **not** an accepted argument of `run()` (passing it raises `TypeError`), only of `report()`.
* The macro file must stay pure ASCII (ImageJ does not read macro files as UTF-8); its header documents the 5-line argument protocol.
* A Chinese font is registered on import from `C:\Windows\Fonts\msyh.ttc`/`simhei.ttf` when present. The figure title/labels are hard-coded English.

### Assumptions, limitations and known quirks

* **Strict folder/filename contract.** Any deviation (extra separators, different naming, missing number) makes the file invisible to the scanner; `area` may only be `c` or an integer.
* **ImageJ engine only counts `.tif`.** The scanner accepts `.png/.jpg/.bmp` but the macro skips them, so such files silently contribute 0 counts when `backend="imagej"`.
* **Pixel-only particle-size filter.** The macro resets spatial calibration, so `min_size/max_size` are in pixels (3–500 px² defaults were tuned for the group's 3 k micrographs); no µm² calibration is applied.
* **The bar-chart ANOVA annotation usually does not appear.** The plotting code looks for an `"p"` column, but the statsmodels branch returns `factor/sum_sq/df/F/PR(>F)`; only the fallback branch has `p`. Consequently the annotation is effectively limited to the fallback path (`aov["p"].iloc[0]` is then the first time point's p-value).
* **Time ordering is lexicographic.** Times are sorted as strings (`"10h"` sorts before `"2h"`); rename to zero-padded labels if order matters.
* **ANOVA is on log10(live+1) counts**, not viability; `log10=True` is the default, Type II SS, unbalanced cells are not modelled explicitly, no post-hoc tests, no multiplicity correction, no random effect for repeat.
* **GUI parameters are partly inert.** The GUI passes `min_roundness`, `green_thresh`, `red_thresh`; in the default ImageJ mode these keys are filtered out by `run()` and silently ignored (only `min_size`/`max_size`/`bg_offset`/`qc_dir`/`imagej_dir` reach the ImageJ engine). The tooltip in the GUI states this.
* **`area_um2` is dead code**; no area-normalised density is computed.
* **Channel-trap heuristic** (brightest channel when named channel is dim) is a pragmatic fix, not a physical measurement; review QC overlays when counts look surprising.
* `skip_repeats` matches folder names exactly (case-sensitive); pass the names as they appear on disk.
* **OpenCV backend is retained only for regression/troubleshooting.** Its fixed thresholds and watershed parameters were superseded by the ImageJ method (project decision, 2026-09-11); historical comparison on the 515 nm series (160 paired fields) attributed most ImageJ-vs-OpenCV differences to the old engine lacking the channel-trap correction.

### QC and validation

* Optional per-image QC overlays (`qc_dir` → `<stem>_qc.png`) show each counted particle with number, the channel actually used and the threshold; this is the primary visual QC.
* Raw CSV keeps `g_image`, `r_image` and per-pair errors, so every count is traceable to a file.
* Cross-engine historical comparison is reproducible with `scripts/compare_count_backends.py` (outputs not committed); the project has standardised on ImageJ, so the OpenCV engine is not a validation oracle.
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

本模块自动计数按 **重复 → 时间点 → 区域** 文件夹层级组织的 LIVE/DEAD 荧光显微图，并把计数转成存活率统计。每个视野成对拍摄两个通道：绿色（`g`，SYTO 9 → 活菌、膜完整）与红色（`r`，碘化丙啶 → 死菌、膜受损）；模块把同一视野的两张图配对，输出活/死计数、合并存活率、堆叠柱状图与双因素 ANOVA。它替代手工 ImageJ 点选，是 [`livedead`](livedead.md) 统计模块的图像侧前端。

存在两个计数引擎：

* **`ImageJ`（默认，方法学基准）**——经典 ImageJ 1.54 headless 批处理 + 项目宏：自适应阈值 = 直方图众数背景 + 40，可选最亮通道回退，`Analyze Particles` 面积过滤。需要已安装 ImageJ。
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

`ImageJEngine` 需要含 `ij.jar` 与 `jre/bin/java.exe` 的 ImageJ 安装；依次探测 `E:/ImageJ/ImageJ`、`F:/ImageJ/ImageJ`、`C:/Users/PC/Downloads/ImageJ`（`find_imagej_dir()`）。宏文件先找 `<ImageJ>/macros/count_livedead.ijm`；缺失时自动把仓库副本 `scripts/imagej/count_livedead.ijm` 拷过去（拷贝失败则直接从仓库位置读取）。

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

### 实现说明

* 包 `labtoolbox/livedead_cellcounter/cellcounter.py`（581 行）；依赖 NumPy、pandas、matplotlib（Agg）；ImageJ 后端额外只用 Java 子进程 + `csv`；OpenCV 后端需要 `opencv-python`。
* 类/函数：`find_imagej_dir`、`ImageJEngine`（`_macro_path`、`_batch_dir`、`count_live_dead`、`count_live_dead_pair`）、`CellCounterEngine`（`extract_channel`、`count_cells_in_channel`、`count_live_dead`）、`parse_filename`、`LiveDeadCellCounter`（`scan_structure`、`count_all`、`summarize`、`anova`、`plot`、`report`）、`run`。
* commit `0e0508e` 时该模块**未注册进统一 CLI**（`labtoolbox/cli.py` 没有 cell-counter 子命令），pyproject 的包列表也未包含它；可用入口是 Python API 与 GUI 标签页 **🔬 LIVE/DEAD 细胞计数**。
* `run()` 把 `**engine_kwargs` 转给所选引擎；`verbose` **不是** `run()` 的参数（传入会 `TypeError`），只有 `report()` 有。
* 宏文件必须保持纯 ASCII（ImageJ 不以 UTF-8 读宏文件）；其头部注释记录了 5 行参数协议。
* 导入时若存在 `C:\Windows\Fonts\msyh.ttc`/`simhei.ttf` 会注册中文字体。图的标题/轴标签为硬编码英文。

### 假设、局限与已知怪癖

* **严格的文件夹/文件名契约。** 任何偏差（多余分隔符、不同命名、缺编号）都会让文件对扫描器不可见；`area` 只能是 `c` 或整数。
* **ImageJ 引擎只数 `.tif`。** 扫描器接受 `.png/.jpg/.bmp`，但宏会跳过它们，因此在 `backend="imagej"` 下这些文件静默贡献 0 计数。
* **粒子面积过滤只有像素单位。** 宏重置了空间标定，因此 `min_size/max_size` 是像素（默认 3–500 px² 按本组 3k 显微图调校）；没有 µm² 标定。
* **柱状图的 ANOVA 标注通常不出现。** 绘图代码找 `"p"` 列，但 statsmodels 分支返回的是 `factor/sum_sq/df/F/PR(>F)`；只有回退分支有 `p`。因此标注实际只限于回退路径（此时 `aov["p"].iloc[0]` 是第一个时间点的 p 值）。
* **时间排序按字典序。** 时间按字符串排序（`"10h"` 排在 `"2h"` 前）；若顺序重要请改成补零标签。
* **ANOVA 作用于 log10(live+1) 计数**，不是存活率；`log10=True` 是默认，Type II 平方和，不显式建模不平衡单元，无事后检验、无多重比较校正、不把重复当随机效应。
* **GUI 参数有一部分失效。** GUI 会传 `min_roundness`、`green_thresh`、`red_thresh`；默认 ImageJ 模式下这些键被 `run()` 过滤掉并静默忽略（只有 `min_size`/`max_size`/`bg_offset`/`qc_dir`/`imagej_dir` 会到达 ImageJ 引擎）。GUI 的提示文字已说明这一点。
* **`area_um2` 是死代码**；不计算任何面积归一化密度。
* **通道陷阱启发式**（命名通道很暗时改数最亮通道）是务实的修正，不是物理测量；计数异常时请查看 QC 叠加图。
* `skip_repeats` 精确匹配文件夹名（区分大小写）；请按磁盘上的实际名称传入。
* **OpenCV 后端只为回归/排障保留。** 其固定阈值与分水岭参数已被 ImageJ 方法取代（项目决定，2026-09-11）；515 nm 系列 160 对视野的历史对比显示 ImageJ 与 OpenCV 的差异主要来自旧引擎缺少通道陷阱修正。

### 质控与验证

* 可选的逐图 QC 叠加图（`qc_dir` → `<stem>_qc.png`）显示每个被计数粒子的编号、实际使用的通道与阈值；这是主要的目视 QC。
* 原始 CSV 保留 `g_image`、`r_image` 与逐对错误信息，每个计数都可追溯到文件。
* 跨引擎历史对比可用 `scripts/compare_count_backends.py` 复现（输出不入库）；项目已统一到 ImageJ，因此 OpenCV 引擎不是验证基准。
* 本文档核对演示（commit `0e0508e`，Python 3.11、OpenCV 4.13、`backend="opencv"`）：`examples/livedead_counter_demo` → 24 对；例如 repeat1/1h/Area1：live 13、dead 12；汇总 Area1 1h = 48.2 % 存活率（n = 6 对）；ANOVA 表如上（Type II、log10 活菌计数）。ImageJ 后端在文档编写机器上无法运行（无 ImageJ 安装），其行为依据宏源码描述。

### 参考文献

* Schneider CA, Rasband WS, Eliceiri KW. NIH Image to ImageJ: 25 years of image analysis. *Nat Methods.* 2012;9:671–675. doi:10.1038/nmeth.2089.
* Ferreira T, Rasband W. *ImageJ User Guide IJ 1.46r.* National Institutes of Health; 2012.（ImageJ 命令参考：`Set Scale`、`Split Channels`、阈值化、`Analyze Particles`；https://imagej.nih.gov/ij/docs/guide/）
* Bradski G. The OpenCV Library. *Dr. Dobb's Journal of Software Tools.* 2000.（旧引擎使用的 OpenCV 函数：`threshold`、形态学、`distanceTransform`、`watershed`、`connectedComponentsWithStats`）
* Thermo Fisher Scientific. *LIVE/DEAD™ BacLight™ Bacterial Viability Kit (L7012) — product manual.*（染色化学与判读）
* Berney M, Hammes F, Bosshard F, Weilenmann HU, Egli T. Assessment and interpretation of bacterial viability by using the LIVE/DEAD BacLight Kit in combination with flow cytometry. *Appl Environ Microbiol.* 2007;73(10):3283–3290. doi:10.1128/AEM.02750-06.
* Seabold S, Perktold J. statsmodels: econometric and statistical modeling with Python. *Proc 9th Python in Science Conf.* 2010:92–96.（双因素 ANOVA）
* 本仓库宏文件 `scripts/imagej/count_livedead.ijm`（默认引擎使用的确切计数流程）。
