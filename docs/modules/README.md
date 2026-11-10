# LabToolbox module documentation / LabToolbox 模块实现文档索引

> [← Documentation home](../README.md) · [English](#english) · [中文](#中文)

## English

### About these documents

These are implementation-level module docs for **LabToolbox** (`labtoolbox`, v0.1.14), a Python toolkit for biomedical surface/ microbiology analysis (F-DLC antibacterial surfaces, laser-induced periodic surface structures, bacterial adhesion, LIVE/DEAD viability). The algorithm/formula content describes the **base source commit `0e0508e`**. The pages were merged into the release/integration branch (`46bdd8f`) and updated for its app/packaging changes: 9 GUI tabs, 9 CLI subcommands, complete pip/installer packaging, bundled ImageJ 1.54 + Temurin 11 JRE, cross-platform fonts, and the XDLVO `γ⁺/γ⁻` solver fix. Each module page is complete in both languages — the `## English` and `## 中文` sections mirror each other, they are not summaries of one another.

The docs are written for a reader who wants to *reproduce the analysis and understand the formulas without reading the code*: purpose and scientific context, input/output formats, the end-to-end pipeline, algorithms with symbols, parameter names and defaults taken from the source, implementation notes (functions/classes/libraries), assumptions and known quirks, QC/validation, and references.

### Module index

| Module | What it does (EN) | 中文 | Typical inputs → outputs |
|---|---|---|---|
| [`growth_curve`](growth_curve.md) | Fits OD600 growth curves (Gompertz/Logistic/…) and plots OD + log CFU | 拟合 OD600 生长曲线，画 OD 与 log CFU 双面板 | Excel/CSV with `time_min, od600, cfu_ml` → fit table + PNG |
| [`lipss_dloa`](lipss_dloa.md) | Whole-field LIPSS period/orientation from SEM via FFT-spot orientation analysis | SEM 图像 FFT 衍射斑取向分析：LIPSS 周期/取向 | SEM image folder → per-image angle/period CSV + distribution PNG |
| [`semtexture`](semtexture.md) | Multi-coupon SEM texture consistency: autocorrelation period, structure-tensor orientation/coherence, ordered/bare area tiles, defect density, ICC/batch criteria | SEM 织构一致性：周期/取向/相干度 + 合格区面积 + 缺陷密度 + 批量判据 | SEM image tree → metrics/tiles/consistency CSVs + class-map PNGs + markdown |
| [`surfmetrics`](surfmetrics.md) | AFM/SEM height maps → ISO 25178 Sa/Sq/Sz + Sdr, true-scale 3-D views and depth profiles | AFM/SEM 高度图 → ISO 粗糙度 + 表面积比 + 3D 图/剖面 | `.ibw`/TIFF/XYZ → metrics CSV + 3-D/profile PNGs (optional Gwyddion backend) |
| [`contact_schematic`](contact_schematic.md) | Measures LIPSS/nanopillar geometry from AFM and renders bacteria–texture contact schematics | 实测 AFM 几何 → 细菌–织构接触 3D 示意图 | `.ibw` tree → fig1/fig2/fig3 (PNG+PDF) + geometry CSV + README |
| [`contact_angle`](contact_angle.md) | OWRK surface free energy from two contact angles | 两液 OWRK 表面自由能 | two angles + liquids → SFE (LW/P components) |
| [`xdlvo`](xdlvo.md) | XDLVO bacterial adhesion: SFE → ΔG_ADH → U(h) barrier/minima; SEI on topography | XDLVO 细菌黏附预测（含 SEI 形貌扩展） | three contact angles (+ ζ, I, radius) → ΔG table + energy-curve PNG |
| [`livedead`](livedead.md) | LIVE/DEAD viability statistics + two-way ANOVA | LIVE/DEAD 存活率统计 + 双因素 ANOVA | Excel/CSV `live, dead, group, time` → summary/ANOVA CSV + bar chart |
| [`livedead_cellcounter`](livedead_cellcounter.md) | Automated LIVE/DEAD micrograph counting (repeat/time/area tree) with ImageJ or OpenCV engine | LIVE/DEAD 荧光图自动计数（ImageJ/OpenCV 引擎） | fluorescence image tree → raw/summary/ANOVA CSVs + stacked bar chart |

### Entry points (integration state)

All nine modules are reachable from both the GUI and the unified CLI; the Python API is the same `run()` entry point each page's pipeline section describes.

| Module | CLI subcommand | GUI tab |
|---|---|---|
| [`growth_curve`](growth_curve.md) | `labtoolbox growth-curve --data …` | 📈 Growth Curve |
| [`lipss_dloa`](lipss_dloa.md) | `labtoolbox lipss-dloa --folder …` | 🔬 LIPSS/DLOA |
| [`semtexture`](semtexture.md) | `labtoolbox sem-texture --folder …` | 🧭 Texture Consistency |
| [`surfmetrics`](surfmetrics.md) | `labtoolbox surfmetrics --file/--folder …` | 🏔️ Surface Morphology |
| [`contact_schematic`](contact_schematic.md) | `labtoolbox schematic --input … --out …` | 📐 Contact Schematic |
| [`contact_angle`](contact_angle.md) | `labtoolbox contact-angle --theta1 … --theta2 …` | 💧 Contact Angle |
| [`xdlvo`](xdlvo.md) | `labtoolbox xdlvo --angles '{…}'` | 🧫 XDLVO |
| [`livedead`](livedead.md) | `labtoolbox livedead --file …` | 🦠 LIVE/DEAD |
| [`livedead_cellcounter`](livedead_cellcounter.md) | `labtoolbox livedead-cellcounter FOLDER` | 🔬 LIVE/DEAD Cell Count |

### How the modules fit together

```
SEM images ──► lipss_dloa  (fast whole-field orientation)
           └─► semtexture (period/orientation consistency, ordered-area maps)
AFM .ibw   ──► surfmetrics (Sa/Sq/Sz/Sdr, 3-D + profiles) ──► contact_schematic (contact schematics)
Contact angles ──► contact_angle (OWRK) and xdlvo (vOCG + ΔG + U(h) + SEI)
LIVE/DEAD images ──► livedead_cellcounter ──► livedead (viability stats / ANOVA)
Growth curves ──► growth_curve (standalone)
```

The `surfmetrics` helper functions (`load_heightmap`, `plane_subtract`, `despike_z`, `stripe_orientation`, `surface_metrics`) are the shared AFM core also used by `contact_schematic`; `xdlvo.sei` builds on the same contact-angle/vOCG physics as `xdlvo.xdlvo`.

### Conventions used throughout the docs

* **Units**: contact angles in degrees; surface energies in mJ/m²; AFM heights/roughness in nm; FFT periods in nm; energies in the interaction plot in `kT`; ionic strength in mol/L; zeta potentials in mV unless explicitly stated otherwise (see the `sei.py` note in [`xdlvo`](xdlvo.md)).
* **Defaults** are the literal values in the code at `0e0508e` and are repeated in each module's parameter table; the numerical algorithms are unchanged by the integration PR apart from the `xdlvo` surface-energy solver fix.
* **Quirks are documented rather than smoothed over.** Where the code has a behaviour that a reader would not expect from the theory (e.g. the hard-coded 240–800 nm SEM period band in `semtexture`, the inert `area_um2` argument in the cell counter), the module page says so explicitly. Where the integration PR fixed an issue (the `xdlvo` `γ⁺/γ⁻` solver swap), the page records both the historical defect and the corrected behaviour/numbers.
* **Reference policy**: only real, verifiable papers, standards and textbooks are cited; DOIs are given only where they could be confirmed, otherwise the full journal/volume/page citation is used. Standards and product manuals are cited as such. Classic methods that are *not* implemented in the code (e.g. Otsu thresholding, Wenzel/Cassie–Baxter models) are deliberately not cited, because the docs describe what the code actually does.
* **Verification status**: every page was written from the source at `0e0508e`; pages touched by the integration PR (entry points, packaging, bundled ImageJ, XDLVO fix) were re-checked against `46bdd8f`. Where a module could be executed on the documentation machine (synthetic or bundled example data), the observed outputs are quoted in the QC/validation section. Modules that need unavailable infrastructure (Bruker `.ibw` files, a local ImageJ installation, WSL Gwyddion) are documented from source only and say so.

### Integration state (PR)

* **GUI**: 9 tabs — the ninth is **📐 Contact Schematic** (`contact_schematic`: AFM data folder, sample label, output dir).
* **CLI**: 9 subcommands — the ninth is **`livedead-cellcounter`** (`FOLDER --backend imagej|opencv --min-size --skip-repeats --qc-dir`).
* **Packaging**: `pyproject.toml` includes all nine packages (`contact_schematic` and `semtexture` were missing at `0e0508e`); release CI builds a Windows installer + portable zip and macOS Intel/Apple-Silicon DMGs. Install/release details: [**docs/INSTALL.md**](../INSTALL.md).
* **Bundled engine**: installers/DMGs embed ImageJ 1.54 + a platform-native Temurin 11 JRE and ship the counting macro read-only; source checkouts auto-discover ImageJ or accept `LABTOOLBOX_IMAGEJ_DIR`. See [`livedead_cellcounter`](livedead_cellcounter.md).
* **Fonts**: cross-platform CJK font selection (`labtoolbox.common.fonts`) for the GUI and matplotlib figures.
* **XDLVO fix**: commit `46bdd8f` corrects the vOCG formamide row so `γ⁺/γ⁻` are no longer swapped; regression test `tests/test_xdlvo_surface_energy.py`. Corrected numbers are in [`xdlvo`](xdlvo.md).

### Adding a module page

A new module page should keep the same section order (`Purpose → Inputs → Outputs → Pipeline → Algorithms → Parameters → Implementation → Assumptions/limitations → QC → References`) in both languages, take every parameter name/default from the code, and add its row to the index table above.

## 中文

### 关于本文档

这是 **LabToolbox**（`labtoolbox`，v0.1.14）的实现级模块文档。LabToolbox 是一个面向生物医学表面/微生物学分析的 Python 工具箱（F-DLC 抗菌表面、激光诱导周期表面结构、细菌黏附、LIVE/DEAD 存活率）。算法/公式内容描述的是**基线源码 commit `0e0508e`**。这些页面已合并进发布/集成分支（`46bdd8f`），并按该分支的 app/打包变化更新：9 个 GUI 标签页、9 个 CLI 子命令、完整的 pip/安装包打包、内置 ImageJ 1.54 + Temurin 11 JRE、跨平台字体，以及 XDLVO `γ⁺/γ⁻` 求解器修复。每个模块页都有完整的中英双语内容——`## English` 与 `## 中文` 两节互相镜像，而不是一方对另一方的摘要。

文档面向的读者是**希望不读代码就能复现分析流程并理解公式**的人：目的与科学背景、输入/输出格式、端到端流程、带符号的算法与公式、取自源码的参数名与默认值、实现说明（函数/类/库）、假设与已知怪癖、质控/验证，以及参考文献。

### 模块索引

| 模块 | 功能（中文） | What it does (EN) | 典型输入 → 输出 |
|---|---|---|---|
| [`growth_curve`](growth_curve.md) | 拟合 OD600 生长曲线（Gompertz/Logistic 等），画 OD 与 log CFU 双面板 | Fits OD600 growth curves and plots OD + log CFU | 含 `time_min, od600, cfu_ml` 的 Excel/CSV → 拟合表 + PNG |
| [`lipss_dloa`](lipss_dloa.md) | SEM 图像 FFT 衍射斑取向分析：LIPSS 周期/取向 | Whole-field LIPSS period/orientation from SEM (FFT spots) | SEM 图像文件夹 → 逐图角度/周期 CSV + 分布 PNG |
| [`semtexture`](semtexture.md) | SEM 织构一致性：自相关周期、结构张量取向/相干度、有序/空白面积分块、缺陷密度、ICC/批次判据 | Multi-coupon SEM texture consistency metrics | SEM 图像树 → metrics/tiles/consistency CSV + 类别图 PNG + markdown |
| [`surfmetrics`](surfmetrics.md) | AFM/SEM 高度图 → ISO 25178 Sa/Sq/Sz + Sdr、真比例 3D 图与深度剖面 | AFM/SEM height maps → ISO areal roughness + Sdr + 3-D/profiles | `.ibw`/TIFF/XYZ → 指标 CSV + 3D/剖面 PNG（可选 Gwyddion 后端） |
| [`contact_schematic`](contact_schematic.md) | 由 AFM 实测 LIPSS/纳米柱几何渲染细菌–织构接触示意图 | Measures texture geometry and renders contact schematics | `.ibw` 目录 → fig1/fig2/fig3（PNG+PDF）+ 几何 CSV + README |
| [`contact_angle`](contact_angle.md) | 两液 OWRK 表面自由能 | OWRK surface free energy from two contact angles | 两个角度 + 液体 → SFE（LW/P 分量） |
| [`xdlvo`](xdlvo.md) | XDLVO 细菌黏附：SFE → ΔG_ADH → U(h) 势垒/势阱；形貌 SEI 扩展 | XDLVO adhesion prediction incl. SEI topography | 三个接触角（+ ζ、I、半径）→ ΔG 表 + 能量曲线 PNG |
| [`livedead`](livedead.md) | LIVE/DEAD 存活率统计 + 双因素 ANOVA | LIVE/DEAD viability statistics + two-way ANOVA | Excel/CSV `live, dead, group, time` → 汇总/ANOVA CSV + 柱状图 |
| [`livedead_cellcounter`](livedead_cellcounter.md) | LIVE/DEAD 荧光图自动计数（重复/时间/区域树；ImageJ 或 OpenCV 引擎） | Automated LIVE/DEAD counting with ImageJ/OpenCV engines | 荧光图树 → 原始/汇总/ANOVA CSV + 堆叠柱状图 |

### 入口（集成状态）

九个模块都可从 GUI 与统一 CLI 使用；Python API 就是各页流程一节描述的同一个 `run()` 入口。

| 模块 | CLI 子命令 | GUI 标签页 |
|---|---|---|
| [`growth_curve`](growth_curve.md) | `labtoolbox growth-curve --data …` | 📈 生长曲线 |
| [`lipss_dloa`](lipss_dloa.md) | `labtoolbox lipss-dloa --folder …` | 🔬 LIPSS/DLOA |
| [`semtexture`](semtexture.md) | `labtoolbox sem-texture --folder …` | 🧭 织构一致性 |
| [`surfmetrics`](surfmetrics.md) | `labtoolbox surfmetrics --file/--folder …` | 🏔️ 表面形貌 |
| [`contact_schematic`](contact_schematic.md) | `labtoolbox schematic --input … --out …` | 📐 接触几何示意 |
| [`contact_angle`](contact_angle.md) | `labtoolbox contact-angle --theta1 … --theta2 …` | 💧 接触角/表面能 |
| [`xdlvo`](xdlvo.md) | `labtoolbox xdlvo --angles '{…}'` | 🧫 XDLVO |
| [`livedead`](livedead.md) | `labtoolbox livedead --file …` | 🦠 LIVE/DEAD |
| [`livedead_cellcounter`](livedead_cellcounter.md) | `labtoolbox livedead-cellcounter FOLDER` | 🔬 LIVE/DEAD 细胞计数 |

### 模块之间的关系

```
SEM 图像 ──► lipss_dloa  （快速整场取向）
         └─► semtexture （周期/取向一致性、合格区图）
AFM .ibw ──► surfmetrics（Sa/Sq/Sz/Sdr、3D + 剖面）──► contact_schematic（接触示意图）
接触角   ──► contact_angle（OWRK）与 xdlvo（vOCG + ΔG + U(h) + SEI）
LIVE/DEAD 图像 ──► livedead_cellcounter ──► livedead（存活率统计 / ANOVA）
生长曲线 ──► growth_curve（独立）
```

`surfmetrics` 的助手函数（`load_heightmap`、`plane_subtract`、`despike_z`、`stripe_orientation`、`surface_metrics`）是共享的 AFM 内核，`contact_schematic` 也使用它；`xdlvo.sei` 与 `xdlvo.xdlvo` 共用同一套接触角/vOCG 物理。

### 文档中的通用约定

* **单位**：接触角为度；表面能 mJ/m²；AFM 高度/粗糙度 nm；FFT 周期 nm；相互作用能曲线 `kT`；离子强度 mol/L；zeta 电位除非特别说明为 mV（见 [`xdlvo`](xdlvo.md) 中 `sei.py` 的说明）。
* **默认值**是 `0e0508e` 代码中的字面值，并在每个模块的参数表中重复给出；除 `xdlvo` 表面能求解器修复外，集成 PR 未改变数值算法。
* **怪癖如实记录，不粉饰。** 对理论预期之外的行为（如 `semtexture` 固定 240–800 nm 周期带、细胞计数里不起作用的 `area_um2` 参数），模块页会明确指出。集成 PR 修复过的问题（`xdlvo` 的 `γ⁺/γ⁻` 求解器互换），页面会同时记录历史缺陷与修正后的行为/数值。
* **参考文献政策**：只引用真实、可核实的论文、标准与教科书；DOI 只在能确认时给出，否则用完整期刊/卷/页码引用。标准与产品手册按标准/手册引用。代码中**未实现**的经典方法（如 Otsu 阈值、Wenzel/Cassie–Baxter 模型）刻意不引用——文档只描述代码实际做了什么。
* **验证状态**：每页都依据 `0e0508e` 源码撰写；受集成 PR 影响的页面（入口、打包、内置 ImageJ、XDLVO 修复）已按 `46bdd8f` 复核。能在文档编写机器上运行（合成或自带示例数据）的模块，其实际输出写在"质控与验证"一节。依赖不可用基础设施的模块（Bruker `.ibw` 数据、本地 ImageJ 安装、WSL Gwyddion）仅依据源码描述，并在文中说明。

### 集成状态（PR）

* **GUI**：9 个标签页——第 9 个是 **📐 接触几何示意**（`contact_schematic`：AFM 数据目录、样品标签、输出目录）。
* **CLI**：9 个子命令——第 9 个是 **`livedead-cellcounter`**（`FOLDER --backend imagej|opencv --min-size --skip-repeats --qc-dir`）。
* **打包**：`pyproject.toml` 包含全部九个包（`contact_schematic` 与 `semtexture` 在 `0e0508e` 时缺失）；发布 CI 构建 Windows 安装包 + 便携 zip 与 macOS Intel/Apple Silicon DMG。安装/发布细节见 [**docs/INSTALL.md**](../INSTALL.md)。
* **内置引擎**：安装包/DMG 内置 ImageJ 1.54 + 平台原生 Temurin 11 JRE，计数宏随包只读分发；源码运行自动探测 ImageJ，或用 `LABTOOLBOX_IMAGEJ_DIR` 指定。见 [`livedead_cellcounter`](livedead_cellcounter.md)。
* **字体**：GUI 与 matplotlib 图使用跨平台中文字体选择（`labtoolbox.common.fonts`）。
* **XDLVO 修复**：commit `46bdd8f` 修正 vOCG 甲酰胺行，`γ⁺/γ⁻` 不再互换；回归测试 `tests/test_xdlvo_surface_energy.py`。修正后的数值见 [`xdlvo`](xdlvo.md)。

### 新增模块页

新模块页应保持相同的栏目顺序（`目的 → 输入 → 输出 → 流程 → 算法 → 参数 → 实现 → 假设/局限 → 质控 → 参考文献`），中英双语齐全；参数名与默认值必须取自代码；并在上面的索引表中加一行。
