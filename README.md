# 实验室工具箱 (LabToolbox)

> **English README**: [README_EN.md](README_EN.md) | **中文**: [README.md](README.md)

Ruinong Pan 的生物医学实验室分析工具集 — 将 OneDrive 共享文件夹中的零散程序整合为统一、模块化、可扩展的工具箱。

## 📥 下载与安装

每个平台一个桌面应用；安装包 / DMG **内置 ImageJ 1.54 与私有 Java 运行时**，无需安装
Python / ImageJ / Java，首次使用不联网下载。

| 平台 | 文件 | 说明 |
|---|---|---|
| 🪟 Windows 10/11 (x64) | `LabToolbox-Setup-<版本>.exe` | 安装版（推荐，中文/英文向导，带卸载） |
| 🪟 Windows 10/11 (x64) | `LabToolbox-Windows-x64.zip` | 便携版（解压即用，无需安装） |
| 🍎 macOS 11+ · Apple 芯片 | `LabToolbox-macOS-AppleSilicon.dmg` | M1/M2/M3/M4 原生 |
| 🍎 macOS 11+ · Intel | `LabToolbox-macOS-Intel.dmg` | Intel Mac 原生 |

> ⚠️ 发布包**未签名**（没有 Windows 代码签名证书，也没有 Apple Developer ID / 公证）：
> Windows 首次运行 SmartScreen 提示「更多信息 → 仍要运行」；macOS 首次启动需
> 「按住 Control 点按 → 打开」，或执行
> `xattr -dr com.apple.quarantine /Applications/LabToolbox.app`。
> 完整步骤、常见问题与「以后如何加签名」见 **[docs/INSTALL.md](docs/INSTALL.md)**。

下载页：<https://github.com/DrFermion/LabToolbox/releases>

## 📦 已整合模块

| 模块 | 功能 | 依赖 |
|---|---|---|
| `growth_curve` | 细菌生长曲线拟合与 OD/CFU 分析 (E. coli, S. aureus) | numpy, scipy, matplotlib |
| `lipss_dloa` | SEM 图像 LIPSS 周期/取向角分析 (DLOA) | numpy, scipy, opencv, matplotlib |
| `xdlvo` | XDLVO 理论细菌粘附预测 (接触角 → 表面能 → ΔG) | numpy, scipy |
| `livedead` | LIVE/DEAD 荧光统计 (存活率, 双因素 ANOVA) | pandas, statsmodels, openpyxl |
| `livedead_cellcounter` | LIVE/DEAD 荧光图像细胞计数 (repeat/时间/区域, 汇总+ANOVA) | numpy, opencv, Pillow |
| `contact_angle` | 接触角/表面自由能计算 (OWRK 等) | numpy, scipy |
| `surfmetrics` | AFM/SEM 高度图 → 3D 图 + 粗糙度 (Sa/Sq/Sz) + 表面积 (Sdr) | numpy, scipy, tifffile, igor* |
| `contact_schematic` | **AFM 流程末端**: 实测几何 (周期/纹深/尖峰间距/柱高) → 细菌黏附 3D 示意图 + 接触几何图 | numpy, scipy, matplotlib, igor* |
| `semtexture` | **多块样品一致性**: SEM 织构周期/取向/相干度 + 分块合格区面积 + 缺陷密度 + 批量一致性判据 (周期 CV / 取向 SD / ICC) | numpy, scipy, pandas, matplotlib, Pillow |

> *`igor` 用于 Bruker .ibw 直读, 需从 GitHub 安装: `pip install "igor @ git+https://github.com/wking/igor"` (PyPI 上的 `igor` 是空壳, 勿装)。

## 🚀 快速开始

```bash
pip install -e .
# 或带图像处理依赖
pip install -e ".[image]"

# 🖥️ 图形界面 (推荐! 点点点就能用)
python -m labtoolbox.gui

# 命令行入口
labtoolbox --help
labtoolbox growth-curve --data data/growth_Ecoli.xlsx
labtoolbox lipss-dloa --folder data/sem_images/
labtoolbox sem-texture --folder data/sem_images/ --output 结果目录   # 织构一致性
labtoolbox xdlvo --angles '{"theta_diiodo":48.2,"theta_water":72.3,"theta_form":61.5}'
labtoolbox livedead --file data/livedead.xlsx
labtoolbox livedead-cellcounter examples/livedead_counter_demo --output 结果目录   # LIVE/DEAD 图像计数 (默认 ImageJ)
labtoolbox contact-angle --theta1 72.3 --theta2 48.2
labtoolbox surfmetrics --folder "AFM 数据目录" --output 结果目录   # 批量: .ibw 直读, 自动校准
# 通道默认自动选 ZSR (ZSensor Retrace, 表面粗糙度分析要求); 旧口径用 --channel height
# 参考线: --profile-mode cross (LIPSS 一条跨纹线) / hv (横纵两条) / auto; 条纹搜索带 --stripe-band 258 772
labtoolbox surfmetrics --file sample.ibw                          # 单文件
labtoolbox schematic --input "AFM 数据目录" --out 结果目录 --label "515 nm"   # 细菌-织构接触示意图 (AFM 末端步骤)
```

## 🖥️ GUI 界面 (tkinter, 零额外依赖)

```
🧪 实验室工具箱 LabToolbox
┌──────────────────────────────────────────────┐
│ [📈 生长曲线] [🔬 LIPSS/DLOA] [🧭 织构一致性] [🧫 XDLVO] [🦠 LIVE/DEAD] [💧 接触角] [🔬 细胞计数] [🏔️ 表面形貌] [✏️ 接触示意] │
│                                                                      │
│  每个标签页 = 一个模块的配置面板                                     │
│  (选文件/填参数 → 点"运行" → 结果自动输出)                          │
└──────────────────────────────────────────────┘
```

- 启动: `python -m labtoolbox.gui`
- 9 个独立标签页（含接触几何示意图与织构一致性）, 参数可视化填写
- 分析结果自动保存到输出目录, 完成弹窗提示

## 🧩 模块化设计 (为扩展而生)

```
labtoolbox/
├── common/          # 共享工具: 文件 IO, 拟合, 统计, 绘图
├── growth_curve/    # 生长曲线
├── lipss_dloa/      # LIPSS/DLOA
├── xdlvo/           # XDLVO
├── livedead/        # LIVE/DEAD
├── livedead_cellcounter/  # LIVE/DEAD 荧光图像细胞计数
├── contact_angle/   # 接触角/表面能
├── cli.py           # 统一命令行入口
└── __init__.py
```

**如何添加新模块**: 在 `labtoolbox/` 下新建包 (如 `raman/`), 实现 `run(config) -> dict` 接口, 在 `cli.py` 注册子命令即可 — 无需改动其他模块。

## 🔬 数据说明

- 原始数据保留在 OneDrive 共享文件夹 (不提交到仓库)
- `data/examples/` 提供示例数据 (脱敏)
- `examples/` 提供 GUI "打开范例表格" 按钮用到的范例文件 (生长曲线 / LIVE/DEAD)
- 所有模块支持 Excel/CSV 输入, 图表输出到 `output/`

## 📚 模块文档

每个模块的完整实现文档（English + 中文：用途、输入输出、算法与公式、参数默认值、
实现细节、假设与局限、参考文献）：

**[docs/modules/README.md](docs/modules/README.md)** — 索引 + 9 个模块页面
(`growth_curve` / `lipss_dloa` / `xdlvo` / `livedead` / `livedead_cellcounter` /
`contact_angle` / `surfmetrics` / `contact_schematic` / `semtexture`)。

## 🛠️ 从源码构建与打包

```bash
pip install -e ".[build]"        # pyinstaller + igor (Bruker .ibw 直读)
python scripts/fetch_imagej.py   # 下载 ImageJ 1.54 + 本机原生 Temurin 11 JRE -> vendor/imagej
pyinstaller labtoolbox.spec --noconfirm
python scripts/verify_bundle.py  # 校验 dist: imagej/ij.jar、jre、计数宏、igor
```

CI (GitHub Actions) 在 `v*` tag 上自动构建 **Windows x64 安装包 + 便携 zip**、
**macOS Intel DMG**、**macOS Apple Silicon DMG** 三个产物并发布到 Releases；
手动触发 `workflow_dispatch` 只构建不发布。未签名，无公证步骤。

## 📄 License

MIT (待定)

## 🧰 开源工具后端 (2026-09-08)

科研可信性: 计数与 AFM 处理可切换到审稿人认可的开源工具内核, 与自研 Python 交叉验证一致。

- **ImageJ 计数 (默认引擎)**: `livedead_cellcounter.run()` 默认 `backend="imagej"` — 经典 ImageJ 1.54
  批处理 (自适应阈值背景众数+40 + Analyze Particles 3-500px)。宏在 `scripts/imagej/count_livedead.ijm`。
  **发布版已内置** ImageJ 1.54 与原生 Java 运行时 (无需安装 Java/ImageJ, 离线可用, 宏只读不再复制)；
  源码运行时可用环境变量 `LABTOOLBOX_IMAGEJ_DIR` 指向本机 ImageJ 安装目录 (经典 1.54, 非 Fiji)。
  引擎缺失时会报错并列出候选路径；旧 OpenCV 引擎需显式传 `--backend opencv`（不会自动回退）。
  旧的 Python/OpenCV 分水岭引擎保留为 `backend="opencv"`, 仅供故障排查/回归对照 —
  方法学与交付统一走 ImageJ (2026-09-11 定), 不再做 Python/ImageJ 双引擎交叉验证。
  历史对比: 515nm 组 160 配对, ImageJ vs 旧 OpenCV 引擎差异主因 = 旧引擎缺通道陷阱修正。
- **Gwyddion AFM 内核**: `labtoolbox surfmetrics --backend gwyddion` — WSL Ubuntu 内 Gwyddion 2.67
  内核 (pygwy, python2.7 编译), 真·平面扣除 + ISO 统计。批处理脚本 `scripts/gwy_batch.py` 部署于
  WSL `/usr/local/bin/gwy_batch.py`。对比: 515 样品 20 ibw, Python vs Gwyddion raw 100% 逐位一致;
  ZS 通道 level 修正未展平文件 (Sa 16.1→3.8 nm)。
- 对比复现: `scripts/compare_count_backends.py` (计数), `scripts/compare_surf_515.py` / 
  `compare_surf_515_zs.py` (AFM), 输出在 `scripts/output/` (不入库)。
