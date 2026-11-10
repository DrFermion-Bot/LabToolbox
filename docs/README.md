# LabToolbox documentation / LabToolbox 文档

> [English](#english) · [中文](#中文) · [Module index](modules/README.md)

## English

### What is documented here

This `docs/` tree contains the **implementation documentation** for LabToolbox (`labtoolbox`, v0.1.14) — a modular Python toolkit for biomedical surface and microbiology data analysis, built around F-DLC antibacterial coatings, laser-induced periodic surface structures (LIPSS) on stainless steel, bacterial adhesion theory and LIVE/DEAD viability assays.

The documentation is written against the source at **commit `0e0508e`** (branch `agent/bilingual-module-docs`). It complements, and does not replace, the project READMEs in the repository root ([README.md](../README.md) — 中文, [README_EN.md](../README_EN.md) — English), which cover installation and quick-start at the interface level.

```
docs/
├── README.md              ← this page
└── modules/
    ├── README.md          ← bilingual module index + cross-module conventions
    ├── growth_curve.md
    ├── lipss_dloa.md
    ├── semtexture.md
    ├── surfmetrics.md
    ├── contact_schematic.md
    ├── contact_angle.md
    ├── xdlvo.md
    ├── livedead.md
    └── livedead_cellcounter.md
```

Every module page contains a complete `## English` section and a complete `## 中文` section that mirror each other, so the documentation can be read in either language without loss.

### Quick navigation

* **All modules, one-line descriptions, and how they fit together** → [module index](modules/README.md)
* **Surface/roughness work (AFM/SEM)**: [surfmetrics](modules/surfmetrics.md) → [contact_schematic](modules/contact_schematic.md)
* **Laser-texture quality (SEM)**: [lipss_dloa](modules/lipss_dloa.md) → [semtexture](modules/semtexture.md)
* **Wettability and adhesion theory**: [contact_angle](modules/contact_angle.md) → [xdlvo](modules/xdlvo.md)
* **Viability / microbiology counts**: [livedead_cellcounter](modules/livedead_cellcounter.md) → [livedead](modules/livedead.md)
* **Growth curves**: [growth_curve](modules/growth_curve.md)

### Running the toolbox

```bash
pip install -e .                 # core dependencies
pip install -e ".[image]"        # + OpenCV/Pillow (legacy counting engine)
pip install "igor @ git+https://github.com/wking/igor"   # .ibw (Bruker AFM) direct read

python -m labtoolbox.gui        # bilingual tkinter GUI (one tab per module)
labtoolbox --help               # unified CLI: growth-curve, lipss-dloa, sem-texture,
                                # xdlvo, livedead, contact-angle, surfmetrics, schematic
```

Optional external engines:

* **ImageJ 1.54** (classic layout with `ij.jar` + `jre/bin/java.exe`, e.g. `E:/ImageJ/ImageJ`) for the default LIVE/DEAD counting backend; the project macro is in `scripts/imagej/`.
* **WSL Ubuntu + Gwyddion 2.67 + `/usr/local/bin/gwy_batch.py`** for `surfmetrics --backend gwyddion`.

Repository data: `examples/` holds the example tables opened by the GUI buttons; `data/examples/` holds sanitized example inputs (a growth-curve CSV, a LIVE/DEAD Excel, a synthetic SEM image). Real study data stay outside the repository.

### Caveats for this commit

Two modules in the working tree — `semtexture` and `contact_schematic` — are importable from a source checkout and wired into the CLI/GUI, but are **not listed in `pyproject.toml`'s `packages`** at `0e0508e`; install them by running from the repository (or use the later packaging fix). The LIVE/DEAD cell counter is available through the GUI and the Python API but has **no unified-CLI subcommand** at this commit. Interface-level READMEs may describe features from a later state; where anything differs, these module pages record the behaviour of `0e0508e`.

### How these pages are written

Each module page follows the same structure: purpose and scientific context; inputs/outputs and formats; end-to-end pipeline; algorithms and formulas with symbols; parameter names and defaults taken from the code; implementation notes; assumptions, limitations and known quirks; QC/validation; references. Quirks are documented as they are, including behaviours a reader might not expect from the theory. References are real papers, standards, textbooks and product manuals — DOIs only where confirmed; methods not implemented in the code are not cited.

## 中文

### 本文档的内容

`docs/` 目录包含 LabToolbox（`labtoolbox`，v0.1.14）的**实现级文档**。LabToolbox 是一个模块化的 Python 工具箱，用于生物医学表面与微生物学数据分析，涵盖 F-DLC 抗菌涂层、不锈钢激光诱导周期表面结构（LIPSS）、细菌黏附理论与 LIVE/DEAD 存活率实验。

文档针对 **commit `0e0508e`** 的源码撰写（分支 `agent/bilingual-module-docs`）。它与仓库根目录的项目 README（[README.md](../README.md) 中文、[README_EN.md](../README_EN.md) 英文，介绍安装与快速上手）互补，而不是替代它们。

```
docs/
├── README.md              ← 本页
└── modules/
    ├── README.md          ← 中英双语模块索引 + 跨模块约定
    ├── growth_curve.md
    ├── lipss_dloa.md
    ├── semtexture.md
    ├── surfmetrics.md
    ├── contact_schematic.md
    ├── contact_angle.md
    ├── xdlvo.md
    ├── livedead.md
    └── livedead_cellcounter.md
```

每个模块页都有完整的 `## English` 与 `## 中文` 两节并互相镜像，因此任选一种语言阅读都不会缺内容。

### 快速导航

* **全部模块、一句话描述、模块间关系** → [模块索引](modules/README.md)
* **表面/粗糙度（AFM/SEM）**：[surfmetrics](modules/surfmetrics.md) → [contact_schematic](modules/contact_schematic.md)
* **激光织构质量（SEM）**：[lipss_dloa](modules/lipss_dloa.md) → [semtexture](modules/semtexture.md)
* **浸润性与黏附理论**：[contact_angle](modules/contact_angle.md) → [xdlvo](modules/xdlvo.md)
* **存活率/微生物计数**：[livedead_cellcounter](modules/livedead_cellcounter.md) → [livedead](modules/livedead.md)
* **生长曲线**：[growth_curve](modules/growth_curve.md)

### 运行工具箱

```bash
pip install -e .                 # 核心依赖
pip install -e ".[image]"        # + OpenCV/Pillow（旧计数引擎）
pip install "igor @ git+https://github.com/wking/igor"   # 直读 .ibw（Bruker AFM）

python -m labtoolbox.gui        # 中英双语 tkinter GUI（每个模块一个标签页）
labtoolbox --help               # 统一 CLI：growth-curve, lipss-dloa, sem-texture,
                                # xdlvo, livedead, contact-angle, surfmetrics, schematic
```

可选外部引擎：

* **ImageJ 1.54**（经典目录，含 `ij.jar` 与 `jre/bin/java.exe`，如 `E:/ImageJ/ImageJ`）用于默认的 LIVE/DEAD 计数后端；项目宏在 `scripts/imagej/`。
* **WSL Ubuntu + Gwyddion 2.67 + `/usr/local/bin/gwy_batch.py`** 用于 `surfmetrics --backend gwyddion`。

仓库数据：`examples/` 存放 GUI 按钮打开的范例表格；`data/examples/` 存放脱敏示例输入（生长曲线 CSV、LIVE/DEAD Excel、合成 SEM 图）。真实研究数据不入库。

### 本 commit 的注意事项

工作区中的两个模块——`semtexture` 与 `contact_schematic`——在源码树中可导入且已接入 CLI/GUI，但在 `0e0508e` 时**未列入 `pyproject.toml` 的 `packages`**；请从仓库源码运行（或使用后续修复的打包版本）。LIVE/DEAD 细胞计数模块可通过 GUI 与 Python API 使用，但该 commit 下**没有统一 CLI 子命令**。接口级 README 可能描述更晚的状态；如有差异，以这些模块页记录的 `0e0508e` 行为为准。

### 这些页面怎么写

每个模块页结构一致：目的与科学背景；输入/输出与格式；端到端流程；带符号的算法与公式；取自代码的参数名与默认值；实现说明；假设、局限与已知怪癖；质控/验证；参考文献。怪癖如实记录，包括读者按理论预期不到的行为。参考文献均为真实论文、标准、教科书与产品手册——DOI 只在确认时给出；代码未实现的方法不引用。
