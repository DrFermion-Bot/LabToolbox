# -*- coding: utf-8 -*-
"""GUI 多语言支持: 中文 / English"""

# 翻译字典: zh -> en
TRANSLATIONS = {
    "🧪 实验室工具箱 LabToolbox": "🧪 Lab Toolbox",
    "实验室工具箱 LabToolbox": "Lab Toolbox",
    "📈 生长曲线": "📈 Growth Curve",
    "🔬 LIPSS/DLOA": "🔬 LIPSS/DLOA",
    "🧫 XDLVO": "🧫 XDLVO",
    "🦠 LIVE/DEAD": "🦠 LIVE/DEAD",
    "💧 接触角/表面能": "💧 Contact Angle",
    "细菌生长曲线拟合 (OD600 / CFU)": "Bacterial growth curve fitting (OD600 / CFU)",
    "数据文件": "Data file",
    "浏览...": "Browse...",
    "输出目录": "Output dir",
    "🚀 运行生长曲线分析": "🚀 Run growth curve",
    "SEM 图像 LIPSS 周期与取向角分析": "SEM image LIPSS period & orientation (DLOA)",
    "SEM 图像文件夹": "SEM image folder",
    "每微米像素数": "Pixels per µm",
    "(31.25 nm/px = 32)": "(31.25 nm/px = 32)",
    "🚀 运行 DLOA 分析": "🚀 Run DLOA",
    "XDLVO 细菌粘附预测": "XDLVO bacterial adhesion prediction",
    "θ 二碘甲烷 (°)": "θ diiodomethane (°)",
    "θ 水 (°)": "θ water (°)",
    "θ 甲酰胺 (°)": "θ formamide (°)",
    "细菌半径 (nm)": "Bacteria radius (nm)",
    "离子强度 (M)": "Ionic strength (M)",
    "🚀 运行 XDLVO 分析": "🚀 Run XDLVO",
    "LIVE/DEAD 存活率统计 + 双因素 ANOVA": "LIVE/DEAD viability + two-way ANOVA",
    "工作表名 (可选)": "Sheet name (optional)",
    "🚀 运行 LIVE/DEAD 分析": "🚀 Run LIVE/DEAD",
    "OWRK 表面自由能计算": "OWRK surface free energy",
    "液体1 接触角 (°)": "Liquid 1 angle (°)",
    "液体2 接触角 (°)": "Liquid 2 angle (°)",
    "液体1": "Liquid 1",
    "液体2": "Liquid 2",
    "🚀 计算表面能": "🚀 Compute SFE",
    "就绪 - 选择一个模块配置并运行": "Ready - pick a module and run",
    "⏳ 运行中...": "⏳ Running...",
    "✅ 完成! 输出见输出目录": "✅ Done! Output saved",
    "分析完成!": "Analysis complete!",
    "图表: ": "Figure: ",
    "错误": "Error",
    "完成": "Done",
    # LIVE/DEAD 细胞计数标签页 (第 6 模块)
    "🔬 LIVE/DEAD 细胞计数": "🔬 LIVE/DEAD Cell Count",
    "荧光图像计数: repeat1/2/3 → 1h/3h → area-channelN":
        "Fluorescence counting: repeat1/2/3 → 1h/3h → area-channelN",
    "图像根文件夹": "Image root folder",
    "结构: 根文件夹/repeat1/1h/1-g1.tif (g=活菌) + 1-r1.tif (r=死菌)\n"
    "文件名: {区域}-{g|r}{编号}, 区域 c=Control, 1/2/3=测试区\n"
    "引擎: imagej (默认方法学: ImageJ 1.54 自适应阈值 + Analyze Particles) / "
    "opencv (旧 Python 引擎, 仅排查对照; 阈值/圆形度只对它生效)":
        "Structure: root/repeat1/1h/1-g1.tif (g=live) + 1-r1.tif (r=dead)\n"
        "Filename: {area}-{g|r}{number}, c=Control, 1/2/3=test area\n"
        "Engine: imagej (default methodology: ImageJ 1.54 adaptive threshold + Analyze Particles) / "
        "opencv (legacy Python engine, troubleshooting only; threshold/roundness apply to it only)",
    "最小面积(px)": "Min area (px)",
    "圆形度": "Roundness",
    "绿阈值": "Green thresh",
    "红阈值": "Red thresh",
    "🚀 运行细胞计数分析": "🚀 Run cell counting",
    # 范例表格相关
    "范例: ": "Example: ",
    "打开范例表格": "Open example table",
    "提示": "Notice",
    "范例文件不存在: ": "Example file not found: ",
    # 表面形貌标签页 (第 7 模块)
    "🏔️ 表面形貌": "🏔️ Surface Morphology",
    "AFM/SEM 高度图 → 3D 图 + 粗糙度 (Sa/Sq/Sz) + 表面积 (Sdr)":
        "AFM/SEM height map → 3D + roughness (Sa/Sq/Sz) + surface area (Sdr)",
    "高度图文件": "Height map file",
    "批量文件夹 (.ibw)": "Batch folder (.ibw)",
    "通道 (空=自动)": "Channel (blank=auto)",
    "像素尺寸 X (nm, 空=自动)": "Pixel size X (nm, blank=auto)",
    "🚀 运行表面分析": "🚀 Run surface analysis",
    "🧭 织构一致性": "🧭 Texture Consistency",
    "SEM 织构一致性与合格区面积": "SEM texture consistency & ordered-area map",
    "SEM 图像根目录（子文件夹=分组）": "SEM root folder (sub-folders = groups)",
    "像素尺寸 nm（空=自动）": "Pixel size nm (blank = auto)",
    "分块边长 (px)": "Tile edge (px)",
    "判定窗边长 (µm)": "Window edge (µm)",
    "🚀 运行一致性分析": "🚀 Run consistency analysis",
    # 细胞计数引擎选择 (第 6 标签页)
    "计数引擎": "Counting engine",
    "未找到 (可设 LABTOOLBOX_IMAGEJ_DIR)": "not found (set LABTOOLBOX_IMAGEJ_DIR)",
    # 接触几何示意标签页 (第 9 模块)
    "📐 接触几何示意": "📐 Contact Schematic",
    "细菌-织构接触几何示意图 (AFM 流程末端)":
        "Bacteria-texture contact schematic (end of AFM flow)",
    "AFM 数据目录": "AFM data folder",
    "样品标签": "Sample label",
    "输出: fig1/2/3 接触示意图 + geometry_measurements.csv + README.md":
        "Outputs: fig1/2/3 schematics + geometry_measurements.csv + README.md",
    "🚀 运行接触几何示意": "🚀 Run contact schematic",
    "(进标题, 如 515 nm)": "(shown in title, e.g. 515 nm)",
    "无法打开范例文件: ": "Cannot open example file: ",
    "(.ibw 自动读取)": "(read from .ibw automatically)",
}


def tr(text, lang="zh"):
    """翻译: lang='zh' 返回原文, lang='en' 返回英文"""
    if lang == "en" and text in TRANSLATIONS:
        return TRANSLATIONS[text]
    return text
