# semtexture — SEM texture uniformity & processing consistency / SEM 织构均匀性与工艺一致性

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

`semtexture` answers the manufacturing/quality question behind laser texturing: **is the surface texture the same on every coupon, and which areas of each field are actually processed?** For a folder of SEM micrographs it returns, per field and per coupon/batch:

* the ripple period `Λ` (nm) — from the **autocorrelation of a phase-coherent mean profile**, cross-checked against the 1-D spectral peak;
* the ripple orientation `θ` (deg) — structure-tensor dominant direction with circular statistics (period 180°);
* the coherence `C` (0–1) — structure-tensor anisotropy, "how ordered" the texture is;
* the profile contrast `K` — visible ripple strength;
* the **ordered / disordered / bare area fractions** from a tile map;
* the **debris density** (bright particles per mm²);
* batch-level consistency figures: between-coupon CV of `Λ`, circular SD of `θ`, SD of `C`, area fractions, and ICC(1,1) when more than one field per coupon exists.

It is the multi-coupon consistency counterpart to [`lipss_dloa`](lipss_dloa.md) (fast whole-field orientation) and [`surfmetrics`](surfmetrics.md) (AFM profiles). Defaults are calibrated on the 515 nm coupon series (2026-11-03).

**Why autocorrelation and not the FFT maximum?** As documented in the module: on 3 k images (31.25 nm/px) the ripple fundamental is ~12 px, but the 2-D FFT power in that band is dominated by the slow illumination envelope at 80–90 px, so "take the strongest peak" returns 450–500 nm instead of the true ~385 nm (the documented v4 defect of the older DLOA pipeline). Averaging intensity samples along the ripple tangent (phase-coherent) and autocorrelating the resulting 1-D profile isolates the fundamental: on six 515 nm coupons it returns 375–395 nm, matching the AFM value 384.6 nm and the v5 ring analysis 378–396 nm.

### Conventions and inputs

* **Pixel size**: 31.25 nm/px for 3 k images (1 µm scale bar = 32 px), 7.8125 nm/px for 12 k images (1 µm = 128 px). It is read automatically from a JEOL JSM `*.txt` sidecar when present: `pixel_nm = 1000 · SM_MICRON_MARKER / SM_MICRON_BAR` (marker in µm, bar in px); if no sidecar is found, `DEFAULT_PIXEL_NM = 31.25` is assumed.
* **Orientation convention**: reported `θ` is the **gradient normal**, i.e. the direction across the ripples, modulo 180°; add 90° for the ridge direction.
* **Input**: a root folder of SEM images (recursive). Supported: `.bmp`, `.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg`. **Groups = immediate parent folder name** (images directly in the root form one group named after the root).
* `exclude` (list of substrings): any path containing one of them is skipped; `qc_report` folders are never re-ingested; the module's own annotated outputs (`*_quality.png`, `*_pair.png`, `*_marked.png`) are skipped.
* **Enhanced-copy de-duplication**: a raw `<name>.<ext>` is dropped when an enhanced `<name>_e.<ext>` exists in the same folder or one level up (the 650 nm tree keeps raws in `<sample>/1/` and enhancements in `<sample>/`, which would otherwise count every field twice).
* Parameter overrides: `pixel_nm`, `tile` (px), `step` (px, default = tile), `tile_um` (default `2.0` µm), `qc` (partial thresholds), `criteria` (batch criteria), `exclude`, `figures`.

### Outputs

Default output directory: `output/sem_texture_<YYYYMMDD>/` with `figures/` and `tiles/` sub-folders.

| File | Content |
|---|---|
| `sem_texture_metrics.csv` | One row per field: period (profile/FFT/agreement), orientation and its SD, coherence, contrast, autocorrelation strength, FFT prominence, periods per FOV, debris count/density/area, mode, tile statistics, area fractions, family angles/periods, tile-level period statistics |
| `sem_texture_tiles.csv` | One row per tile: `y0`, `x0`, coherence, theta, period, ac strength, contrast, mean intensity, valid flag, family, class, severity, excess ratio, group/file/coupon |
| `sem_texture_consistency.csv` | One row per group: field/coupon counts, period mean/SD/CV, theta mean/circular SD, coherence, contrast, ordered/bare/disordered means and extremes, debris median, per-check limits and PASS/FAIL, verdict |
| `sem_texture_checks.json` | The six batch checks (label, column, operator, limit, unit) as JSON |
| `report_sem_texture.md` | Markdown digest: batch table, criteria table with verdicts, per-image results, ICC(1,1) of the period |
| `figures/<stem>_map.png` | Per field: raw image; class map (green ordered / orange disordered / red bare / grey excluded); local period map with colour bar |
| `figures/consistency_summary.png` | Per-image period, orientation and ordered-area plots, coloured by group |

`run()` returns `{"output_dir", "metrics_csv", "tiles_csv", "consistency_csv", "markdown", "figures", "stats", "checks", "icc", "n_images", "df"}`.

### Per-image pipeline

1. **Resolve pixel size / tile size**: `px = pixel_nm or sidecar or 31.25`; `tile = round(tile_um·1000/px)` (min 32 px) unless `tile` is given; `step = step or tile` (non-overlapping by default, so painted areas equal reported fractions).
2. **Load grayscale** (PIL; RGB converted to `L`), then **crop the scale bar / instrument footer**: rows are removed from the bottom while their mean stays below `0.90 × median(image)`, up to a maximum of 30 % of the height; up to six trailing bright rows (1-px frame line) are skipped first.
3. **High-pass** `hp = img − gaussian_filter(img, σ = 20 px)` — removes the illumination envelope (> ~0.6 µm at 3 k).
4. **Structure tensor** (normalised by the 99th percentile amplitude): `gx`, `gy` from first-order Gaussian derivatives (σ = 1), `Jxx = G6(gx²)`, `Jyy = G6(gy²)`, `Jxy = G6(gx·gy)`; then
   `C = √((Jxx−Jyy)² + 4Jxy²) / (Jxx + Jyy + ε)` (0 = isotropic, 1 = perfect line),
   `θ = ½·atan2(2Jxy, Jxx−Jyy) mod 180°`.
   Field orientation `θ0` = circular mean of `θ` weighted by `C²`; field coherence `C_img` = mean `C`.
5. **Phase-coherent mean profile**: rotate the image by `θ0 − 90°` so the gradient is vertical, crop an 8 % margin, average across columns, subtract the mean, smooth with a 1.5-sample Gaussian.
6. **Period from autocorrelation**: search the normalised autocorrelation for local maxima with period in `BAND_NM = (240, 800)` nm (`pmin = max(floor(240/px), 3)`, `pmax = min(ceil(800/px), len(profile)//2)`); take the largest; parabolic interpolation gives `Λ`; `ac_strength` is the autocorrelation at the peak (set to NaN when < 0.05). Cross-check: 1-D Hann-windowed FFT peak in the same band gives `period_fft_nm` and `fft_prominence = (peak − median)/median`.
7. **Contrast**: `K = std(profile) / mean(image)`.
8. **Second pass**: if `Λ/px > 13` px, the structure-tensor window is enlarged to `tensor_sigma = max(6, 0.5·Λ_px)` and steps 4–6 are recomputed, so that `C` means the same thing at 3 k and 12 k (a fixed 6-px window sees 187 nm at 3 k but only 47 nm at 12 k and would bias `C` downward).
9. **Debris**: `hp − grey_opening(hp, 15×15)` isolates bright particles; threshold `median + 8·1.4826·MAD`; ignore a 6-px frame; label 8-connected objects and keep those with area ≥ 20 px; report count, objects per mm² and area fraction.
10. **Mode decision** (`_families`): `single` when the field profile `ac_strength ≥ SINGLE_AC_SPLIT = 0.60` (one ripple family, grating-like); otherwise `mixed`, and a second family is added at `θ0 + 90°` with the **same** lattice constant (pillar/crossed lattice).
11. **Tile map**: at each `(y0, x0)` of the non-overlapping grid: structure tensor (σ = 4), tile orientation (weighted circular mean), mean `C`, mean profile (3 % margin), tile period/`ac_strength`; a tile is `valid` when its mean intensity ≥ 0.45 × the field median (excludes the dark border/footer area).
12. **Classification** (per tile): best family by
    `score = min(d_angle/angle_tol, 9) + min(d_period_frac/period_tol, 9)`;
    effective period tolerance `tol_eff = max(period_tol, 0.9/n_per_win)` with `n_per_win = tile·px/Λ` (a window holding N periods locates the fundamental to ~0.3/N, so the band is relaxed to 3σ but never tighter than the preset).
    `ordered` iff `C ≥ coherence_ordered` **and** `d_λ ≤ tol_eff` **and** `d_angle ≤ angle_tol` **and** `ac ≥ max(ac_floor, ac_rel · median_ac_of_valid_tiles)`.
    `textured` = `C ≥ coherence_texture` → `disordered`; otherwise `bare`. Excluded tiles get class −1.
    `severity = 0` for ordered tiles, otherwise `clip((r − 1)/1.5, 0, 1)` where `r = max` of the gate ratios (measured/allowed) for period, angle, coherence and autocorrelation — a continuous "how far out of spec" score used for the annotated tint.
13. **Area fractions** from a rasterised class map (overlapping tiles: worst class wins; priority bare > disordered > excluded > ordered): `ordered_frac`, `disordered_frac`, `bare_frac` = pixel shares of valid pixels; `invalid_frac = 1 − valid/total`.
14. **Field summary**: `mode`, tile count, `periods_per_window`, `period_tol_used`, family angles/periods, tile period median, MAD-based SD, MAD fraction, IQR, tile period CV, tile `θ` SD, mean tile coherence/contrast; `period_nm` is then set to the dominant family's period with the profile estimate kept as `period_profile_nm`.

### Batch statistics and consistency criteria

Per group (i.e. per parent folder / coupon set), `_batch_stats` computes field/coupon counts, `period_mean_nm ± SD`, `period_cv_pct = 100·SD(ddof=1)/mean`, circular `θ` mean and SD, `coherence_mean/sd`, `contrast_mean`, `ordered_mean_pct/ordered_min_pct`, `bare_mean_pct/bare_max_pct`, `disordered_mean_pct`, `debris_median_per_mm2`.

Six checks (`DEFAULT_CRITERIA`, all must pass for a PASS verdict):

| # | Check | Criterion |
|---|---|---|
| 1 | period CV between coupons | `≤ cv_period_pct = 3.0 %` |
| 2 | orientation SD between coupons | `≤ theta_sd_deg = 3.0°` |
| 3 | mean coherence | `≥ coherence_mean = 0.40` |
| 4 | mean ordered area | `≥ ordered_mean_pct = 70 %` |
| 5 | worst coupon vs group mean | `ordered_min_pct ≥ ordered_mean_pct − ordered_spread_pts (20 pts)` (relative uniformity) |
| 6 | worst coupon bare area | `≤ bare_max_pct = 10 %` |

ICC(1,1) (one-way random effects, Shrout & Fleiss formulation) is computed per group from the field periods grouped by coupon, only for coupons with >1 field:

```
k       = mean number of fields per coupon
grand   = Σ(n_i · mean_i) / Σ n_i
MSB     = Σ n_i (mean_i − grand)² / (g − 1)
MSW     = Σ_i Σ_j (x_ij − mean_i)² / (Σ n_i − g)
ICC(1,1) = (MSB − MSW) / (MSB + (k − 1)·MSW)
```

### Circular statistics

Angles are handled with period 180° by doubling:

```
mean:  θ̄ = ½ · arg( Σ w_j · e^{i·2θ_j} )  mod 180°
R     = |Σ w_j e^{i·2θ_j}| / Σ w_j
SD:    σ_θ = ½ · √(−2 ln R)                [rad] → degrees
```

### Tile classification presets (`DEFAULT_QC`)

| Parameter | `single` (grating) | `mixed` (pillar lattice) | Meaning |
|---|---|---|---|
| `coherence_ordered` | 0.45 | 0.38 | minimum tile coherence for "ordered" |
| `coherence_texture` | 0.15 | 0.12 | minimum tile coherence for "texture present" (else bare) |
| `period_tol` | 0.10 | 0.20 | relative period tolerance (mixed wider: intrinsic lattice dispersion) |
| `angle_tol_deg` | 10 | 15 | orientation tolerance |
| `ac_rel` | 0.55 | 0.55 | tile `ac` must be ≥ this fraction of the field's median |
| `ac_floor` | 0.10 | 0.08 | absolute autocorrelation floor |

Other constants: `DEFAULT_PIXEL_NM = 31.25`, `BAND_NM = (240, 800)` nm, `HP_SIGMA_PX = 20`, `DEFAULT_TILE_UM = 2.0`, `SINGLE_AC_SPLIT = 0.60`, `TILE_PX = 256` (fallback tile edge), class codes `BARE=0`, `DISORDERED=1`, `ORDERED=2`.

### Annotated copies (`annotate_image` / `annotate_folder`)

`annotate_image` copies the **full** micrograph (instrument footer and scale bar preserved) and paints only the defective tiles with a translucent colour from the *severity* scale (pale yellow `rgb(1.00, 0.95, 0.66)` → deep red `rgb(0.42, 0.00, 0.04)`, alpha 0.14–0.42). It adds a dashed white outline "analysed field", a statistics box (coupon, `Λ`, `C`, ordered/disordered/bare %), a gradient legend ("marginally off-spec" → "far off-spec / no texture", "unmarked = inside the acceptance band") or a "no defective region detected" note. `annotate_folder` keeps the group sub-folder structure, writes `<stem><suffix>.png` (default suffix `_quality`) and `quality_map_summary.csv`. The CLI exposes this via `--annotate-dir`.

### Parameters and defaults

| `run()` parameter | Default | Meaning |
|---|---|---|
| `folder` / `--folder` | required | SEM image root; sub-folders = groups |
| `output_dir` / `--output` | `output/sem_texture_<date>` | Output directory |
| `pixel_nm` / `--pixel-nm` | `None` → sidecar → 31.25 | Pixel size |
| `tile` / `--tile` | `None` (→ `tile_um`) | Tile edge in px (overrides `tile_um`) |
| `tile_um` / `--tile-um` | `2.0` µm | Classification window in physical units |
| `step` | `None` (= tile) | Tile stride; non-overlapping default |
| `qc` | `None` | Partial override of the QC preset (per mode) |
| `criteria` | `None` | Partial override of the batch criteria |
| `figures` / `--no-figures` | `True` | Per-image tile maps + summary figure |
| `verbose` | `True` | Progress printing |
| `exclude` / `--exclude` | `None` | Path substrings to skip (e.g. another wavelength batch) |

CLI `labtoolbox sem-texture --folder … [--pixel-nm …] [--tile-um …] [--tile …] [--output …] [--exclude …] [--no-figures] [--annotate-dir …]`; GUI tab **🧭 织构一致性** (pixel size blank = auto, window edge µm default 2).

### Implementation notes

* Package `labtoolbox/semtexture/`: `texture.py` (1093 lines); dependencies NumPy, SciPy (`ndimage`: gaussian filters, rotate, label, grey/binary opening), pandas, matplotlib (Agg; `ListedColormap`, `BoundaryNorm`), Pillow (grayscale loading). No OpenCV, no ImageJ.
* Public API: `run`, `analyse_image`, `annotate_image`, `annotate_folder`, `_discover`, `_load_gray`, `_crop_scalebar`, `quality_rgba`, `DEFAULT_QC`, `DEFAULT_CRITERIA`, `DEFAULT_PIXEL_NM`, `BAND_NM`, `DEFAULT_TILE_UM` (exported by `__init__`).
* Per-image figure and per-group summary are drawn with `matplotlib` only; the markdown report uses Chinese headings and English parameter names.
* The package is listed in `pyproject.toml`'s `packages` (added by the integration PR), so `pip install` and the PyInstaller desktop app include it; it was already wired into the unified CLI (`sem-texture`) and the GUI tab **🧭 Texture Consistency**.
* Complexity is driven by the per-tile loop: each valid tile computes a structure tensor, a rotated profile and two period estimates; typical 3 k images with 2 µm windows (64 px) give ~15–60 tiles per field.

### Assumptions, limitations and known quirks

* **`BAND_NM = (240, 800)` nm is hard-coded** and matches the 515 nm LIPSS family (`0.5λ–1.5λ`); for other wavelengths the admissible-period band must be edited in the source — there is no CLI parameter. Demonstrated in this documentation: the bundled synthetic image (176.8 nm fringe period, below the band) is reported as `Λ ≈ 530 nm` — a reminder to check the band before trusting `Λ`.
* **Mode and thresholds are calibrated heuristics.** `SINGLE_AC_SPLIT = 0.60`, the two QC presets and the six batch criteria were tuned on the 515 nm series; other textures (pillar lattices, different magnification) may need `qc`/`criteria` overrides.
* **The classification window is physical (2 µm default) but the high-pass is 20 px**, so the removed illumination scale differs with magnification (0.625 µm at 3 k, 156 nm at 12 k).
* **Area fractions are pixel fractions of the rasterised class map**; with overlapping tiles the worst class wins per pixel. With the default non-overlapping step they equal the painted area, but `tile_frac_ordered` (count-based) can differ from `ordered_frac` (area-based) when tiles overlap.
* **`single`/`mixed` mode** is decided from the field autocorrelation strength, not from the folder name; a `mixed` field is modelled as two orthogonal families with the *same* period, which is an approximation for pillar lattices.
* **NaN propagation.** Fields where the period cannot be fitted keep NaN in `period_nm`/`theta_*` and still enter the batch statistics (`np.nan*` functions), so a group with one valid field has `period_sd = NaN` and CV/θ-SD checks `FAIL` (not enough fields). ICC returns NaN for single-field coupons.
* **Markdown digest is Chinese-only**, while the CSV/JSON outputs are language-neutral; the `verdict` is a plain `PASS`/`FAIL` string.
* **`_crop_scalebar` is a relative heuristic**: dark sample regions at the bottom of the field can be (partially) cropped; a bright footer survives.
* **Debris counting** uses bright particles relative to a 15×15 grey opening; large bright regions (contamination patches) appear as one large object and are counted as one, not by area.
* The `strength`/`prominence` values are relative to local spectral medians and are not comparable across images; use them as internal diagnostics.
* `period_agree_pct` compares profile and FFT estimates; a large disagreement is a flag but does not block the run.
* `_discover` treats any image in the root as its own group named after the root folder; mixing depths therefore mixes group labels.

### QC and validation

* Built-in batch QC: the six criteria + per-check limits and PASS/FAIL (`sem_texture_checks.json`, markdown), ICC(1,1) for replicated fields, visual class maps per field and annotated copies (`annotate_folder`) for human review.
* The annotated PNG is the intended reviewer artifact: defective areas are tinted by severity but the SEM structure remains visible, and the in-image statistics box documents `Λ`, `C` and area fractions.
* Validation history (from the module docstring): on six 515 nm coupons the profile-autocorrelation period is 375–395 nm, matching AFM 384.6 nm and the v5 ring analysis 378–396 nm — the reason this method replaced the FFT-maximum DLOA pipeline.
* Reproduced for this documentation (commit `0e0508e`, Python 3.11, NumPy 2.4/SciPy 1.17): `run()` on the single-image `data/examples/sem_test` folder produced `sem_texture_metrics.csv`, `tiles.csv`, `consistency.csv`, `checks.json` and the markdown report; the field period came out `530.4 nm` (profile) vs `673.4 nm` (FFT), `θ = 45.0°`, `C = 0.980`, ordered/disordered/bare = 0/100/0 %, 64 tiles of 64 px (2 µm), verdict `FAIL` (single field → CV/θ-SD not computable; band mismatch of the synthetic 176.8 nm texture as noted above). This illustrates both the output contract and the band limitation.

### References

* Bigün J, Granlund GH. Optimal orientation detection of linear symmetry. *Proc. First International Conference on Computer Vision (ICCV).* 1987:433–438. (structure tensor / orientation coherence)
* Fisher NI. *Statistical Analysis of Circular Data.* Cambridge University Press; 1993. (circular mean/SD with period 180°, doubling trick)
* Shrout PE, Fleiss JL. Intraclass correlations: uses in assessing rater reliability. *Psychol Bull.* 1979;86(2):420–428. doi:10.1037/0033-2909.86.2.420. (ICC(1,1) formulation)
* Bendat JS, Piersol AG. *Random Data: Analysis and Measurement Procedures.* 4th ed. Wiley; 2010. (autocorrelation-based period estimation, spectral cross-checks)
* Bonse J, Höhm S, Kirner SV, Rosenfeld A, Krüger J. Laser-induced periodic surface structures — a scientific evergreen. *IEEE J Sel Top Quantum Electron.* 2017;23(3):9000615. (LIPSS period/λ relation and expected LIPSS morphology)
* Goldstein JI, Newbury DE, Michael JR, Ritchie NWM, Scott JHJ, Joy DC. *Scanning Electron Microscopy and X-ray Microanalysis.* 4th ed. Springer; 2018. (SEM magnification/scale calibration and JSM sidecar metadata used for `pixel_nm`)
* Russ JC, Neal FB. *The Image Processing Handbook.* 7th ed. CRC Press; 2016. (texture/structure-tensor and spectral analysis background)
* ISO 25178-2:2012. *Geometrical product specifications (GPS) — Surface texture: Areal — Part 2: Terms, definitions and surface texture parameters.* ISO, Geneva. (areal-texture terminology context; the ordered/bare area fractions are project-specific, not ISO parameters)

## 中文

### 目的与科学背景

`semtexture` 回答激光织构背后的制造/质量设问：**每个样片的表面织构是否一致？每幅图里哪些区域真正被加工了？** 对一文件夹的 SEM 显微图，它逐视野、逐样片/批次给出：

* 条纹周期 `Λ`（nm）——由**相位相干平均剖面的自相关**得到，并与一维谱峰交叉核对；
* 条纹取向 `θ`（度）——结构张量主方向 + 圆统计（周期 180°）；
* 相干度 `C`（0–1）——结构张量各向异性，即织构"有多有序"；
* 剖面对比度 `K`——可见条纹强度；
* 由分块图得到的**有序 / 无序 / 空白（未加工）面积分数**；
* **缺陷（亮颗粒）密度**（每 mm²）；
* 批次级一致性指标：样片间 `Λ` 的 CV、`θ` 的圆标准差、`C` 的标准差、面积分数，以及同一测点多视野时的 ICC(1,1)。

它是 [`lipss_dloa`](lipss_dloa.md)（快速整场取向）与 [`surfmetrics`](surfmetrics.md)（AFM 剖面）的多测点一致性对应物。默认值在 515 nm 样片系列上标定（2026-11-03）。

**为什么用自相关而不是 FFT 最大值？** 如模块所述：3k 图（31.25 nm/px）上条纹基频约 12 px，但该频段的二维 FFT 功率被 80–90 px 的慢变照明包络主导，于是"取最强峰"得到 450–500 nm 而不是真实的 ~385 nm（旧 DLOA 流程已记录的 v4 缺陷）。沿条纹切向（相位相干地）平均强度、再对得到的一维剖面做自相关，可以分离出基频：在 6 个 515 nm 样片上返回 375–395 nm，与 AFM 的 384.6 nm 及 v5 环形分析 378–396 nm 吻合。

### 约定与输入

* **像素尺寸**：3k 图为 31.25 nm/px（1 µm 比例尺 = 32 px），12k 图为 7.8125 nm/px（1 µm = 128 px）。若存在 JEOL JSM `*.txt` sidecar 会自动读取：`pixel_nm = 1000 · SM_MICRON_MARKER / SM_MICRON_BAR`（marker 单位 µm，bar 单位 px）；没有 sidecar 时假定 `DEFAULT_PIXEL_NM = 31.25`。
* **取向约定**：报告的 `θ` 是**梯度法向**，即横跨条纹的方向，按 180° 取模；脊方向需 +90°。
* **输入**：SEM 图像根目录（递归）。支持 `.bmp`、`.tif`、`.tiff`、`.png`、`.jpg`、`.jpeg`。**分组 = 直接父文件夹名**（根目录下直接的图像构成以根目录命名的一组）。
* `exclude`（子串列表）：路径含任一子串即跳过；`qc_report` 文件夹永不被重新摄入；模块自己生成的标注输出（`*_quality.png`、`*_pair.png`、`*_marked.png`）会跳过。
* **增强副本去重**：若同一文件夹或上一层存在增强版 `<name>_e.<ext>`，则原始 `<name>.<ext>` 会被丢弃（650 nm 数据树把原图放 `<sample>/1/`、增强图放 `<sample>/`，否则每个视野会被数两次）。
* 可覆盖参数：`pixel_nm`、`tile`（px）、`step`（px，默认 = tile）、`tile_um`（默认 `2.0` µm）、`qc`（部分阈值）、`criteria`（批次判据）、`exclude`、`figures`。

### 输出

默认输出目录：`output/sem_texture_<YYYYMMDD>/`，含 `figures/` 与 `tiles/` 子目录。

| 文件 | 内容 |
|---|---|
| `sem_texture_metrics.csv` | 每视野一行：周期（剖面/FFT/一致性）、取向及其标准差、相干度、对比度、自相关强度、FFT 显著性、每视野周期数、缺陷计数/密度/面积、模式、分块统计、面积分数、族角度/周期、分块级周期统计 |
| `sem_texture_tiles.csv` | 每分块一行：`y0`、`x0`、相干度、theta、周期、ac 强度、对比度、平均强度、有效标志、族、类、severity、excess ratio、group/file/coupon |
| `sem_texture_consistency.csv` | 每组一行：视野/样片数、周期 mean/SD/CV、theta 均值/圆 SD、相干度、对比度、有序/空白/无序均值与极值、缺陷中位数、各判据限值与 PASS/FAIL、总 verdict |
| `sem_texture_checks.json` | 六个批次判据（标签、列、运算符、限值、单位）的 JSON |
| `report_sem_texture.md` | Markdown 摘要：批次表、带判定的判据表、逐图结果、周期的 ICC(1,1) |
| `figures/<stem>_map.png` | 每视野：原图；类别图（绿=有序 / 橙=无序 / 红=空白 / 灰=排除）；局域周期图带色标 |
| `figures/consistency_summary.png` | 逐图周期、取向与有序面积图，按组着色 |

`run()` 返回 `{"output_dir", "metrics_csv", "tiles_csv", "consistency_csv", "markdown", "figures", "stats", "checks", "icc", "n_images", "df"}`。

### 单图流程

1. **确定像素/分块尺寸**：`px = pixel_nm or sidecar or 31.25`；未给 `tile` 时 `tile = round(tile_um·1000/px)`（最小 32 px）；`step = step or tile`（默认为不重叠，因此涂色面积等于报告的分数）。
2. **读入灰度**（PIL；RGB 转 `L`），再**裁掉比例尺/仪器页脚**：从底部开始，只要行均值低于 `0.90 × 图像中位数` 就删行，最多删 30 % 高度；此前最多跳过 6 行尾部亮行（1 px 边框线）。
3. **高通** `hp = img − gaussian_filter(img, σ = 20 px)`——去掉照明包络（3k 图上 > ~0.6 µm）。
4. **结构张量**（按 99 百分位幅度归一化）：一阶高斯导数（σ = 1）得 `gx`、`gy`；`Jxx = G6(gx²)`、`Jyy = G6(gy²)`、`Jxy = G6(gx·gy)`；然后
   `C = √((Jxx−Jyy)² + 4Jxy²) / (Jxx + Jyy + ε)`（0 = 各向同性，1 = 完美线状），
   `θ = ½·atan2(2Jxy, Jxx−Jyy) mod 180°`。
   视野取向 `θ0` = 以 `C²` 加权的 `θ` 圆均值；视野相干度 `C_img` = `C` 的均值。
5. **相位相干平均剖面**：把图像旋转 `θ0 − 90°` 使梯度竖直，裁掉 8 % 边距，沿列平均，减均值，用 1.5 样本高斯平滑。
6. **自相关求周期**：在归一化自相关中找周期落在 `BAND_NM = (240, 800)` nm 内的局部极大（`pmin = max(floor(240/px), 3)`，`pmax = min(ceil(800/px), len(prof)//2)`）；取最大者；抛物线插值得 `Λ`；峰值处的自相关值为 `ac_strength`（< 0.05 时置 NaN）。交叉核对：同一频段的一维 Hann 窗 FFT 峰给出 `period_fft_nm` 与 `fft_prominence = (peak − median)/median`。
7. **对比度**：`K = std(剖面) / mean(图像)`。
8. **第二遍**：若 `Λ/px > 13` px，把结构张量窗放大到 `tensor_sigma = max(6, 0.5·Λ_px)` 并重算 4–6 步，使 3k 与 12k 下 `C` 含义一致（固定 6 px 窗在 3k 看 187 nm、在 12k 只看 47 nm，会把 `C` 系统性压低）。
9. **缺陷**：`hp − grey_opening(hp, 15×15)` 分离亮颗粒；阈值 `median + 8·1.4826·MAD`；忽略 6 px 边框；8 连通标记，保留面积 ≥ 20 px 的对象；报告计数、每 mm² 个数与面积分数。
10. **模式判定**（`_families`）：视野剖面 `ac_strength ≥ SINGLE_AC_SPLIT = 0.60` 时为 `single`（单一条纹族，光栅型）；否则为 `mixed`，并增加一个位于 `θ0 + 90°`、晶格常数**相同**的第二族（柱阵列/交叉晶格）。
11. **分块图**：在非重叠网格的每个 `(y0, x0)`：结构张量（σ = 4）、分块取向（加权圆均值）、平均 `C`、平均剖面（3 % 边距）、分块周期/`ac_strength`；分块平均强度 ≥ 0.45 × 视野中位数时才算 `valid`（排除暗边/页脚）。
12. **分类**（逐分块）：按
    `score = min(d_angle/angle_tol, 9) + min(d_period_frac/period_tol, 9)`
    选最佳族；有效周期容差 `tol_eff = max(period_tol, 0.9/n_per_win)`，其中 `n_per_win = tile·px/Λ`（含 N 个周期的窗对基频的定位精度约 0.3/N，故带宽容到 3σ，但不比预设更紧）。
    `ordered` 需同时满足 `C ≥ coherence_ordered`、`d_λ ≤ tol_eff`、`d_angle ≤ angle_tol`、`ac ≥ max(ac_floor, ac_rel · 有效分块 ac 中位数)`。
    `textured = C ≥ coherence_texture` → `disordered`；否则 `bare`。排除分块类别为 −1。
    `severity = 0`（有序分块），否则 `clip((r − 1)/1.5, 0, 1)`，其中 `r` 是周期、角度、相干度、自相关各门限比值（实测/允许）的最大值——用于标注图的连续"偏离规范程度"分数。
13. **面积分数**：由栅格化类别图统计（重叠分块按最差类别优先；优先级 空白 > 无序 > 排除 > 有序）：`ordered_frac`、`disordered_frac`、`bare_frac` 为有效像素中的占比；`invalid_frac = 1 − 有效/总数`。
14. **视野汇总**：`mode`、分块数、`periods_per_window`、`period_tol_used`、各族角度/周期、分块周期中位数、基于 MAD 的 SD、MAD 相对值、IQR、分块周期 CV、分块 `θ` 标准差、分块相干度/对比度均值；随后 `period_nm` 被替换为主导族的周期，剖面估计保留在 `period_profile_nm`。

### 批次统计与一致性判据

每组（即每个父文件夹/样片集）由 `_batch_stats` 计算：视野/样片数、`period_mean_nm ± SD`、`period_cv_pct = 100·SD(ddof=1)/mean`、`θ` 的圆均值与圆标准差、`coherence_mean/sd`、`contrast_mean`、`ordered_mean_pct/ordered_min_pct`、`bare_mean_pct/bare_max_pct`、`disordered_mean_pct`、`debris_median_per_mm2`。

六项判据（`DEFAULT_CRITERIA`，全部通过才给 PASS）：

| # | 判据 | 阈值 |
|---|---|---|
| 1 | 样片间周期 CV | `≤ cv_period_pct = 3.0 %` |
| 2 | 样片间取向 SD | `≤ theta_sd_deg = 3.0°` |
| 3 | 平均相干度 | `≥ coherence_mean = 0.40` |
| 4 | 平均有序面积 | `≥ ordered_mean_pct = 70 %` |
| 5 | 最差样片 vs 组均值 | `ordered_min_pct ≥ ordered_mean_pct − ordered_spread_pts (20 pt)`（相对均匀性） |
| 6 | 最差样片空白面积 | `≤ bare_max_pct = 10 %` |

ICC(1,1)（单因素随机效应，Shrout & Fleiss 形式）按组、把各测点的视野周期按样片分组计算，只对视野数 > 1 的样片有效：

```
k       = 每样片平均视野数
grand   = Σ(n_i · mean_i) / Σ n_i
MSB     = Σ n_i (mean_i − grand)² / (g − 1)
MSW     = Σ_i Σ_j (x_ij − mean_i)² / (Σ n_i − g)
ICC(1,1) = (MSB − MSW) / (MSB + (k − 1)·MSW)
```

### 圆统计

角度按 180° 周期处理，用倍角法：

```
均值:  θ̄ = ½ · arg( Σ w_j · e^{i·2θ_j} )  mod 180°
R     = |Σ w_j e^{i·2θ_j}| / Σ w_j
标准差: σ_θ = ½ · √(−2 ln R)                [rad] → 度
```

### 分块分类预设（`DEFAULT_QC`）

| 参数 | `single`（光栅） | `mixed`（柱阵列） | 含义 |
|---|---|---|---|
| `coherence_ordered` | 0.45 | 0.38 | 判"有序"的最小分块相干度 |
| `coherence_texture` | 0.15 | 0.12 | 判"有织构"的最小相干度（否则为空白） |
| `period_tol` | 0.10 | 0.20 | 相对周期容差（mixed 更宽：晶格固有间距弥散） |
| `angle_tol_deg` | 10 | 15 | 取向容差 |
| `ac_rel` | 0.55 | 0.55 | 分块 `ac` 须 ≥ 视野中位数的该比例 |
| `ac_floor` | 0.10 | 0.08 | 自相关绝对下限 |

其他常数：`DEFAULT_PIXEL_NM = 31.25`、`BAND_NM = (240, 800)` nm、`HP_SIGMA_PX = 20`、`DEFAULT_TILE_UM = 2.0`、`SINGLE_AC_SPLIT = 0.60`、`TILE_PX = 256`（回退分块边长）、类别码 `BARE=0`、`DISORDERED=1`、`ORDERED=2`。

### 标注副本（`annotate_image` / `annotate_folder`）

`annotate_image` 复制**完整**显微图（保留仪器页脚和比例尺），只给缺陷分块涂半透明色，颜色取自 *severity* 色阶（浅黄 `rgb(1.00, 0.95, 0.66)` → 深红 `rgb(0.42, 0.00, 0.04)`，alpha 0.14–0.42）。还会加一条虚线白框标出"分析视场"、一个统计框（样片、`Λ`、`C`、有序/无序/空白 %）、一个渐变图例（"marginally off-spec" → "far off-spec / no texture"、"unmarked = inside the acceptance band"），或写着"no defective region detected"。`annotate_folder` 保留分组子目录结构，写 `<stem><suffix>.png`（默认 suffix `_quality`）与 `quality_map_summary.csv`。CLI 通过 `--annotate-dir` 暴露此功能。

### 参数与默认值

| `run()` 参数 | 默认值 | 含义 |
|---|---|---|
| `folder` / `--folder` | 必填 | SEM 图像根目录；子文件夹 = 分组 |
| `output_dir` / `--output` | `output/sem_texture_<日期>` | 输出目录 |
| `pixel_nm` / `--pixel-nm` | `None` → sidecar → 31.25 | 像素尺寸 |
| `tile` / `--tile` | `None`（→ `tile_um`） | 分块边长（px，覆盖 `tile_um`） |
| `tile_um` / `--tile-um` | `2.0` µm | 物理判定窗边长 |
| `step` | `None`（= tile） | 分块步长；默认不重叠 |
| `qc` | `None` | QC 预设的部分覆盖（按模式生效） |
| `criteria` | `None` | 批次判据的部分覆盖 |
| `figures` / `--no-figures` | `True` | 逐图分块图 + 汇总图 |
| `verbose` | `True` | 进度打印 |
| `exclude` / `--exclude` | `None` | 要跳过的路径子串（如另一波长批次） |

命令行 `labtoolbox sem-texture --folder … [--pixel-nm …] [--tile-um …] [--tile …] [--output …] [--exclude …] [--no-figures] [--annotate-dir …]`；GUI 标签页 **🧭 织构一致性**（像素尺寸留空 = 自动，判定窗边长 µm 默认 2）。

### 实现说明

* 包 `labtoolbox/semtexture/`：`texture.py`（1093 行）；依赖 NumPy、SciPy（`ndimage`：高斯滤波、rotate、label、grey/binary opening）、pandas、matplotlib（Agg；`ListedColormap`、`BoundaryNorm`）、Pillow（灰度读取）。不用 OpenCV，不用 ImageJ。
* 公开 API：`run`、`analyse_image`、`annotate_image`、`annotate_folder`、`_discover`、`_load_gray`、`_crop_scalebar`、`quality_rgba`、`DEFAULT_QC`、`DEFAULT_CRITERIA`、`DEFAULT_PIXEL_NM`、`BAND_NM`、`DEFAULT_TILE_UM`（由 `__init__` 导出）。
* 逐图图与分组汇总图只用 `matplotlib`；markdown 报告用中文标题、英文参数名。
* 该包已列入 `pyproject.toml` 的 `packages`（集成 PR 加入），因此 `pip install` 与 PyInstaller 桌面应用都会包含它；它此前已接入统一 CLI（`sem-texture`）与 GUI 标签页 **🧭 织构一致性**。
* 复杂度由逐分块循环决定：每个有效分块都算一次结构张量、一个旋转剖面和两次周期估计；典型 3k 图 + 2 µm 窗（64 px）每视野约 15–60 块。

### 假设、局限与已知怪癖

* **`BAND_NM = (240, 800)` nm 是硬编码的**，对应 515 nm LIPSS 族（`0.5λ–1.5λ`）；其他波长必须在源码里改这个允许周期带——没有 CLI 参数。本文档已演示：自带的合成图（条纹周期 176.8 nm，低于该带）被报成 `Λ ≈ 530 nm`——提醒使用前先核对频带。
* **模式与阈值是标定出来的启发式。** `SINGLE_AC_SPLIT = 0.60`、两套 QC 预设与六项批次判据都在 515 nm 系列上调过；其他织构（柱阵列、不同放大倍数）可能需要覆盖 `qc`/`criteria`。
* **判定窗是物理尺寸（默认 2 µm），但高通是 20 px**，因此被去掉的照明尺度随放大倍数变化（3k 下 0.625 µm，12k 下 156 nm）。
* **面积分数是栅格类别图的像素占比**；分块重叠时每个像素取最差类别。默认不重叠步长下等于涂色面积，但分块重叠时计数型 `tile_frac_ordered` 会与面积型 `ordered_frac` 不同。
* **`single`/`mixed` 模式**由视野自相关强度决定，不看文件夹名；`mixed` 被建模为两个正交且**同周期**的族，这对柱阵列是近似。
* **NaN 传播。** 周期拟合失败的视野在 `period_nm`/`theta_*` 上保留 NaN，仍进入批次统计（`np.nan*` 系列函数），因此只有一个有效视野的组会出现 `period_sd = NaN` 且 CV/θ-SD 判据 `FAIL`（视野不足）。单视野样片的 ICC 返回 NaN。
* **Markdown 摘要只有中文**，而 CSV/JSON 输出与语言无关；`verdict` 是纯 `PASS`/`FAIL` 字符串。
* **`_crop_scalebar` 是相对启发式**：视野底部的暗样品区域可能被（部分）裁掉；较亮的页脚会保留。
* **缺陷计数**用相对 15×15 灰度开运算的亮颗粒；大面积亮区（污染斑）作为一个大对象只计 1 个，而不是按面积计。
* `strength`/`prominence` 是相对局部谱中位数的量，不同图像间不可比；只作内部诊断。
* `period_agree_pct` 对比剖面与 FFT 估计；差异大是警示信号，但不会阻止运行。
* `_discover` 把根目录下任何深度的图像都归到其直接父文件夹名；混合层级会造成分组标签混合。

### 质控与验证

* 内建批次 QC：六项判据 + 每项限值与 PASS/FAIL（`sem_texture_checks.json`、markdown）、重复视野的 ICC(1,1)、逐视野类别图与供人工复核的标注副本（`annotate_folder`）。
* 标注 PNG 是给审稿人的目标产物：缺陷区域按 severity 着色但仍能看清 SEM 结构，图内统计框记录 `Λ`、`C` 与面积分数。
* 验证历史（模块 docstring）：6 个 515 nm 样片上剖面自相关周期为 375–395 nm，与 AFM 384.6 nm、v5 环形分析 378–396 nm 吻合——这是该方法取代 FFT 最大值 DLOA 流程的原因。
* 本文档复现（commit `0e0508e`，Python 3.11、NumPy 2.4/SciPy 1.17）：对单图目录 `data/examples/sem_test` 运行 `run()`，生成 `sem_texture_metrics.csv`、`tiles.csv`、`consistency.csv`、`checks.json` 与 markdown 报告；视野周期为 `530.4 nm`（剖面）对 `673.4 nm`（FFT），`θ = 45.0°`，`C = 0.980`，有序/无序/空白 = 0/100/0 %，64 px（2 µm）分块共 64 个，verdict 为 `FAIL`（单视野 → CV/θ-SD 不可计算；合成 176.8 nm 织构的频带失配如上所述）。该示例同时展示了输出契约与频带局限。

### 参考文献

* Bigün J, Granlund GH. Optimal orientation detection of linear symmetry. *Proc. First International Conference on Computer Vision (ICCV).* 1987:433–438.（结构张量 / 取向相干度）
* Fisher NI. *Statistical Analysis of Circular Data.* Cambridge University Press; 1993.（180° 周期圆均值/圆标准差、倍角法）
* Shrout PE, Fleiss JL. Intraclass correlations: uses in assessing rater reliability. *Psychol Bull.* 1979;86(2):420–428. doi:10.1037/0033-2909.86.2.420.（ICC(1,1) 形式）
* Bendat JS, Piersol AG. *Random Data: Analysis and Measurement Procedures.* 4th ed. Wiley; 2010.（基于自相关的周期估计与谱交叉核对）
* Bonse J, Höhm S, Kirner SV, Rosenfeld A, Krüger J. Laser-induced periodic surface structures — a scientific evergreen. *IEEE J Sel Top Quantum Electron.* 2017;23(3):9000615.（LIPSS 周期与 λ 的关系及预期形貌）
* Goldstein JI, Newbury DE, Michael JR, Ritchie NWM, Scott JHJ, Joy DC. *Scanning Electron Microscopy and X-ray Microanalysis.* 4th ed. Springer; 2018.（SEM 放大倍数/比例尺标定，以及用于 `pixel_nm` 的 JSM sidecar 元数据）
* Russ JC, Neal FB. *The Image Processing Handbook.* 7th ed. CRC Press; 2016.（纹理/结构张量与谱分析背景）
* ISO 25178-2:2012. *Geometrical product specifications (GPS) — Surface texture: Areal — Part 2: Terms, definitions and surface texture parameters.* ISO, Geneva.（面积纹理术语背景；有序/空白面积分数是项目自定义指标，不是 ISO 参数）
