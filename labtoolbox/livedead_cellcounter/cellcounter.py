# -*- coding: utf-8 -*-
"""
LIVE/DEAD 荧光显微镜细胞计数模块 (LiveDeadCellCounter)
整合自 counter2.2.0 计数引擎 + F-DLC_stats_fixed.R 统计流程

输入文件夹结构:
  ├── repeat1/           (重复实验 1)
  │   ├── 1h/            (采样时间 1h)
  │   │   ├── 1-r2.tif   (processed area 1 - red channel graph 2)
  │   │   ├── 1-g2.tif   (processed area 1 - green channel graph 2)
  │   │   └── ...
  │   ├── 3h/
  │   └── 5h/
  ├── repeat2/
  └── repeat3/

文件名格式: {area}-{channel}{number}.tif
  area:    1/2/3... (测试区域) 或 c (control 区域)
  channel: r (红色=死菌) / g (绿色=活菌)
  number:  同区域内采样编号

输出:
  - 汇总表 (活菌/死菌/总数/死亡率/标准差, 所有 Control 合并)
  - 柱状图 (Control/Area1/Area2... 分组 + ANOVA 标注)
  - 统计分析表 (双因素 ANOVA + 逐时间点 Tukey)
"""
import glob
import os
import re
import shutil
import sys
import warnings

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ..common.fonts import platform_key, setup_matplotlib_cjk
from ..common.io_utils import save_figure, save_csv, ensure_output_dir

# 中文字体 (Windows 雅黑 / macOS PingFang / Linux Noto, 见 common/fonts.py)
try:
    setup_matplotlib_cjk()
except Exception:  # noqa: BLE001 - 字体只影响图注显示, 不能阻塞计数
    pass


# ==================== ImageJ 发现 (源码运行 + PyInstaller 打包 app) ====================
# 打包路径契约 (与 packaging/labtoolbox.spec 一致, 随安装包分发, 无运行时下载):
#   <bundle>/imagej/ij.jar
#   <bundle>/imagej/jre/bin/java.exe                  Windows (Temurin JRE)
#   <bundle>/imagej/jre/Contents/Home/bin/java        macOS (Temurin JRE)
#   <bundle>/scripts/imagej/count_livedead.ijm        宏 (只读直接引用, 不复制)
# bundle 根 = sys._MEIPASS: PyInstaller 6 Windows onedir 的 _internal / macOS .app
# 的 Contents/Frameworks; 另兼容 exe 同级 imagej/ (onedir 平铺) 与 .app 的
# Contents/Resources|Frameworks. 环境变量 LABTOOLBOX_IMAGEJ_DIR 可覆盖 (指向含
# ij.jar 的 ImageJ 目录, 或指向含 imagej/ 的 bundle 根).

# 旧版源码安装候选 (2026-10: F: 已搬到 E:; 依次探测, 兼容再次搬家)
IMAGEJ_CANDIDATES = [r"E:/ImageJ/ImageJ", r"F:/ImageJ/ImageJ", r"C:/Users/PC/Downloads/ImageJ"]

# 本模块所在仓库根: labtoolbox/livedead_cellcounter/cellcounter.py → 上三级.
# 打包后 __file__ 在 _MEIPASS 内, 该路径自然等于 bundle 根, 不会指回构建机.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_MACRO_NAME = "count_livedead.ijm"

# ImageJ 安装目录里的 java 相对路径 (按平台排序; 三种 JRE 布局都认)
_JAVA_REL = {
    "win32": [("jre", "bin", "java.exe"), ("jre", "bin", "java"),
              ("jre", "Contents", "Home", "bin", "java"),
              ("bin", "java.exe"), ("bin", "java")],
    "darwin": [("jre", "Contents", "Home", "bin", "java"), ("jre", "bin", "java"),
               ("jre", "bin", "java.exe"), ("bin", "java")],
}
_JAVA_REL_DEFAULT = [("jre", "bin", "java"), ("jre", "Contents", "Home", "bin", "java"),
                     ("jre", "bin", "java.exe"), ("bin", "java")]


def _dedupe(paths):
    """去重但保持顺序 (同一路径只探测一次)."""
    out, seen = [], set()
    for p in paths:
        if not p:
            continue
        key = os.path.normcase(os.path.abspath(p))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _bundle_roots():
    """PyInstaller/打包 app 的根目录候选 (源码运行返回空列表)."""
    if not (getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None)):
        return []
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(meipass)
        roots.append(os.path.join(meipass, "_internal"))
        contents = os.path.dirname(os.path.abspath(meipass))
        roots += [os.path.join(contents, "Resources"),
                  os.path.join(contents, "Frameworks")]
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    roots.append(exe_dir)
    roots.append(os.path.join(exe_dir, "_internal"))
    contents = os.path.dirname(exe_dir)
    roots += [os.path.join(contents, "Resources"), os.path.join(contents, "Frameworks")]
    return _dedupe(roots)


def imagej_dir_candidates():
    """按优先级返回 ImageJ 安装目录候选 (不保证存在)."""
    cands = []
    env = os.environ.get("LABTOOLBOX_IMAGEJ_DIR", "").strip()
    if env:
        cands += [env, os.path.join(env, "imagej")]
    for root in _bundle_roots():
        cands.append(os.path.join(root, "imagej"))
    cands += [os.path.join(_REPO_ROOT, "imagej"),
              os.path.join(_REPO_ROOT, "vendor", "imagej")]
    cands += list(IMAGEJ_CANDIDATES)
    return _dedupe(cands)


def find_imagej_jar(imagej_dir):
    """ImageJ 核心 jar; 不存在返回 None."""
    if not imagej_dir:
        return None
    p = os.path.join(imagej_dir, "ij.jar")
    return p if os.path.isfile(p) else None


def find_java(imagej_dir):
    """在 ImageJ 目录里找 java 可执行文件 (平台相关布局).

    找不到时才退回 PATH 里的 java (仅为源码/开发方便; 打包版总是自带 JRE).
    """
    if not imagej_dir:
        return None
    for rel in _JAVA_REL.get(platform_key(), _JAVA_REL_DEFAULT):
        p = os.path.join(imagej_dir, *rel)
        if os.path.isfile(p):
            return p
    return shutil.which("java")


def find_imagej():
    """探测 ImageJ: {'dir','jar','java','searched'} — 找不到时 dir/jar/java 为 None."""
    searched = imagej_dir_candidates()
    for d in searched:
        jar = find_imagej_jar(d)
        if jar:
            return {"dir": d, "jar": jar, "java": find_java(d), "searched": searched}
    return {"dir": None, "jar": None, "java": None, "searched": searched}


def find_imagej_dir():
    """兼容旧接口: 探测到的 ImageJ 安装目录; 找不到时返回首个候选 (沿用旧行为)."""
    st = find_imagej()
    if st["dir"]:
        return st["dir"]
    return imagej_dir_candidates()[0]


def _macro_candidates(imagej_dir=None):
    """宏文件候选 (打包/仓库副本优先, 安装目录副本其次)."""
    out = []
    env = os.environ.get("LABTOOLBOX_IMAGEJ_DIR", "").strip()
    if env:
        # env 可指向 ImageJ 安装目录, 也可指向 bundle 根 (含 imagej/ 与 scripts/)
        out += [os.path.join(env, "macros", _MACRO_NAME),
                os.path.join(env, "imagej", "macros", _MACRO_NAME),
                os.path.join(env, "scripts", "imagej", _MACRO_NAME)]
    for root in _bundle_roots():
        out += [os.path.join(root, "scripts", "imagej", _MACRO_NAME),
                os.path.join(root, "imagej", "macros", _MACRO_NAME)]
    out += [os.path.join(_REPO_ROOT, "scripts", "imagej", _MACRO_NAME),
            os.path.join(_REPO_ROOT, "imagej", "macros", _MACRO_NAME),
            os.path.join(_REPO_ROOT, "vendor", "imagej", "macros", _MACRO_NAME)]
    if imagej_dir:
        out.append(os.path.join(imagej_dir, "macros", _MACRO_NAME))
    out += [os.path.join(c, "macros", _MACRO_NAME) for c in IMAGEJ_CANDIDATES]
    return _dedupe(out)


def find_macro(imagej_dir=None):
    """可用的 count_livedead.ijm 绝对路径; 找不到返回 None.

    打包 app 只读, 所以宏从 bundle/仓库位置直接引用 (ImageJ -batch 接受任意
    绝对路径), 不再复制进 ImageJ 安装目录.
    """
    for p in _macro_candidates(imagej_dir):
        if os.path.isfile(p):
            return p
    return None


def imagej_status():
    """GUI/诊断用: 一行探测结果 (dir/java/jar/macro/found + 探测过的候选)."""
    st = find_imagej()
    st["macro"] = find_macro(st["dir"])
    st["found"] = bool(st["dir"] and st["java"])
    return st


# ==================== 计数引擎 (整合自 counter2.2.0) ====================
class ImageJEngine:
    """ImageJ 计数引擎 (开源工具后端, 替代/对照 OpenCV 引擎)

    方法学: 自适应阈值 = 背景直方图众数+40 -> 通道陷阱修正 (命名 g/r 通道
    无信号时取最亮通道) -> Analyze Particles size 3-500 px。
    引擎: 经典 ImageJ 1.54 headless (-batch), 目录级批处理 + 缓存。
    接口与 CellCounterEngine 对齐: count_live_dead(path) -> {'green','red'}

    路径: 打包版用随包的 <bundle>/imagej/ij.jar + 平台对应 JRE (系统 Java 非必需);
    源码运行依次探测 LABTOOLBOX_IMAGEJ_DIR、bundle/仓库/vendor 与旧安装路径。
    宏 scripts/imagej/count_livedead.ijm 只读直接引用 (不复制进安装目录); 宏需为纯 ASCII,
    中文路径走 UTF-8 参数文件, Image-Pro 假校准会自动清除。
    """

    def __init__(self, imagej_dir=None, min_size=3, max_size=500,
                 bg_offset=40, qc_dir=None):
        """qc_dir: 可选 QC 输出根目录 — 每张图存 <stem>_qc.png (每个被计数粒子画
        品红圈+编号), 用于故障排查 (数 0/漏数/多圈时看圈位置). None = 不输出."""
        self.imagej_dir = imagej_dir or find_imagej_dir()
        self.min_size = int(min_size)
        self.max_size = int(max_size)
        self.bg_offset = int(bg_offset)
        self.qc_dir = qc_dir
        self._cache = {}  # dirname -> {filename: count}

    # -- 内部: 目录级 ImageJ 批处理 --
    def _macro_path(self):
        """宏文件绝对路径 (只读直接引用, 不复制进 ImageJ 安装目录).

        打包后 app bundle (.app / Program Files) 只读, 所以优先用 bundle/仓库里的
        scripts/imagej/count_livedead.ijm, 其次才是 ImageJ 安装目录 macros/ 里已有
        的副本; 都找不到时返回最可能的位置, 由 _batch_dir 给出可读报错。
        """
        found = find_macro(self.imagej_dir)
        if found:
            return found
        cands = _macro_candidates(self.imagej_dir)
        return cands[0] if cands else _MACRO_NAME

    def _batch_dir(self, directory):
        """跑一次 ImageJ 批处理整个目录, 填充缓存 {fname: count}"""
        import subprocess, tempfile
        macro = self._macro_path()
        if not os.path.exists(macro):
            raise FileNotFoundError(
                f"ImageJ 宏不存在: {macro} — 打包版应随包提供 "
                f"scripts/imagej/count_livedead.ijm; 源码运行可设 LABTOOLBOX_IMAGEJ_DIR. "
                f"候选: {_macro_candidates(self.imagej_dir)[:6]}")
        java = find_java(self.imagej_dir)
        ij_jar = find_imagej_jar(self.imagej_dir)
        if not java or not ij_jar:
            raise FileNotFoundError(
                f"ImageJ 未安装完整: {self.imagej_dir} (需要 ij.jar + "
                f"jre/bin/java.exe | jre/bin/java | jre/Contents/Home/bin/java) — "
                f"候选: {imagej_dir_candidates()[:6]}")
        fd, args_path = tempfile.mkstemp(suffix=".txt", prefix="ij_args_")
        out_csv = args_path + ".csv"
        qc_sub = ""
        if self.qc_dir:
            qc_sub = os.path.join(self.qc_dir, os.path.basename(directory.rstrip("/\\")))
            os.makedirs(qc_sub, exist_ok=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(directory.replace("\\", "/") + "\n")
            f.write(out_csv.replace("\\", "/") + "\n")
            f.write((qc_sub.replace("\\", "/") if qc_sub else "") + "\n")
            f.write(str(self.min_size) + "\n")   # macro line 4: min particle size (px)
            f.write(str(self.max_size) + "\n")   # macro line 5: max particle size (px)
        env = dict(os.environ, JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8")
        cmd = [java, "-cp", ij_jar, "ij.ImageJ", "-batch", macro, args_path]
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True,
                                  text=True, timeout=1800)
        finally:
            try:
                os.unlink(args_path)
            except OSError:
                pass
        counts = {}
        if os.path.exists(out_csv):
            import csv
            with open(out_csv, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    try:
                        counts[row["filename"]] = int(float(row["count"]))
                    except (ValueError, KeyError):
                        counts[row["filename"]] = 0
            try:
                os.unlink(out_csv)
            except OSError:
                pass
        self._cache[directory] = counts
        return counts

    # -- 对外接口 (与 CellCounterEngine 对齐) --
    def count_live_dead(self, img_path):
        """单张图: 返回 {'green': n, 'red': n}.
        g 图数绿色通道(活菌), r 图数红色通道(死菌) — ImageJ 宏已按命名通道单边计数.
        """
        img_path = os.path.abspath(img_path)
        d = os.path.dirname(img_path)
        if d not in self._cache:
            self._batch_dir(d)
        fn = os.path.basename(img_path)
        cnt = self._cache[d].get(fn, 0)
        low = fn.lower()
        # 命名通道: 形如 '1-g2.tif' / 'c_r1.tif' 中 g/r 位于数字前
        import re
        m = re.search(r"[-_]?([rg])[_-]?\d+", low)
        is_g = (m.group(1) == "g") if m else ("-g" in low)
        return {"green": cnt if is_g else 0, "red": 0 if is_g else cnt}

    def count_live_dead_pair(self, g_img, r_img):
        """(可选) 显式配对, 避免文件名歧义"""
        d = os.path.dirname(os.path.abspath(g_img))
        if d not in self._cache:
            self._batch_dir(d)
        fn_g = os.path.basename(g_img)
        fn_r = os.path.basename(r_img)
        live = self._cache[d].get(fn_g, 0)
        dead = self._cache[d].get(fn_r, 0)
        return {"green": live, "red": dead}


class CellCounterEngine:
    """荧光图像细胞计数引擎 (分水岭粘连分割版)"""

    def __init__(self, min_size=10, max_size=1000, kernel_size=3,
                 green_thresh=20, red_thresh=30, min_roundness=0.6,
                 min_channel_ratio=1.2, split_thresh=0.1):
        self.min_size = min_size
        self.max_size = max_size
        self.kernel_size = kernel_size
        self.green_thresh = green_thresh
        self.red_thresh = red_thresh
        self.min_roundness = min_roundness
        self.min_channel_ratio = min_channel_ratio
        self.split_thresh = split_thresh

    def extract_channel(self, img_cv2, channel):
        import cv2
        img_rgb = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2RGB)
        return img_rgb[:, :, 1] if channel == "green" else img_rgb[:, :, 0]

    def count_cells_in_channel(self, channel_img, channel_name, original_rgb):
        """分水岭粘连分割 + 过滤计数"""
        import cv2
        intensity_threshold = self.green_thresh if channel_name == "green" else self.red_thresh
        _, binary = cv2.threshold(channel_img, intensity_threshold, 255, cv2.THRESH_BINARY)

        kernel = np.ones((self.kernel_size, self.kernel_size), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # 分水岭粘连分割
        sure_bg = cv2.dilate(binary, kernel, iterations=2)
        dist_transform = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
        _, sure_fg = cv2.threshold(dist_transform, self.split_thresh * dist_transform.max(), 255, 0)
        sure_fg = np.uint8(sure_fg)
        unknown = cv2.subtract(sure_bg, sure_fg)
        _, markers = cv2.connectedComponents(sure_fg)
        markers += 1
        markers[unknown == 255] = 0
        img_3ch = cv2.cvtColor(channel_img, cv2.COLOR_GRAY2BGR)
        markers = cv2.watershed(img_3ch, markers)
        binary_split = np.zeros_like(binary)
        binary_split[markers > 1] = 255

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary_split, connectivity=8)
        contours, _ = cv2.findContours(binary_split, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        R_channel = original_rgb[:, :, 0]
        G_channel = original_rgb[:, :, 1]

        valid_count = 0
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if not (self.min_size <= area <= self.max_size):
                continue
            if i - 1 < len(contours):
                perimeter = cv2.arcLength(contours[i - 1], True)
                if perimeter == 0:
                    continue
                roundness = 4 * np.pi * area / (perimeter ** 2)
                if roundness < self.min_roundness:
                    continue
            width = stats[i, cv2.CC_STAT_WIDTH]
            height = stats[i, cv2.CC_STAT_HEIGHT]
            aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 10
            if aspect_ratio > 3:
                continue
            # 串色校正
            mask = (labels == i).astype(np.uint8)
            avg_R = max(cv2.mean(R_channel, mask=mask)[0], 1)
            avg_G = max(cv2.mean(G_channel, mask=mask)[0], 1)
            if channel_name == "green":
                if avg_G / avg_R < self.min_channel_ratio:
                    continue
            elif channel_name == "red":
                if avg_R / avg_G < self.min_channel_ratio:
                    continue
            valid_count += 1
        return valid_count

    def count_live_dead(self, img_path):
        """统计单张图: 返回 {'green': n, 'red': n}"""
        import cv2
        img_bytes = np.fromfile(img_path, dtype=np.uint8)
        img_cv2 = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
        if img_cv2 is None:
            raise ValueError(f"无法读取图像: {img_path}")
        original_rgb = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2RGB)
        result = {"green": 0, "red": 0}
        result["green"] = self.count_cells_in_channel(
            self.extract_channel(img_cv2, "green"), "green", original_rgb)
        result["red"] = self.count_cells_in_channel(
            self.extract_channel(img_cv2, "red"), "red", original_rgb)
        return result


# ==================== 文件名解析 ====================
AREA_PATTERN = re.compile(r"^([0-9]+|c)[-_]?([rg])(\d+)$", re.IGNORECASE)


def parse_filename(fname):
    """解析 '1-r2' → (area='1', channel='r', num=2); 'c-g1' → (area='c', channel='g', num=1)"""
    stem = os.path.splitext(os.path.basename(fname))[0]
    m = AREA_PATTERN.match(stem.strip())
    if not m:
        return None
    area, channel, num = m.group(1).lower(), m.group(2).lower(), int(m.group(3))
    return area, channel, num


# ==================== 主分析器 ====================
class LiveDeadCellCounter:
    def __init__(self, engine=None, area_um2=None):
        self.engine = engine or CellCounterEngine()
        # 每张图对应面积 (µm²), 用于换算 CFU/cm²; 默认 None = 只输出计数
        self.area_um2 = area_um2

    def scan_structure(self, root, skip_repeats=()):
        """扫描 repeat 文件夹结构, 返回:
        {repeat: {time: [image_paths]}}
        skip_repeats: 跳过的 repeat 名 (如 ("repeat2",)), 用于数据不全/无效组
        """
        if not os.path.isdir(root):
            raise ValueError(f"输入不是文件夹: {root}")
        repeats = sorted(
            [d for d in os.listdir(root)
             if os.path.isdir(os.path.join(root, d)) and re.match(r"^repeat\s*\d+$", d, re.I)],
            key=lambda d: int(re.search(r"\d+", d).group()))
        if len(repeats) < 3:
            warnings.warn(f"只找到 {len(repeats)} 个 repeat 文件夹 (建议 ≥3), 继续处理")
        structure = {}
        for rep in repeats:
            rep_path = os.path.join(root, rep)
            times = {}
            for t_dir in sorted(os.listdir(rep_path)):
                t_path = os.path.join(rep_path, t_dir)
                if os.path.isdir(t_path) and re.search(r"\d+h$", t_dir, re.I):
                    imgs = [f for f in glob.glob(os.path.join(t_path, "*"))
                            if f.lower().endswith((".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"))
                            and parse_filename(os.path.basename(f))]
                    if imgs:
                        times[t_dir.lower()] = imgs
            if times:
                structure[rep] = times
        for r in skip_repeats:
            structure.pop(r, None)
        if not structure:
            raise ValueError(
                "未找到 repeat 文件夹结构。需要: 根目录/repeat1/1h/*.tif, "
                "文件名如 '1-r2.tif' (area-channel编号)")
        return structure

    def count_all(self, structure, verbose=True):
        """统计所有图片, 返回长表 DataFrame。

        配对逻辑: 荧光显微镜的 g 图和 r 图是同一视野的两个通道,
        文件名 {area}-g{n} 和 {area}-r{n} 配对:
          - g 图 → 数绿色通道 = 活菌 (live)
          - r 图 → 数红色通道 = 死菌 (dead)
        每对图贡献一个 live 计数和一个 dead 计数。

        返回: repeat, time, area, num, live, dead, total, dead_rate
        """
        rows = []
        total_pairs = 0
        for times in structure.values():
            for imgs in times.values():
                # 按 (area, num) 分组配对
                pairs = {}
                for img in imgs:
                    parsed = parse_filename(os.path.basename(img))
                    if not parsed:
                        continue
                    area, channel, num = parsed
                    key = (area, num)
                    pairs.setdefault(key, {})[channel] = img
                total_pairs += len(pairs)
        done = 0
        for rep, times in structure.items():
            for t, imgs in times.items():
                # 按 (area, num) 分组
                pairs = {}
                for img in imgs:
                    parsed = parse_filename(os.path.basename(img))
                    if not parsed:
                        continue
                    area, channel, num = parsed
                    key = (area, num)
                    pairs.setdefault(key, {})[channel] = img
                for (area, num), ch_imgs in pairs.items():
                    g_img = ch_imgs.get("g")
                    r_img = ch_imgs.get("r")
                    # 只数对应通道
                    try:
                        live = None
                        if g_img:
                            counts = self.engine.count_live_dead(g_img)
                            live = counts["green"]
                        dead = None
                        if r_img:
                            counts = self.engine.count_live_dead(r_img)
                            dead = counts["red"]
                        if live is None:
                            live = 0
                        if dead is None:
                            dead = 0
                        rows.append({
                            "repeat": rep, "time": t, "area": area, "num": num,
                            "g_image": os.path.basename(g_img) if g_img else "",
                            "r_image": os.path.basename(r_img) if r_img else "",
                            "live": live, "dead": dead,
                            "total": live + dead,
                        })
                    except Exception as e:
                        rows.append({
                            "repeat": rep, "time": t, "area": area, "num": num,
                            "g_image": os.path.basename(g_img) if g_img else "",
                            "r_image": os.path.basename(r_img) if r_img else "",
                            "live": np.nan, "dead": np.nan, "total": np.nan,
                            "error": str(e)[:50],
                        })
                    done += 1
                    if verbose and done % 20 == 0:
                        print(f"  进度: {done}/{total_pairs}")
        df = pd.DataFrame(rows)
        if df.empty:
            raise ValueError("没有成功统计任何图片对")
        df["dead_rate"] = df["dead"] / df["total"].replace(0, np.nan)
        return df

    def summarize(self, df):
        """按 area+time 汇总 (Control 的所有 repeat 合并):
        活菌/死菌/总数均值±标准差, 死亡率, n"""
        # area 标签: c→Control, 数字→Area n
        df = df.copy()
        df["area_label"] = df["area"].apply(
            lambda a: "Control" if a == "c" else f"Area {a}")
        groups = df.groupby(["area_label", "time"])
        summ = groups.agg(
            live_mean=("live", "mean"), live_sd=("live", "std"),
            dead_mean=("dead", "mean"), dead_sd=("dead", "std"),
            total_mean=("total", "mean"), total_sd=("total", "std"),
            dead_rate_mean=("dead_rate", "mean"),
            n=("live", "count"),
        ).reset_index()
        # 合并计数法存活率
        pooled = groups.apply(lambda d: pd.Series({
            "live_pooled": d["live"].sum(),
            "dead_pooled": d["dead"].sum(),
            "viability_pct": d["live"].sum() / d["total"].sum() * 100 if d["total"].sum() > 0 else np.nan,
        }), include_groups=False).reset_index()
        summ = summ.merge(pooled, on=["area_label", "time"])
        # NaN 标准差 → 0
        for c in ["live_sd", "dead_sd", "total_sd"]:
            summ[c] = summ[c].fillna(0)
        return summ

    def anova(self, df, value_col="live", log10=True):
        """双因素 ANOVA: value ~ area * time (合并计数, log10 转换可选)"""
        from scipy import stats
        df = df.copy()
        df["area_label"] = df["area"].apply(
            lambda a: "Control" if a == "c" else f"Area {a}")
        if log10:
            df["_val"] = np.log10(df[value_col].clip(lower=1) + 1)
        else:
            df["_val"] = df[value_col]
        groups = sorted(df["area_label"].unique())
        times = sorted(df["time"].unique())
        # 用 statsmodels 或手动双因素
        try:
            import statsmodels.api as sm
            from statsmodels.formula.api import ols
            model = ols("_val ~ C(area_label) * C(time)", data=df).fit()
            aov = sm.stats.anova_lm(model, typ=2)
            return aov.reset_index().rename(columns={"index": "factor"})
        except Exception:
            # 手动: 只做 area 单因素
            results = {}
            for t in times:
                sub = df[df["time"] == t]
                grps = [sub[sub["area_label"] == g]["_val"].dropna() for g in groups]
                grps = [g for g in grps if len(g) > 0]
                if len(grps) >= 2:
                    f, p = stats.f_oneway(*grps)
                    results[t] = {"F": f, "p": p}
            return pd.DataFrame(results).T.reset_index().rename(columns={"index": "time"})

    def plot(self, df, output_dir="output"):
        """柱状图: Control/Area1/Area2... × time, 活/死菌堆叠 + ANOVA 标注"""
        ensure_output_dir(output_dir)
        summ = self.summarize(df)
        areas = ["Control"] + [f"Area {i}" for i in sorted(
            {a for a in df["area"].unique() if a != "c"},
            key=lambda x: int(x))]
        times = sorted(summ["time"].unique())
        n_areas, n_times = len(areas), len(times)

        fig, ax = plt.subplots(figsize=(max(8, n_areas * n_times * 1.2), 5.5))
        width = 0.7 / n_times
        colors_live = "#00ba38"
        colors_dead = "#f8766d"

        x_positions = []
        for ai, area in enumerate(areas):
            for ti, t in enumerate(times):
                row = summ[(summ["area_label"] == area) & (summ["time"] == t)]
                if row.empty:
                    continue
                r = row.iloc[0]
                x = ai * (n_times + 0.5) + ti * width
                x_positions.append((x, area, t))
                # 死菌在下, 活菌在上 (堆叠)
                ax.bar(x, r["dead_mean"], width=width * 0.9, color=colors_dead,
                       edgecolor="black", linewidth=0.5)
                ax.bar(x, r["live_mean"], width=width * 0.9, bottom=r["dead_mean"],
                       color=colors_live, edgecolor="black", linewidth=0.5,
                       yerr=r["live_sd"], error_kw=dict(elinewidth=1, capsize=2))
                # 总数误差条
                ax.errorbar(x, r["dead_mean"] + r["live_mean"], yerr=r["total_sd"],
                            fmt="none", ecolor="black", elinewidth=1, capsize=3)

        # ANOVA 标注 (每个 area vs Control 的 Tukey p 值简化: 用单因素 p)
        try:
            aov = self.anova(df, value_col="live", log10=True)
            if "p" in aov.columns:
                p_first = aov["p"].iloc[0] if len(aov) else np.nan
                ax.text(0.5, 0.95,
                        f"Two-way ANOVA (log10): area p = {p_first:.2e}" if pd.notna(p_first) else "",
                        transform=ax.transAxes, ha="center", fontsize=10, fontstyle="italic")
        except Exception:
            pass

        # 坐标轴
        ax.set_xticks([ai * (n_times + 0.5) + (n_times - 1) * width / 2 for ai in range(n_areas)])
        ax.set_xticklabels(areas, fontsize=12)
        ax.set_xlabel("")
        ax.set_ylabel("Number of bacteria (per image)", fontsize=13)
        ax.set_title("LIVE/DEAD Fluorescence Counts", fontsize=14, fontweight="bold")
        ax.tick_params(direction="in")
        ax.legend(handles=[
            plt.Rectangle((0, 0), 1, 1, color=colors_live, label="Live (green)"),
            plt.Rectangle((0, 0), 1, 1, color=colors_dead, label="Dead (red)"),
        ], loc="upper right", frameon=False)
        plt.tight_layout()
        fig_path = save_figure(fig, f"{output_dir}/livedead_cell_count.png")
        plt.close(fig)
        return fig_path

    def report(self, root, output_dir="output", verbose=True, skip_repeats=()):
        """完整分析: 计数 → 汇总表 → 柱状图 → ANOVA
        skip_repeats: 跳过无效 repeat (如 ("repeat2",))"""
        ensure_output_dir(output_dir)
        structure = self.scan_structure(root, skip_repeats=skip_repeats)
        df = self.count_all(structure, verbose=verbose)
        # 保存原始计数
        raw_csv = save_csv(df, f"{output_dir}/livedead_raw_counts.csv")
        # 汇总表
        summ = self.summarize(df)
        summ_csv = save_csv(summ, f"{output_dir}/livedead_summary.csv")
        # ANOVA
        aov = self.anova(df)
        aov_csv = save_csv(aov, f"{output_dir}/livedead_anova.csv")
        # 图
        fig_path = self.plot(df, output_dir)
        return {
            "raw": df, "raw_csv": raw_csv,
            "summary": summ, "summary_csv": summ_csv,
            "anova": aov, "anova_csv": aov_csv,
            "figure": fig_path,
        }


def run(folder, output_dir="output", area_um2=None, backend="imagej",
        skip_repeats=(), **engine_kwargs):
    """一键 LIVE/DEAD 细胞计数分析

    backend: "imagej" (默认, 开源 ImageJ 引擎 — 自适应阈值+Analyze Particles,
             经典 ImageJ 1.54; 打包版用随包 imagej/, 源码运行自动探测本地安装) /
             "opencv" (旧的 Python 分水岭引擎, 仅保留作故障排查/回归对照,
             方法学上已被 ImageJ 取代)
    skip_repeats: 跳过无效 repeat (如 ("repeat2",))
    """
    if backend == "imagej":
        ij_kw = {k: engine_kwargs[k] for k in
                 ("imagej_dir", "min_size", "max_size", "bg_offset", "qc_dir")
                 if k in engine_kwargs}
        engine = ImageJEngine(**ij_kw)
    else:
        engine = CellCounterEngine(**engine_kwargs)
    analyzer = LiveDeadCellCounter(engine=engine, area_um2=area_um2)
    return analyzer.report(folder, output_dir, skip_repeats=skip_repeats)
