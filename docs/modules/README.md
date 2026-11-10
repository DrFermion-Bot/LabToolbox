# LabToolbox module documentation / LabToolbox 模块实现文档索引

> [← Documentation home](../README.md) · [English](#english) · [中文](#中文)

## English

### About these documents

These are implementation-level module docs for **LabToolbox** (`labtoolbox`, v0.1.14), a Python toolkit for biomedical surface/ microbiology analysis (F-DLC antibacterial surfaces, laser-induced periodic surface structures, bacterial adhesion, LIVE/DEAD viability). They document the source code **as it stands at commit `0e0508e`** (branch `agent/bilingual-module-docs`, base `master`). Each module page is complete in both languages — the `## English` and `## 中文` sections mirror each other, they are not summaries of one another.

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
* **Defaults** are the literal values in the code at `0e0508e` and are repeated in each module's parameter table.
* **Quirks are documented rather than smoothed over.** Where the code has a behaviour that a reader would not expect from the theory (e.g. the swapped `γ⁺/γ⁻` rows in `xdlvo`, the fixed 240–800 nm SEM period band in `semtexture`, the inert `area_um2` argument in the cell counter), the module page says so explicitly.
* **Reference policy**: only real, verifiable papers, standards and textbooks are cited; DOIs are given only where they could be confirmed, otherwise the full journal/volume/page citation is used. Standards and product manuals are cited as such. Classic methods that are *not* implemented in the code (e.g. Otsu thresholding, Wenzel/Cassie–Baxter models) are deliberately not cited, because the docs describe what the code actually does.
* **Verification status**: every page was written from the source at `0e0508e`. Where a module could be executed on the documentation machine (synthetic or bundled example data), the observed outputs are quoted in the QC/validation section. Modules that need unavailable infrastructure (Bruker `.ibw` files, a local ImageJ installation, WSL Gwyddion) are documented from source only and say so.

### Adding a module page

A new module page should keep the same section order (`Purpose → Inputs → Outputs → Pipeline → Algorithms → Parameters → Implementation → Assumptions/limitations → QC → References`) in both languages, take every parameter name/default from the code, and add its row to the index table above.

## 中文

### 关于本文档

这是 **LabToolbox**（`labtoolbox`，v0.1.14）的实现级模块文档。LabToolbox 是一个面向生物医学表面/微生物学分析的 Python 工具箱（F-DLC 抗菌表面、激光诱导周期表面结构、细菌黏附、LIVE/DEAD 存活率）。文档描述的是 **commit `0e0508e` 时的源码**（分支 `agent/bilingual-module-docs`，基线 `master`）。每个模块页都有完整的中英双语内容——`## English` 与 `## 中文` 两节互相镜像，而不是一方对另一方的摘要。

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
* **默认值**是 `0e0508e` 代码中的字面值，并在每个模块的参数表中重复给出。
* **怪癖如实记录，不粉饰。** 对理论预期之外的行为（如 `xdlvo` 的 `γ⁺/γ⁻` 行序互换、`semtexture` 固定 240–800 nm 周期带、细胞计数里不起作用的 `area_um2` 参数），模块页会明确指出。
* **参考文献政策**：只引用真实、可核实的论文、标准与教科书；DOI 只在能确认时给出，否则用完整期刊/卷/页码引用。标准与产品手册按标准/手册引用。代码中**未实现**的经典方法（如 Otsu 阈值、Wenzel/Cassie–Baxter 模型）刻意不引用——文档只描述代码实际做了什么。
* **验证状态**：每页都依据 `0e0508e` 源码撰写。能在文档编写机器上运行（合成或自带示例数据）的模块，其实际输出写在"质控与验证"一节。依赖不可用基础设施的模块（Bruker `.ibw` 数据、本地 ImageJ 安装、WSL Gwyddion）仅依据源码描述，并在文中说明。

### 新增模块页

新模块页应保持相同的栏目顺序（`目的 → 输入 → 输出 → 流程 → 算法 → 参数 → 实现 → 假设/局限 → 质控 → 参考文献`），中英双语齐全；参数名与默认值必须取自代码；并在上面的索引表中加一行。
