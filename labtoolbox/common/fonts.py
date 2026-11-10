# -*- coding: utf-8 -*-
"""跨平台中文字体 (tkinter 样式 / matplotlib 图内文字共用).

背景: 旧代码把 "Microsoft YaHei UI" 写死在 tkinter 样式里, 到 macOS/Linux 上中文
会变成豆腐块; matplotlib 侧也只在 Windows 字体路径里找. 这里按平台给出候选:

  Windows  Microsoft YaHei UI / Microsoft YaHei / SimHei
  macOS    PingFang SC / Hiragino Sans GB / STHeiti
  Linux    Noto Sans CJK SC / Source Han Sans SC / WenQuanYi Zen Hei

可用环境变量 LABTOOLBOX_CJK_FONT 强制指定字体家族名 (打包/排查用).
"""
import os
import sys

# tkinter: 字体家族名 (Tk 认识的名字, 如 "Microsoft YaHei UI" / "PingFang SC")
_FAMILIES = {
    "win32": ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei",
              "Noto Sans CJK SC", "Source Han Sans SC", "DejaVu Sans"],
    "darwin": ["PingFang SC", "Hiragino Sans GB", "Heiti SC", "STHeiti",
               "Noto Sans CJK SC", "Source Han Sans SC", "DejaVu Sans"],
    "linux": ["Noto Sans CJK SC", "Source Han Sans SC", "Noto Sans SC",
              "WenQuanYi Zen Hei", "WenQuanYi Micro Hei", "DejaVu Sans"],
}

# matplotlib: .ttc/.ttf 文件 (matplotlib 自带的字体扫描不一定覆盖这些系统路径,
# 手动 addfont 一次即可; msyh.ttc 在 Windows 上原本就是这么加的)
_FONT_FILES = {
    "win32": [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
              r"C:\Windows\Fonts\simhei.ttf"],
    "darwin": ["/System/Library/Fonts/PingFang.ttc",
               "/System/Library/Fonts/STHeiti Light.ttc",
               "/System/Library/Fonts/STHeiti Medium.ttc",
               "/System/Library/Fonts/Hiragino Sans GB.ttc",
               "/Library/Fonts/Arial Unicode.ttf"],
    "linux": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"],
}

# matplotlib: 字体家族名 (优先级同 _FAMILIES, 但 matplotlib 里 "Microsoft YaHei"
# 是家族名, 不带 UI 后缀)
_MPL_FAMILIES = {
    "win32": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC"],
    "darwin": ["PingFang SC", "Hiragino Sans GB", "Heiti SC", "STHeiti",
               "Noto Sans CJK SC", "Source Han Sans SC"],
    "linux": ["Noto Sans CJK SC", "Source Han Sans SC", "Noto Sans SC",
              "WenQuanYi Zen Hei", "WenQuanYi Micro Hei"],
}

_MPL_READY = False
_MPL_READY_NAME = None


def platform_key():
    """返回 "win32" / "darwin" / "linux" (未知平台按 linux 处理)."""
    p = sys.platform
    if p.startswith("win"):
        return "win32"
    if p == "darwin":
        return "darwin"
    return "linux"


def font_family_candidates(platform=None):
    """tkinter 可用的中文字体家族候选 (按优先级)."""
    return list(_FAMILIES.get(platform or platform_key(), _FAMILIES["linux"]))


def font_file_candidates(platform=None):
    """matplotlib 需要手动注册的字体文件候选 (按优先级)."""
    return list(_FONT_FILES.get(platform or platform_key(), _FONT_FILES["linux"]))


def matplotlib_family_candidates(platform=None):
    """matplotlib 字体家族候选 (按优先级)."""
    return list(_MPL_FAMILIES.get(platform or platform_key(), _MPL_FAMILIES["linux"]))


def _forced_family():
    """环境变量强制的字体家族 (可选)."""
    return os.environ.get("LABTOOLBOX_CJK_FONT", "").strip() or None


def pick_tk_font(root=None, candidates=None):
    """选一个当前 Tk 真的认得的字体家族; 选不到返回 Tk 默认字体家族.

    必须在 Tk() 之后调用 (字体枚举依赖 Tk 解释器). 不改变任何样式, 只返回家族名.
    """
    forced = _forced_family()
    if forced:
        return forced
    cands = candidates or font_family_candidates()
    try:
        from tkinter import font as tkfont
        known = set(tkfont.families(root))
    except Exception:  # noqa: BLE001 - 字体枚举失败就按候选顺序信一次
        return cands[0] if cands else None
    for name in cands:
        if name in known:
            return name
    try:
        from tkinter import font as tkfont
        return tkfont.nametofont("TkDefaultFont").actual("family")
    except Exception:  # noqa: BLE001
        return cands[0] if cands else None


def setup_matplotlib_cjk(force=False):
    """让 matplotlib 图里的中文正常显示 (缺字体 → 豆腐块).

    做两件事: (1) 把平台字体文件注册进 matplotlib; (2) 从实际可用家族里挑第一个,
    写进 rcParams["font.sans-serif"]. 幂等 (force=True 可重跑). 返回选中的家族名.
    """
    global _MPL_READY, _MPL_READY_NAME
    if _MPL_READY and not force:
        return _MPL_READY_NAME
    try:
        import matplotlib
        from matplotlib import font_manager
    except Exception:  # noqa: BLE001 - 没装 matplotlib 时静默跳过
        _MPL_READY = True
        return None
    for path in font_file_candidates():
        if os.path.exists(path):
            try:
                font_manager.fontManager.addfont(path)
            except Exception:  # noqa: BLE001 - .ttc 解析失败就跳过, 不阻塞出图
                pass
    try:
        available = {f.name for f in font_manager.fontManager.ttflist}
    except Exception:  # noqa: BLE001
        available = set()
    families = matplotlib_family_candidates()
    forced = _forced_family()
    if forced:
        families = [forced] + [f for f in families if f != forced]
    selected = None
    for name in families:
        if name in available:
            matplotlib.rcParams["font.sans-serif"] = [name] + [
                f for f in families if f != name] + ["DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            selected = name
            break
    else:
        matplotlib.rcParams["axes.unicode_minus"] = False
    _MPL_READY = True
    _MPL_READY_NAME = selected
    return selected