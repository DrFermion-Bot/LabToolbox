# lipss_dloa — LIPSS period & orientation from SEM images (DLOA) / SEM 图像 LIPSS 周期与取向角分析

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

`lipss_dloa` measures the period `Λ` and the orientation of laser-induced periodic surface structures (LIPSS) from grazing-incidence SEM micrographs. It is the project's **DLOA** ("diffraction-pattern / FFT-spot orientation analysis"): instead of thresholding individual ripples, the 2-D Fourier transform of the whole field is computed, the diffraction spots are detected, and their angular distribution gives the dominant ripple orientation and its spread. Typical use: quick, whole-field characterisation of laser-textured stainless-steel coupons (515 nm wavelength family) before AFM-based profile analysis (see [`surfmetrics`](surfmetrics.md)) and multi-coupon consistency analysis (see [`semtexture`](semtexture.md)).

The module is a straight port of the validated "sem-fft-analysis" spot-DLOA script (6 samples, spacing 449–482 nm); its known weaknesses motivated the later autocorrelation-based pipeline in `semtexture`.

### Inputs and data formats

| Input | Type | Default | Meaning |
|---|---|---|---|
| `folder` / `--folder` | str, required | — | Folder of SEM images (recursive listing is **not** done; only files directly in the folder) |
| `pixel_size_um` | float | `1/32 µm` = 31.25 nm/px | Pixel size; CLI exposes it as `--pixel-per-um` (default 32), GUI as "每微米像素数" |
| `output_dir` / `--output` | str | `output` | Output directory |

* Accepted image extensions: `.bmp`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`; images are read as 8-bit grayscale through `cv2.imdecode(np.fromfile(path))`, which supports Chinese/Unicode paths.
* Files whose lower-case name contains `_fft`, `_annotated`, `_spectrum` or `result_` are skipped (to avoid re-analysing old outputs).
* Images are analysed as plain intensity fields; there is no scale-bar detection — the pixel size must be supplied.
* Bundled test image: `data/examples/sem_test/lipss_test_45deg.bmp` (512 × 512, synthetic diagonal fringes, 5.657 px period = 176.8 nm at 31.25 nm/px).

### Outputs

| Output | Content |
|---|---|
| `output/LIPSS_orientation_angles.csv` | One row per successfully analysed image: `file`, `theta_fft_deg`, `lipss_angle_deg`, `fwhm_2dtheta_deg`, `spacing_nm` |
| `output/dloa_<file>.png` | Orientation-distribution curve (magenta) with the detected `theta_fft` marked (red dashed line) |
| return dict | `{"results": [row dicts], "csv": path}` — invalid images are silently skipped (`None`) and do not appear |

### End-to-end pipeline

1. **Read** the grayscale image.
2. **Crop the bottom dark band** (SEM footer / scale-bar strip): row means are scanned from the bottom row upwards; while a row mean is `< 30` (8-bit intensity) it is removed; the crop stops at the first bright row. If the last row is bright, nothing is removed.
3. **Reject degenerate fields**: empty image or `min(shape) < 200` px → return `None`.
4. **Windowed log power spectrum**: multiply by a separable Hann window `W(i,j) = hann(h)_i · hann(w)_j`; compute `F = fftshift(fft2(img · W))`; then `L = ln(1 + gaussian(|F|², σ = 1.5))`.
5. **Detect diffraction spots** in `L`: strict local maxima over the 8 neighbours, outside a central disk of radius `exclude_radius = 40` px; sort by `L` descending; take the `n_top = 20` strongest; keep only spots with radius `r ≥ min_radius = 45` px; store `(α mod 180°, r, L)`.
6. **Orientation distribution**: histogram the spot angles into 181 bins over `[0, 180)°` with the spot amplitudes as weights; smooth with a Gaussian (`σ = 2` bins); subtract the minimum and normalise the maximum to 1.
7. **Report**: `theta_fft_deg` = bin centre of the distribution maximum; `lipss_angle_deg = (theta_fft + 90) mod 180` (ridge direction, by convention); `fwhm_2dtheta_deg` = width of the region where the (smoothed) distribution is `≥ 50 %` of its peak; `spacing_nm` from the strongest kept spot.
8. **Figure** (per image): the orientation distribution, `θ_fft` line, axis labels `Orientation in Degree` / `Distribution of Orientation (a.u.)`.

### Algorithms and formulas

```
p            pixel size (µm), default 1/32
f_nyq        = 1 / (2p)                      cycles/µm (Nyquist; 16 cycles/µm at 31.25 nm/px)
L(u,v)       = ln(1 + G_σ=1.5( |FFT2(img · W)|² ))
spot         strict 8-neighbour local maximum of L, outside r < 40 px
α            = atan2(dy, dx) mod 180°       (dy, dx = spot offset from the FFT centre)
D(θ)         = normalise( G_σ=2( hist(α; weights = L_spot) ) − min )
θ_fft        = argmax_θ D(θ)
Λ_ridge      = (θ_fft + 90°) mod 180°
FWHM         = θ_last − θ_first  over  { θ : D(θ) ≥ 0.5 · max D }
```

Spacing from the strongest spot (`r` in pixels, image width `w`):

```
k [cycles/µm] = r · f_nyq / (w/2) = r / (w · p)
Λ [nm]        = 1000 / k = w · (p·1000 [nm]) / r
```

With the defaults and a 512-px-wide image: measurable period range is roughly `2p … w·p/45` = 62.5 … 356 nm; for 1024-px images the upper limit is ≈711 nm. (The lower bound is the Nyquist limit; the upper bound comes from `min_radius = 45` px.)

### Parameters and defaults

| Parameter | Default | Meaning |
|---|---|---|
| `pixel_size_um` | `1/32` µm (31.25 nm/px) | Physical pixel size; set from the SEM magnification / scale bar |
| `exclude_radius` | 40 px | Radius of the central FFT disk ignored (DC/low-frequency haze) |
| `n_top` | 20 | Number of strongest local maxima kept as candidate spots |
| `min_radius` | 45 px | Minimum spot radius; also sets the largest measurable period |
| CLI `--pixel-per-um` | 32 | Inverse pixel size (pixels per µm) |
| `output_dir` | `output` | Output directory (created if missing) |

`DLOAAnalyzer(pixel_size_um=..., exclude_radius=40, n_top=20, min_radius=45)` exposes all thresholds; `run(folder, output_dir, pixel_size_um)` is the convenience entry point.

### Implementation notes

* Package `labtoolbox/lipss_dloa/`: `dloa.py` (163 lines). Dependencies: NumPy, SciPy (`ndimage.gaussian_filter`), OpenCV (`cv2.imdecode` for Unicode-path grayscale reading), pandas (imported lazily in `analyze_folder` for the CSV), matplotlib (Agg).
* `DLOAAnalyzer` methods: `_read_gray`, `_detect_black_border`, `_log_power`, `_find_spots`, `_distribution`, `_fwhm` (static), `analyze_image`, `analyze_folder`.
* Spot detection is a pure-Python nested loop over all pixels (`for i in range(2, h-2): for j in range(2, w-2)`), i.e. O(N²) per image — slow for large SEM images (acceptable for 1–3 k images).
* `analyze_folder` sorts the file list, analyses each image with a figure and collects rows into `LIPSS_orientation_angles.csv` (UTF-8 with BOM). If no image is valid, `pandas.DataFrame([])` is written as an empty file.
* CLI `labtoolbox lipss-dloa --folder ... [--pixel-per-um 32] [--output ...]`; GUI tab **🔬 LIPSS/DLOA** (default 32 px/µm). The unified CLI registers `lipss-dloa` in `labtoolbox/cli.py`.

### Assumptions, limitations and known quirks

* **One global orientation per field.** The distribution assumes a single dominant ripple family; crossed/mixed textures produce a multi-peak distribution whose `argmax` and "FWHM" are not physically meaningful.
* **No physical period band.** Unlike `semtexture`/`surfmetrics` (which can restrict the FFT search to e.g. `0.5λ–1.5λ`), this module always takes the strongest spot in the whole spectrum. Low-frequency illumination gradients and scan artefacts can outrank the true LIPSS peak — this is exactly the documented failure of the older DLOA pipeline (450–500 nm reported instead of the true ~385 nm on 3 k images; see the `semtexture` module docstring, "v4 defect"). Prefer `semtexture` for quantitative Λ on 3 k images.
* **`min_radius` bounds the period from above** (Λ > w·p/45 is unmeasurable) — larger periods need a larger image or a smaller `min_radius`; the constraint is easy to miss because it is expressed in FFT pixels.
* **Spacing assumes a square image with equal pixel size in x and y**, and uses the image width `w`; non-square scans or anisotropic pixels bias the value. The Nyquist conversion uses `pixel_size_um` only.
* **FWHM is a width of the half-maximum region, not a fitted peak width.** If secondary peaks exceed 50 %, `θ_last − θ_first` spans across them and overestimates the spread; the histogram resolution is 1°.
* **Angles are modulo 180°.** `theta_fft_deg` is the direction of periodicity (gradient normal); `lipss_angle_deg = θ_fft + 90°` is the ridge/stripe direction. The distinction matters when comparing with AFM profile directions.
* **Strict local maxima** (`>` on all 8 neighbours) miss flat-topped/duplicated FFT peaks; the top-20 cap may drop weak but genuine spots.
* **Crop heuristic** removes only the bottom dark band and only when the last row is darker than 30; a dark sample region can be partially cropped, while light footers survive.
* **No QC metric** is attached to the fit (no peak prominence, no agreement check, no second method); single images returning `None` are silently absent from the CSV.

### QC and validation

* The per-image orientation-distribution PNG is the primary QC: a sharp single peak indicates a well-ordered LIPSS field, a broad/multi-peak curve indicates a mixed texture or an artefact.
* Historical validation: the module was ported from a validated spot-DLOA script (6 samples, spacing 449–482 nm). Cross-checks against AFM (`surfmetrics`) and the autocorrelation pipeline (`semtexture`) later showed the restrictions above; the project now uses `semtexture` for quantitative period/orientation consistency and keeps DLOA as a fast whole-field orientation view.
* Verified example (commit `0e0508e`, Python 3.11/NumPy 2.4/SciPy 1.17): the bundled 512 × 512 test image with 45°-periodic fringes gives `theta_fft_deg = 45.25°`, `lipss_angle_deg = 135.25°`, `fwhm_2dtheta_deg = 4.97°`, `spacing_nm = 176.78 nm`. Independent FFT check: the spectral peak sits at offset (−64, −64) px → 5.657 px period → 176.8 nm at 31.25 nm/px, i.e. the spacing formula and angle convention are reproduced exactly.

### References

* Russ JC, Neal FB. *The Image Processing Handbook.* 7th ed. CRC Press; 2016. (Fourier-domain texture/orientation analysis, windowing and spectral peak interpretation)
* Gonzalez RC, Woods RE. *Digital Image Processing.* 4th ed. Pearson; 2018. (2-D FFT, Hann window, spectral leakage)
* Bonse J, Höhm S, Kirner SV, Rosenfeld A, Krüger J. Laser-induced periodic surface structures — a scientific evergreen. *IEEE J Sel Top Quantum Electron.* 2017;23(3):9000615. (LIPSS formation and expected periods vs laser wavelength; context for interpreting the measured Λ)
* Goldstein JI, Newbury DE, Michael JR, Ritchie NWM, Scott JHJ, Joy DC. *Scanning Electron Microscopy and X-ray Microanalysis.* 4th ed. Springer; 2018. (SEM image formation, scale calibration and footers)
* The module docstring states it was integrated from the project's validated "sem-fft-analysis" spot-DLOA script (6 samples, 449–482 nm spacing).

## 中文

### 目的与科学背景

`lipss_dloa` 从掠入射 SEM 显微图测量激光诱导周期表面结构（LIPSS）的周期 `Λ` 与取向。它是本项目中的 **DLOA**（"衍射图样 / FFT 衍射斑取向分析"）：不逐个阈值化条纹，而是对整幅图做二维傅里叶变换、检测衍射斑，再由斑点的角度分布得到主条纹取向及其展宽。典型用途：对激光织构不锈钢样片（515 nm 波长系列）做快速整场表征，再进入基于 AFM 的剖面分析（见 [`surfmetrics`](surfmetrics.md)）与多样片一致性分析（见 [`semtexture`](semtexture.md)）。

本模块是已验证的 "sem-fft-analysis" spot-DLOA 脚本（6 个样品，间距 449–482 nm）的直接移植；其已知弱点促成了后来 `semtexture` 中基于自相关的流程。

### 输入与数据格式

| 输入 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `folder` / `--folder` | str，必填 | — | SEM 图像文件夹（**不递归**，只分析该文件夹直接包含的文件） |
| `pixel_size_um` | float | `1/32 µm` = 31.25 nm/px | 像素尺寸；CLI 以 `--pixel-per-um`（默认 32）暴露，GUI 为“每微米像素数” |
| `output_dir` / `--output` | str | `output` | 输出目录 |

* 接受扩展名：`.bmp`、`.png`、`.jpg`、`.jpeg`、`.tif`、`.tiff`；图像经 `cv2.imdecode(np.fromfile(path))` 读为 8 位灰度（支持中文/Unicode 路径）。
* 文件名（小写）含 `_fft`、`_annotated`、`_spectrum` 或 `result_` 的文件会被跳过（避免重复分析旧输出）。
* 图像按普通强度场处理；没有比例尺自动识别，必须提供像素尺寸。
* 自带测试图：`data/examples/sem_test/lipss_test_45deg.bmp`（512 × 512，合成斜条纹，周期 5.657 px，在 31.25 nm/px 下为 176.8 nm）。

### 输出

| 输出 | 内容 |
|---|---|
| `output/LIPSS_orientation_angles.csv` | 每张成功分析的图一行：`file`、`theta_fft_deg`、`lipss_angle_deg`、`fwhm_2dtheta_deg`、`spacing_nm` |
| `output/dloa_<file>.png` | 取向分布曲线（品红）并标出检测到的 `theta_fft`（红虚线） |
| 返回 dict | `{"results": [逐行 dict], "csv": path}`——无效图像被静默跳过（`None`），不出现在结果中 |

### 端到端流程

1. **读入**灰度图。
2. **裁掉底部暗带**（SEM 页脚/比例尺条）：从最后一行向上扫描行均值，只要行均值 `< 30`（8 位强度）就裁掉，遇到第一行亮行停止；若最后一行本身是亮的则不裁。
3. **剔除退化图**：空图或 `min(shape) < 200` px → 返回 `None`。
4. **加窗对数功率谱**：乘以可分离 Hann 窗 `W(i,j) = hann(h)_i · hann(w)_j`；算 `F = fftshift(fft2(img · W))`；再算 `L = ln(1 + gaussian(|F|², σ = 1.5))`。
5. **检测衍射斑**：在 `L` 中找严格 8 邻域局部极大，排除半径 `exclude_radius = 40` px 的中心盘；按 `L` 降序取 `n_top = 20` 个最强点；只保留半径 `r ≥ min_radius = 45` px 的点；记录 `(α mod 180°, r, L)`。
6. **取向分布**：把斑点角度以强度为权重统计到 `[0, 180)°` 的 181 个 bin；高斯平滑（`σ = 2` bin）；减去最小值并把最大值归一为 1。
7. **报告**：`theta_fft_deg` = 分布最大值所在 bin 中心；`lipss_angle_deg = (theta_fft + 90) mod 180`（按约定为脊/条纹方向）；`fwhm_2dtheta_deg` = （平滑后）分布 `≥ 峰值 50 %` 区域的宽度；`spacing_nm` 由最强的保留斑点计算。
8. **作图**（逐图）：取向分布、`θ_fft` 线、轴标签 `Orientation in Degree` / `Distribution of Orientation (a.u.)`。

### 算法与公式

```
p            像素尺寸（µm），默认 1/32
f_nyq        = 1 / (2p)                      cycles/µm（Nyquist；31.25 nm/px 时为 16 cycles/µm）
L(u,v)       = ln(1 + G_σ=1.5( |FFT2(img · W)|² ))
spot         L 的严格 8 邻域局部极大，且 r ≥ 40 px（排除中心盘）
α            = atan2(dy, dx) mod 180°       （dy, dx = 斑点相对 FFT 中心的偏移）
D(θ)         = 归一化( G_σ=2( hist(α; 权重 = L_spot) ) − min )
θ_fft        = argmax_θ D(θ)
Λ_ridge      = (θ_fft + 90°) mod 180°
FWHM         = θ_last − θ_first  （对 { θ : D(θ) ≥ 0.5 · max D } 取首末）
```

由最强斑点计算间距（`r` 为像素、图像宽 `w`）：

```
k [cycles/µm] = r · f_nyq / (w/2) = r / (w · p)
Λ [nm]        = 1000 / k = w · (p·1000 [nm]) / r
```

默认参数下、宽 512 px 的图：可测周期范围约 `2p … w·p/45` = 62.5 … 356 nm；1024 px 图的上限约 711 nm。（下限来自 Nyquist；上限来自 `min_radius = 45` px。）

### 参数与默认值

| 参数 | 默认值 | 含义 |
|---|---|---|
| `pixel_size_um` | `1/32` µm（31.25 nm/px） | 物理像素尺寸；按 SEM 放大倍数/比例尺设置 |
| `exclude_radius` | 40 px | 忽略的 FFT 中心盘半径（DC/低频雾） |
| `n_top` | 20 | 作为候选斑保留的最强局部极大数 |
| `min_radius` | 45 px | 斑点最小半径；同时决定可测最大周期 |
| CLI `--pixel-per-um` | 32 | 像素尺寸的倒数（每微米像素数） |
| `output_dir` | `output` | 输出目录（不存在则创建） |

`DLOAAnalyzer(pixel_size_um=..., exclude_radius=40, n_top=20, min_radius=45)` 暴露全部阈值；`run(folder, output_dir, pixel_size_um)` 是便捷入口。

### 实现说明

* 包 `labtoolbox/lipss_dloa/`：`dloa.py`（163 行）。依赖 NumPy、SciPy（`ndimage.gaussian_filter`）、OpenCV（`cv2.imdecode` 读 Unicode 路径灰度图）、pandas（`analyze_folder` 内懒加载用于 CSV）、matplotlib（Agg）。
* `DLOAAnalyzer` 方法：`_read_gray`、`_detect_black_border`、`_log_power`、`_find_spots`、`_distribution`、`_fwhm`（静态）、`analyze_image`、`analyze_folder`。
* 斑点检测是对全图的双层 Python 循环（`for i in range(2, h-2): for j in range(2, w-2)`），每图 O(N²)——大 SEM 图较慢（1–3k 图可接受）。
* `analyze_folder` 对文件列表排序，逐图分析（并出图），把行写入 `LIPSS_orientation_angles.csv`（UTF-8 带 BOM）。若没有一张有效图，`pandas.DataFrame([])` 会写出空文件。
* 命令行 `labtoolbox lipss-dloa --folder ... [--pixel-per-um 32] [--output ...]`；GUI 标签页 **🔬 LIPSS/DLOA**（默认 32 px/µm）。统一 CLI 在 `labtoolbox/cli.py` 注册 `lipss-dloa` 子命令。

### 假设、局限与已知怪癖

* **每幅图只有一个全局取向。** 分布假设单一主导条纹族；交叉/混合织构会产生多峰分布，其 `argmax` 与"FWHM"没有物理意义。
* **没有物理周期带限制。** 与 `semtexture`/`surfmetrics`（可把 FFT 搜索限制在例如 `0.5λ–1.5λ`）不同，本模块始终取全谱最强斑。低频照明梯度与扫描伪影可能压过真实 LIPSS 峰——这正是旧 DLOA 流程的已知失效（对 3k 图报告 450–500 nm 而非真实的 ~385 nm；见 `semtexture` 模块 docstring 的 "v4 defect"）。对 3k 图的定量 Λ，请优先使用 `semtexture`。
* **`min_radius` 从上方限制可测周期**（Λ > w·p/45 测不到）——更大周期需要更大图像或更小的 `min_radius`；由于约束以 FFT 像素表达，容易被忽略。
* **间距假设方形图像且 x/y 像素尺寸相同**，且只用图像宽度 `w`；非方形扫描或各向异性像素会带来偏差。Nyquist 换算只用 `pixel_size_um`。
* **FWHM 是半高区域的宽度，不是拟合峰宽。** 若次峰也超过 50 %，`θ_last − θ_first` 会跨越它们而高估展宽；直方图分辨率为 1°。
* **角度按 180° 取模。** `theta_fft_deg` 是周期性（梯度法向）方向；`lipss_angle_deg = θ_fft + 90°` 是脊/条纹方向。与 AFM 剖面方向对比时这个区别很重要。
* **严格局部极大**（8 邻域全 `>`）会漏掉平顶/重复 FFT 峰；top-20 上限也可能丢掉弱但真实的斑点。
* **裁剪启发式**只去掉底部暗带，且仅当最后一行暗于 30 时才裁；较暗的样品区域可能被部分裁掉，而较亮的页脚会保留。
* **没有 QC 指标**挂在拟合上（无峰显著性、无一致性检查、无第二方法）；返回 `None` 的图静默缺席 CSV。

### 质控与验证

* 逐图的取向分布 PNG 是主要 QC：尖锐单峰表明 LIPSS 有序；宽峰/多峰表明织构混合或有伪影。
* 历史验证：模块移植自已验证的 spot-DLOA 脚本（6 样品，间距 449–482 nm）。之后与 AFM（`surfmetrics`）及自相关流程（`semtexture`）的交叉对比暴露了上述限制；项目现在用 `semtexture` 做定量周期/取向一致性，DLOA 保留为快速整场取向视图。
* 核对示例（commit `0e0508e`，Python 3.11/NumPy 2.4/SciPy 1.17）：自带的 512 × 512 合成 45° 周期条纹图给出 `theta_fft_deg = 45.25°`、`lipss_angle_deg = 135.25°`、`fwhm_2dtheta_deg = 4.97°`、`spacing_nm = 176.78 nm`。独立 FFT 核对：谱峰位于偏移 (−64, −64) px → 周期 5.657 px → 31.25 nm/px 下 176.8 nm，即间距公式与角度约定被精确复现。

### 参考文献

* Russ JC, Neal FB. *The Image Processing Handbook.* 7th ed. CRC Press; 2016.（频域纹理/取向分析、加窗与谱峰解释）
* Gonzalez RC, Woods RE. *Digital Image Processing.* 4th ed. Pearson; 2018.（二维 FFT、Hann 窗、频谱泄漏）
* Bonse J, Höhm S, Kirner SV, Rosenfeld A, Krüger J. Laser-induced periodic surface structures — a scientific evergreen. *IEEE J Sel Top Quantum Electron.* 2017;23(3):9000615.（LIPSS 形成及周期随激光波长的预期；解释实测 Λ 的背景）
* Goldstein JI, Newbury DE, Michael JR, Ritchie NWM, Scott JHJ, Joy DC. *Scanning Electron Microscopy and X-ray Microanalysis.* 4th ed. Springer; 2018.（SEM 成像、比例尺标定与页脚）
* 模块 docstring 说明它整合自本项目已验证的 "sem-fft-analysis" spot-DLOA 脚本（6 样品，449–482 nm 间距）。
