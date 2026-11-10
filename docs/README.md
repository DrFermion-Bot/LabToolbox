# LabToolbox documentation / LabToolbox 文档

> [English](#english) · [中文](#中文) · [Module index](modules/README.md) · [Install guide](INSTALL.md)

## English

### What is documented here

This `docs/` tree contains the **implementation documentation** for LabToolbox (`labtoolbox`, v0.1.14) — a modular Python toolkit for biomedical surface and microbiology data analysis, built around F-DLC antibacterial coatings, laser-induced periodic surface structures (LIPSS) on stainless steel, bacterial adhesion theory and LIVE/DEAD viability assays.

The module pages document the analysis algorithms and behaviour at the **base source commit `0e0508e`**, and are updated for the **release/integration branch** (`46bdd8f`, where these pages were merged together with the app and packaging work). That integration state adds: the ninth GUI tab (`contact_schematic`) and ninth CLI subcommand (`livedead-cellcounter`), pip/installer packaging for all nine module packages, cross-platform CJK fonts, bundled ImageJ 1.54 + a native Temurin 11 JRE inside the installers, and a fix for the vOCG `γ⁺/γ⁻` swap in `xdlvo` (details and corrected numbers in the [xdlvo page](modules/xdlvo.md)).

It complements, and does not replace, the project READMEs in the repository root ([README.md](../README.md) — 中文, [README_EN.md](../README_EN.md) — English) and the install/release guide [docs/INSTALL.md](INSTALL.md).

```
docs/
├── README.md              ← this page
├── INSTALL.md             ← install / release guide (bilingual)
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

* **Install, choose a download, bundled ImageJ and unsigned-build workarounds** → [install guide](INSTALL.md)
* **All modules, one-line descriptions, and how they fit together** → [module index](modules/README.md)
* **Surface/roughness work (AFM/SEM)**: [surfmetrics](modules/surfmetrics.md) → [contact_schematic](modules/contact_schematic.md)
* **Laser-texture quality (SEM)**: [lipss_dloa](modules/lipss_dloa.md) → [semtexture](modules/semtexture.md)
* **Wettability and adhesion theory**: [contact_angle](modules/contact_angle.md) → [xdlvo](modules/xdlvo.md)
* **Viability / microbiology counts**: [livedead_cellcounter](modules/livedead_cellcounter.md) → [livedead](modules/livedead.md)
* **Growth curves**: [growth_curve](modules/growth_curve.md)

### Running the toolbox

**Option 1 — packaged desktop app (recommended for lab users).** The installers and DMGs contain the Python runtime, ImageJ 1.54 and a private Java runtime, so no Python/Java installation is needed and nothing is downloaded at first use. Windows: `LabToolbox-Setup-<version>.exe` or the portable `LabToolbox-Windows-x64.zip`; macOS: Intel and Apple Silicon DMGs. Builds are unsigned, so SmartScreen/Gatekeeper warnings are expected — see [INSTALL.md](INSTALL.md) for the exact workarounds.

**Option 2 — source checkout (developers).**

```bash
pip install -e .                  # core dependencies
pip install -e ".[image]"         # + OpenCV/Pillow (legacy counting engine)
pip install -e ".[build]"         # + PyInstaller (local packaging)
pip install "igor @ git+https://github.com/wking/igor"   # .ibw (Bruker AFM) direct read

python -m labtoolbox.gui         # bilingual tkinter GUI — 9 tabs
labtoolbox --help                # unified CLI — 9 subcommands:
                                 # growth-curve, lipss-dloa, sem-texture, xdlvo,
                                 # livedead, livedead-cellcounter, contact-angle,
                                 # surfmetrics, schematic
```

Engine and font notes:

* **LIVE/DEAD counting engine**: default classic ImageJ 1.54. Packaged apps run the bundled copy (`imagej/ij.jar` + a platform-native Temurin 11 JRE, read-only — no system Java required); a source checkout auto-discovers ImageJ through `LABTOOLBOX_IMAGEJ_DIR`, then the repo/bundle `imagej/` or `vendor/imagej/`, then legacy local installs, with the `java` on `PATH` as a development fallback. The counting macro ships read-only at `scripts/imagej/count_livedead.ijm` and is never copied into the ImageJ folder. If ImageJ is missing, the ImageJ backend raises a clear error listing its search candidates — pass `--backend opencv` to use the legacy engine.
* **Gwyddion backend**: optional, needs WSL Ubuntu + Gwyddion 2.67 + `/usr/local/bin/gwy_batch.py` (`labtoolbox surfmetrics --backend gwyddion`).
* **Fonts**: GUI and figure text resolve CJK fonts per platform (Windows Microsoft YaHei, macOS PingFang, Linux Noto); override with the `LABTOOLBOX_CJK_FONT` environment variable.

Repository data: `examples/` holds the example tables opened by the GUI buttons; `data/examples/` holds sanitized example inputs (a growth-curve CSV, a LIVE/DEAD Excel, a synthetic SEM image). Real study data stay outside the repository.

### Release / integration state

The integration branch that merged these pages differs from the documentation base (`0e0508e`) in the following user-visible ways; the module pages are written against the integration state:

| Area | Integration state |
|---|---|
| GUI | **9 tabs** — adds **📐 接触几何示意** (`contact_schematic`: AFM data folder, sample label, output dir) |
| CLI | **9 subcommands** — adds **`livedead-cellcounter`** (`folder` positional, `--backend imagej\|opencv`, `--min-size`, `--skip-repeats`, `--qc-dir`) |
| Packaging | `pyproject.toml` packages now include **all nine modules** (previously `contact_schematic` and `semtexture` were missing); `[build]` extra; release CI builds a Windows x64 installer + portable zip and macOS Intel/Apple-Silicon DMGs |
| Bundled engine | installers/DMGs embed **ImageJ 1.54** (unmodified `ij.jar`) + a **native Temurin 11 JRE**; the counting macro is bundled read-only; no runtime downloads |
| Fonts | platform-appropriate CJK font selection for the GUI and matplotlib figures |
| XDLVO fix | commit **`46bdd8f`**: the vOCG formamide row is corrected so `γ⁺/γ⁻` are no longer swapped; regression test `tests/test_xdlvo_surface_energy.py` (run with `python -m unittest discover -s tests`) |

The numerical results quoted in each page's QC section were measured at the documentation base `0e0508e`; they remain valid for the integration branch **except** the `xdlvo` contact-angle SFE outputs, whose corrected values are given in the xdlvo page. Known limitations that the integration PR does **not** change are still documented per module (e.g. the cell counter accepts `area_um2` without using it, `xdlvo` still squares negative square roots silently, and `semtexture`'s admissible period band is fixed at 240–800 nm).

### How these pages are written

Each module page follows the same structure: purpose and scientific context; inputs/outputs and formats; end-to-end pipeline; algorithms and formulas with symbols; parameter names and defaults taken from the code; implementation notes; assumptions, limitations and known quirks; QC/validation; references. Algorithm content is not rewritten for app/packaging changes — integration updates touch entry points (GUI/CLI), packaging, bundled-engine discovery and the XDLVO fix. Quirks are documented as they are, including behaviours a reader might not expect from the theory. References are real papers, standards, textbooks and product manuals — DOIs only where confirmed; methods not implemented in the code are not cited.

## 中文

### 本文档的内容

`docs/` 目录包含 LabToolbox（`labtoolbox`，v0.1.14）的**实现级文档**。LabToolbox 是一个模块化的 Python 工具箱，用于生物医学表面与微生物学数据分析，涵盖 F-DLC 抗菌涂层、不锈钢激光诱导周期表面结构（LIPSS）、细菌黏附理论与 LIVE/DEAD 存活率实验。

模块页描述的是**基线源码 commit `0e0508e`** 时的算法与行为，并已按**发布/集成分支**（`46bdd8f`，文档与 app/打包工作合并之处）更新。该集成状态新增：第 9 个 GUI 标签页（`contact_schematic`）与第 9 个 CLI 子命令（`livedead-cellcounter`）、全部九个模块包的 pip/安装包打包、跨平台中文字体、安装包内置 ImageJ 1.54 + 原生 Temurin 11 JRE，以及 `xdlvo` 中 vOCG `γ⁺/γ⁻` 互换的修复（细节与修正后的数值见 [xdlvo 页面](modules/xdlvo.md)）。

它与仓库根目录的项目 README（[README.md](../README.md) 中文、[README_EN.md](../README_EN.md) 英文）以及安装/发布指南 [docs/INSTALL.md](INSTALL.md) 互补，而不是替代它们。

```
docs/
├── README.md              ← 本页
├── INSTALL.md             ← 安装 / 发布指南（双语）
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

* **安装、选择下载、内置 ImageJ 与未签名版本的处理** → [安装指南](INSTALL.md)
* **全部模块、一句话描述、模块间关系** → [模块索引](modules/README.md)
* **表面/粗糙度（AFM/SEM）**：[surfmetrics](modules/surfmetrics.md) → [contact_schematic](modules/contact_schematic.md)
* **激光织构质量（SEM）**：[lipss_dloa](modules/lipss_dloa.md) → [semtexture](modules/semtexture.md)
* **浸润性与黏附理论**：[contact_angle](modules/contact_angle.md) → [xdlvo](modules/xdlvo.md)
* **存活率/微生物计数**：[livedead_cellcounter](modules/livedead_cellcounter.md) → [livedead](modules/livedead.md)
* **生长曲线**：[growth_curve](modules/growth_curve.md)

### 运行工具箱

**方式一——打包桌面应用（实验室用户推荐）。** 安装包与 DMG 已包含 Python 运行时、ImageJ 1.54 与私有 Java 运行时，无需另装 Python/Java，首次使用也不联网下载。Windows：`LabToolbox-Setup-<版本>.exe` 或便携版 `LabToolbox-Windows-x64.zip`；macOS：Intel 与 Apple Silicon 两个 DMG。发布版**未签名**，因此会出现 SmartScreen/Gatekeeper 提示——具体处理方法见 [INSTALL.md](INSTALL.md)。

**方式二——源码运行（开发者）。**

```bash
pip install -e .                  # 核心依赖
pip install -e ".[image]"         # + OpenCV/Pillow（旧计数引擎）
pip install -e ".[build]"         # + PyInstaller（本地打包）
pip install "igor @ git+https://github.com/wking/igor"   # 直读 .ibw（Bruker AFM）

python -m labtoolbox.gui         # 中英双语 tkinter GUI —— 9 个标签页
labtoolbox --help                # 统一 CLI —— 9 个子命令：
                                 # growth-curve, lipss-dloa, sem-texture, xdlvo,
                                 # livedead, livedead-cellcounter, contact-angle,
                                 # surfmetrics, schematic
```

引擎与字体说明：

* **LIVE/DEAD 计数引擎**：默认经典 ImageJ 1.54。打包版运行内置副本（`imagej/ij.jar` + 平台原生的 Temurin 11 JRE，只读，无需系统 Java）；源码运行依次自动探测 `LABTOOLBOX_IMAGEJ_DIR`、仓库/随包 `imagej/` 或 `vendor/imagej/`、旧本地安装，最后才用 `PATH` 里的 `java`（仅开发方便）。计数宏以只读方式随包分发于 `scripts/imagej/count_livedead.ijm`，永远不会被复制进 ImageJ 目录。找不到 ImageJ 时 ImageJ 后端会给出清晰的报错并列出搜索候选——可改用 `--backend opencv` 走旧引擎。
* **Gwyddion 后端**：可选，需要 WSL Ubuntu + Gwyddion 2.67 + `/usr/local/bin/gwy_batch.py`（`labtoolbox surfmetrics --backend gwyddion`）。
* **字体**：GUI 与图内文字按平台选择中文字体（Windows 微软雅黑、macOS PingFang、Linux Noto）；可用环境变量 `LABTOOLBOX_CJK_FONT` 覆盖。

仓库数据：`examples/` 存放 GUI 按钮打开的范例表格；`data/examples/` 存放脱敏示例输入（生长曲线 CSV、LIVE/DEAD Excel、合成 SEM 图）。真实研究数据不入库。

### 发布/集成状态

合并这些文档的集成分支与文档基线（`0e0508e`）相比，有以下用户可见变化；模块页按集成状态撰写：

| 方面 | 集成状态 |
|---|---|
| GUI | **9 个标签页**——新增 **📐 接触几何示意**（`contact_schematic`：AFM 数据目录、样品标签、输出目录） |
| CLI | **9 个子命令**——新增 **`livedead-cellcounter`**（`folder` 位置参数，`--backend imagej\|opencv`、`--min-size`、`--skip-repeats`、`--qc-dir`） |
| 打包 | `pyproject.toml` 的包列表现在包含**全部九个模块**（此前缺 `contact_schematic` 与 `semtexture`）；新增 `[build]` extra；发布 CI 构建 Windows x64 安装包+便携 zip 与 macOS Intel/Apple Silicon DMG |
| 内置引擎 | 安装包/DMG 内置 **ImageJ 1.54**（未修改的 `ij.jar`）+ **平台原生 Temurin 11 JRE**；计数宏随包只读分发；运行时零下载 |
| 字体 | GUI 与 matplotlib 图按平台选择中文字体 |
| XDLVO 修复 | commit **`46bdd8f`**：修正 vOCG 甲酰胺行，`γ⁺/γ⁻` 不再互换；回归测试 `tests/test_xdlvo_surface_energy.py`（运行 `python -m unittest discover -s tests`） |

各页 QC 一节引用的数值是在文档基线 `0e0508e` 上测得的，对集成分支仍然有效——**唯一例外**是 `xdlvo` 的接触角表面能输出，其修正后的数值见 xdlvo 页面。集成 PR **未**改变的已知局限仍按模块记录（例如细胞计数模块接受 `area_um2` 但不使用、`xdlvo` 仍会静默平方负的平方根、`semtexture` 的允许周期带固定为 240–800 nm）。

### 这些页面怎么写

每个模块页结构一致：目的与科学背景；输入/输出与格式；端到端流程；带符号的算法与公式；取自代码的参数名与默认值；实现说明；假设、局限与已知怪癖；质控/验证；参考文献。算法内容不因 app/打包变化而重写——集成更新只涉及入口（GUI/CLI）、打包、内置引擎探测与 XDLVO 修复。怪癖如实记录，包括读者按理论预期不到的行为。参考文献均为真实论文、标准、教科书与产品手册——DOI 只在确认时给出；代码未实现的方法不引用。