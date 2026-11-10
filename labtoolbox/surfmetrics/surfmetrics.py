# -*- coding: utf-8 -*-
"""
表面形貌参数模块: AFM/SEM 高度图 → 3D 图 + ISO 25178 粗糙度 (Sa/Sq/Sz) + 表面积 (Sdr)

支持格式:
  - .ibw  (Bruker/Igor AFM 原始数据, 直读; 自动读 ScanSize 校准 + 自动选 ZSR 通道)
          通道优先级: ZSensor Retrace (ZSR, 传感器原始信号 — 表面粗糙度分析用这个)
                      > Height Retrace (软件平滑过, 起伏被低估; 要旧口径用 channel="height")
          ZSR 默认走 2D 平面扣除 + 5σ 去尖峰 (未展平数据必需)
  - .tif/.tiff (高度图)
  - .txt/.csv/.xyz (纯高度矩阵 或 x,y,z 三列)

输出 (ISO 25178 面积参数):
  Sa   算术平均高度  (nm)
  Sq   均方根高度    (nm)
  Sz   最大峰谷差    (nm)
  Sdr  表面积增加率  (%)  = (真实表面积 - 投影面积)/投影面积 * 100
"""
import os
import re
import sys
import csv
import glob

import numpy as np


def load_heightmap(path, channel=None):
    """读取高度图. 返回 (z, px_hint, py_hint); px_hint=None 表示未知需手动指定

    channel 可以是索引, 也可以是名字 ("height" / "zsr") —— ZSR = ZSensor Retrace,
    表面粗糙度分析要求用这个通道 (Height Retrace 是被软件平滑过的)。
    """
    if isinstance(channel, str):
        channel = resolve_channel(path, channel)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".tif", ".tiff", ".png"):
        import tifffile
        z = tifffile.imread(path).astype(float)
        if z.ndim == 3:
            z = z[:, :, 0]
        return z, None, None
    if ext == ".ibw":  # Bruker/Igor binary wave — 直读 AFM 数据
        from igor import binarywave
        rec = binarywave.load(path)
        w = rec["wave"]
        data = np.array(w["wData"])
        labels = w.get("labels") or []
        flat = [l for grp in labels for l in (grp if isinstance(grp, list) else [grp])]
        names = [(l.decode("utf-8", errors="ignore") if isinstance(l, bytes) else str(l))
                 for l in flat if l]
        ch_sel = channel
        if data.ndim == 3:
            if ch_sel is None:
                # 通道优先级 (2026-09-15 导师定规): ZSensor Retrace (ZSR) > Height Retrace > 首个有数据
                # ZSR 是压电传感器原始反馈 (未滤波未展平), 表面粗糙度分析必须用它; Height 被软件平滑过,
                # 起伏会被系统性低估。要用旧口径: 显式给 channel="height" / --channel height。
                for want in ("zsensor", "height"):
                    for i, nm in enumerate(names):
                        if want in nm.lower():
                            ch_sel = i
                            break
                    if ch_sel is not None:
                        break
                if ch_sel is None:
                    stds = [float(data[:, :, i].std()) for i in range(data.shape[2])]
                    alive = [i for i, s in enumerate(stds) if s > 1e-9]
                    if alive:
                        ch_sel = alive[0]
                        print(f"⚠️  未找到高度通道, 使用首个有数据通道 "
                              f"{names[ch_sel] if ch_sel < len(names) else ch_sel} (非高度, 结果仅作形貌参考)")
                    else:
                        raise ValueError("所有通道均无数据")
            z = data[:, :, ch_sel].astype(float)
            nm = names[ch_sel] if ch_sel < len(names) else f"ch{ch_sel}"
            # Bruker .ibw 高度通道原始单位是"米" → 按量级自动转 nm
            sd = float(z.std())
            if 1e-12 < sd < 1e-4:
                z = z * 1e9
                print(f"    通道: {nm} (单位 m → 已转 nm, std={sd:.2e}m = {z.std():.2f}nm)")
            else:
                print(f"    通道: {nm} (std={sd:.2f}, 视为已用 nm 或相对单位)")
            if z.std() < 1e-3:
                raise ValueError(f"{nm} 通道转换后仍无有效高度数据")
        else:
            z = data.astype(float)
        note = (w.get("note") or b"").decode("utf-8", errors="ignore")
        m = re.search(r"ScanSize:\s*([0-9.eE+-]+)", note)
        px = py = None
        if m:
            scan_m = float(m.group(1))  # 米
            n = max(z.shape)
            px = py = scan_m * 1e9 / n  # nm/px
        return z, px, py
    data = np.loadtxt(path, ndmin=2)
    if data.shape[1] == 3:  # x,y,z 三列 → 转矩阵
        xs = np.unique(data[:, 0])
        ys = np.unique(data[:, 1])
        z = data[:, 2].reshape(len(ys), len(xs))
        return z, None, None
    return data, None, None  # 纯高度矩阵


def surface_metrics(z, px, py):
    """z: 高度矩阵 (nm), px/py: 像素尺寸 (nm). 返回 dict"""
    z = z.astype(float)
    zc = z - z.mean()
    Sa = float(np.abs(zc).mean())
    Sq = float(np.sqrt((zc ** 2).mean()))
    Sz = float(z.max() - z.min())
    # --- Sdr: 相邻像素三角剖分 (ISO 25178 标准做法) ---
    h, w = z.shape
    dz10 = z[1:, :-1] - z[:-1, :-1]  # 向右高度差
    dz01 = z[:-1, 1:] - z[:-1, :-1]  # 向下高度差
    dz11 = z[1:, 1:] - z[:-1, :-1]   # 对角高度差
    a1 = np.stack([np.full_like(dz10, px), np.zeros_like(dz10), dz10], -1)
    b1 = np.stack([np.full_like(dz11, px), np.full_like(dz11, py), dz11], -1)
    a2 = np.stack([np.zeros_like(dz01), np.full_like(dz01, py), dz01], -1)
    b2 = np.stack([np.full_like(dz11, px), np.full_like(dz11, py), dz11], -1)

    def tri_area(a, b):
        c = np.cross(a, b)
        return 0.5 * np.sqrt((c ** 2).sum(-1))

    S3d = float((tri_area(a1, b1) + tri_area(a2, b2)).sum())
    Sproj = (h - 1) * (w - 1) * px * py
    Sdr = (S3d / Sproj - 1.0) * 100.0
    return {"Sa_nm": Sa, "Sq_nm": Sq, "Sz_nm": Sz,
            "S3d_um2": S3d / 1e6, "Sproj_um2": Sproj / 1e6, "Sdr_pct": Sdr}


_CJK_READY = False


def _setup_cjk_font():
    """让图里的中文正常显示 (matplotlib 默认字体没有汉字 → 出豆腐块).

    字体候选/字体文件按平台定义在 labtoolbox.common.fonts (Windows 雅黑 /
    macOS PingFang / Linux Noto); 这里保留 surfmetrics 原有的幂等缓存语义.
    """
    global _CJK_READY
    if _CJK_READY:
        return
    try:
        from ..common.fonts import setup_matplotlib_cjk
        setup_matplotlib_cjk()
    except Exception:  # noqa: BLE001 - 字体只影响显示, 不能阻塞出图
        pass
    _CJK_READY = True


def _apply_z_ticks(ax, z, xr, yr, zr, k):
    """Set z ticks so the labels stay readable when the z direction is tiny on screen.

    In true-scale / slightly exaggerated views the z extent can be a few per cent of the XY
    extent, and matplotlib's default 5-6 tick labels then overlap into an unreadable smear.
    Returns True when the ticks were dropped (the colour bar carries the height scale).
    """
    ratio = (zr / 1000.0 * k) / max((xr + yr) / 2.0, 1e-9)
    if ratio < 0.10:
        ax.set_zticks([])
        return True
    if ratio < 0.5:
        ax.set_zticks(np.linspace(float(z.min()), float(z.max()), 3))
    return False


def _cbar(fig, surf, ax=None):
    """统一的 colorbar 样式: 刻度字号小一点、标签留白大一点 —— 否则 "Height (nm)" 会贴住刻度数字."""
    kw = {"ax": ax} if ax is not None else {}
    cb = fig.colorbar(surf, shrink=0.62, pad=0.06 if ax is None else 0.10, aspect=26, **kw)
    cb.set_label("Height (nm)", labelpad=12, fontsize=9.5)
    cb.ax.tick_params(labelsize=8.5, pad=2)
    return cb


def _z_scale_bar(ax, X, Y, z, label=True):
    """在 3D 图上画一条 z 标线 (尺子): 从高度 0 到最高点, 两端小钩 + 数值标注。

    为什么需要: z 与 XY 等比时 z 轴刻度会被隐藏 (`_apply_z_ticks`), 高度只剩 colorbar 可读,
    但 colorbar 给的是全域色标、不是"这图最高点多高"的绝对参照 —— 标线补的就是这把尺子。
    位置取**屏幕上最左**的角: 不同视角 (azim) 下 mpl 画 z 轴的位置会变, 用投影算而不是写死。
    画完把 zlim 复位, 保证标线不改变盒子的物理比例。
    """
    from mpl_toolkits.mplot3d import proj3d
    zmin, zmax = float(z.min()), float(z.max())
    z0, z1 = 0.0, zmax
    if z1 <= z0:                     # 全负/退化高度: 退回 min→max, 否则画不出东西
        z0, z1 = zmin, zmax
    x0, x1 = float(X.min()), float(X.max())
    y0, y1 = float(Y.min()), float(Y.max())
    M = ax.get_proj()
    corner, best = (x0, y0), float("inf")
    for cx, cy in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
        sx, _sy, _sz = proj3d.proj_transform(cx, cy, z1, M)
        if sx < best:
            best, corner = sx, (cx, cy)
    cx, cy = corner
    tick = 0.05 * (x1 - x0 + 1e-9)
    ax.plot([cx, cx], [cy, cy], [z0, z1], color="k", lw=1.8, zorder=20, solid_capstyle="butt")
    for zz in (z0, z1):
        ax.plot([cx - tick, cx + tick], [cy, cy], [zz, zz], color="k", lw=1.3, zorder=20)
    if label:
        ax.text(cx - tick * 1.7, cy, z0, "0", fontsize=8, ha="right", va="center", zorder=21)
        ax.text(cx - tick * 1.7, cy, z1, f"{z1:.0f} nm", fontsize=8, ha="right", va="center", zorder=21)
    ax.set_zlim(zmin, zmax)          # 标线不许改变盒子比例 / 视角
    return z0, z1


def plot3d(z, px, py, out, title=None, z_mode="real", z_bar=None):
    """Single-file 3D surface map. z: nm; px/py: nm per pixel.

    z_mode: "real" (default) = z axis on the same physical scale as XY, no vertical
            exaggeration; "auto" = z shown at ~25% of the XY extent (keeps shallow relief
            readable); a number = manual z magnification factor.
    z_bar:  z 标线 (0 → 最高高度). None=自动 (只在 z 刻度被隐藏时画, 免得和刻度重复);
            True=总是画; False=不画.
    """
    import matplotlib
    matplotlib.use("Agg")
    _setup_cjk_font()
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    h, w = z.shape
    xr = (w - 1) * px / 1000.0          # µm
    yr = (h - 1) * (py or px) / 1000.0  # µm
    zr = float(np.ptp(z))               # nm
    k = 1.0
    if z_mode == "auto":
        if zr > 0:
            k = max(0.25 * (xr + yr) / 2.0 / (zr / 1000.0), 1.0)
    elif z_mode == "real":
        k = 1.0
    else:
        k = float(z_mode)
    X, Y = np.meshgrid(np.arange(w) * px / 1000.0, np.arange(h) * (py or px) / 1000.0)
    m = surface_metrics(z, px, py or px)
    fig = plt.figure(figsize=(9, 6.5))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(X, Y, z, cmap="viridis", linewidth=0,
                           antialiased=True, rstride=1, cstride=1)
    # 横纵轴 (X/Y) 严格按物理尺寸比例 + z 按显示模式; z 数据轴保持真实 nm
    ax.set_box_aspect((xr, yr, zr / 1000.0 * k))
    ticks_hidden = _apply_z_ticks(ax, z, xr, yr, zr, k)
    # z 标线: 0 → 最高高度 (刻度被隐藏时读者仍能读出绝对高度) — 主人 2026-09-15 要求
    # z_bar=None 自动: 只在刻度被隐藏 (存在 colorbar 但 z 轴无数字) 时画, 免得和刻度重复
    if z_bar is None:
        z_bar = bool(ticks_hidden)
    if z_bar:
        _z_scale_bar(ax, X, Y, z)
    ax.set_xlabel("X (µm)", labelpad=13)
    ax.set_ylabel("Y (µm)", labelpad=13)
    ax.tick_params(labelsize=8.5, pad=1.5)
    # z 刻度隐藏时连 z 标签一起去掉: 否则它和 colorbar 的刻度数字、标签挤在同一片区域 (实测重叠)
    ax.set_zlabel("" if ticks_hidden else "Height (nm)", labelpad=8)
    t = title or (f"Sa={m['Sa_nm']:.2f} nm, Sq={m['Sq_nm']:.2f} nm, "
                  f"Sz={m['Sz_nm']:.1f} nm, Sdr={m['Sdr_pct']:.2f}%")
    t += ("  [z and XY at the same scale]" if abs(k - 1.0) < 1e-9
          else f"  [z x{k:.2g}]")
    if ticks_hidden:
        t += "  ·  height scale: see colour bar"
    ax.set_title(t, fontsize=10)
    _cbar(fig, surf)
    fig.tight_layout(pad=1.4)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def _norm_dir(deg):
    """Fold a ruler direction into [-90, 90) — a line has no sense of forward/backward."""
    return ((float(deg) + 90.0) % 180.0) - 90.0


def stripe_orientation(z, px, py, band_nm=None):
    """Dominant stripe (LIPSS-like) direction from the 2D FFT of the height map.

    A corrugated surface shows its periodicity along the direction PERPENDICULAR to the ridges,
    so the FFT peak direction is exactly the direction a profile line has to run to cross the
    ripples. ``band_nm=(lo, hi)`` keeps only peaks whose period is inside that window — needed
    for ZS(ZSR) data, where large-scale scan artefacts (µm-scale stripes) can outrank the real
    LIPSS peak; for a 515 nm laser the physical window is (0.5λ, 1.5λ) = (258, 772) nm.

    Returns:

        {"cross_deg":  ruler direction that crosses the ripples   (deg, CCW from +X, mod 180)
         "ridge_deg":  ridge (stripe) direction = cross_deg + 90
         "period_nm":  stripe period,
         "strength":   peak / median spectral magnitude — how stripe-like the surface is}
    """
    h, w = z.shape
    yy, xx = np.mgrid[0:h, 0:w]
    A = np.column_stack([xx.ravel() / max(w - 1, 1), yy.ravel() / max(h - 1, 1),
                         np.ones(h * w)])
    coef, *_ = np.linalg.lstsq(A, z.ravel(), rcond=None)             # drop the tilt first
    zp = z - (A @ coef).reshape(h, w)
    F = np.fft.fftshift(np.fft.fft2(zp * np.outer(np.hanning(h), np.hanning(w))))
    mag = np.abs(F)
    cy, cx = h // 2, w // 2
    mag[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3] = 0            # kill DC + neighbours
    mag[h // 2:, :] = 0                                              # one half plane (symmetric)
    med_ref = float(np.median(mag[mag > 0])) if (mag > 0).any() else 1.0   # 峰强基准取未掩蔽前的
    if band_nm:                                    # 只在物理上可能的周期带里找峰
        lo, hi = float(band_nm[0]), float(band_nm[1])
        fy_all = (np.arange(h)[:, None] - cy) / (h * py)
        fx_all = (np.arange(w)[None, :] - cx) / (w * px)
        with np.errstate(divide="ignore", invalid="ignore"):
            period = 1.0 / np.hypot(fx_all, fy_all)
        mag = np.where((period >= lo) & (period <= hi), mag, 0.0)
        if not mag.any():
            raise ValueError(f"带宽 {band_nm} nm 内没有可用的 FFT 峰")
    py2, px2 = np.unravel_index(int(np.argmax(mag)), mag.shape)
    med = med_ref                                          # 峰强 = 峰 / 全谱中位 (可与无带结果比)
    fx = (px2 - cx) / (w * px)          # cycles/nm along X
    fy = (py2 - cy) / (h * py)          # cycles/nm along Y
    f = float(np.hypot(fx, fy))
    ang = float(np.degrees(np.arctan2(fy, fx)))      # periodicity direction in the XY plane
    return {"cross_deg": _norm_dir(ang),
            "ridge_deg": _norm_dir(ang + 90.0),
            "period_nm": (1.0 / f) if f > 0 else float("nan"),
            "strength": float(mag[py2, px2]) / (med or 1.0)}


def _sample_line(z, px, py, spec):
    """Sample the height map along one reference line.

    spec = {"kind": "row", "pos": <pixel row>}         ruler along X at that row
           {"kind": "col", "pos": <pixel column>}      ruler along Y at that column
           {"kind": "angle", "deg": <deg CCW from +X>} ruler through the image centre

    Returns (dist_um, height_nm, x_um, y_um): distance along the ruler measured from its start,
    the height profile, and the ruler's coordinates on the surface (for the 3D overlay).
    """
    h, w = z.shape
    kind = (spec or {}).get("kind", "row")
    if kind == "row":
        r = max(0, min(h - 1, int(spec.get("pos", h // 2))))
        i = np.arange(w)
        x = i * px / 1000.0
        y = np.full(w, r * py / 1000.0)
        return x - x[0], z[r, :].astype(float), x, y
    if kind == "col":
        c = max(0, min(w - 1, int(spec.get("pos", w // 2))))
        j = np.arange(h)
        x = np.full(h, c * px / 1000.0)
        y = j * py / 1000.0
        return y - y[0], z[:, c].astype(float), x, y

    th = np.radians(float(spec.get("deg", 0.0)))
    xc, yc = (w - 1) * px / 2000.0, (h - 1) * py / 2000.0       # centre, µm
    dx, dy = np.cos(th), np.sin(th)
    lim = []
    for d, c, hi in ((dx, xc, (w - 1) * px / 1000.0), (dy, yc, (h - 1) * py / 1000.0)):
        if abs(d) < 1e-12:
            continue
        lim.append(((hi - c) / d) if d > 0 else ((0.0 - c) / d))
    L = max(0.0, (min(lim) if lim else 0.0) - 0.02 * min((w - 1) * px, (h - 1) * py) / 1000.0)
    step = max(min(px, py) / 1000.0, 1e-6)
    n = int(max(2, min(4000, round(2 * L / step))))             # ~one sample per pixel
    t = np.linspace(-L, L, n)
    xs, ys = xc + t * dx, yc + t * dy
    fi = np.clip(xs * 1000.0 / px, 0, w - 1.001)
    fj = np.clip(ys * 1000.0 / py, 0, h - 1.001)
    i0, j0 = fi.astype(int), fj.astype(int)
    i1, j1 = i0 + 1, j0 + 1
    wi, wj = fi - i0, fj - j0
    hgt = ((1 - wi) * (1 - wj) * z[j0, i0] + wi * (1 - wj) * z[j0, i1]
           + (1 - wi) * wj * z[j1, i0] + wi * wj * z[j1, i1])
    return t - t[0], hgt.astype(float), xs, ys


def plot_profiles(z, px, py, out, row=None, col=None, title=None, z_mode="real", lines=None,
                  z_bar=None):
    """Reference-line profile figure (English only).

    Left  = 3D topography at true z/XY scale with the reference line(s) drawn on the surface and
            labelled with their orientation and position; plus a z scale bar (0 → max).
    Right = depth profiles measured along those same lines, in matching colours.

    lines=None reproduces the classic two-line figure (H-line along X + V-line along Y, through
    the centre or through ``row``/``col``). Pass ``lines`` to choose the rulers explicitly:

        [{"kind": "angle", "deg": 78.0}]                             # ONE ruler crossing the
                                                                     # ripples (LIPSS)
        [{"kind": "row", "pos": 256}, {"kind": "col", "pos": 256}]   # H + V (isotropic / NP)

    A line is the ruler: peak-to-valley amplitude and the periodicity of a surface are only
    measurable along a profile, while the 3D view shows the overall morphology.

    z_bar: z 标线 (0 → 最高高度, 只标这两个数 —— 主人 2026-09-15 指定);
           None=自动 (z 刻度被隐藏时才画) / True=总是画 / False=不画.
    """
    import matplotlib
    matplotlib.use("Agg")
    _setup_cjk_font()
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    h, w = z.shape
    pyv = py or px
    xr = (w - 1) * px / 1000.0          # µm
    yr = (h - 1) * pyv / 1000.0         # µm
    zr = float(np.ptp(z))               # nm
    k = 1.0
    if z_mode == "auto":
        if zr > 0:
            k = max(0.25 * (xr + yr) / 2.0 / (zr / 1000.0), 1.0)
    elif z_mode != "real":
        k = float(z_mode)
    X, Y = np.meshgrid(np.arange(w) * px / 1000.0, np.arange(h) * pyv / 1000.0)
    m = surface_metrics(z, px, pyv)

    if lines is None:
        r = h // 2 if row is None else max(0, min(h - 1, int(row)))
        c = w // 2 if col is None else max(0, min(w - 1, int(col)))
        lines = [{"kind": "row", "pos": r, "label": f"H-line (along X)\n Y = {r * pyv / 1000.0:.2f} µm"},
                 {"kind": "col", "pos": c, "label": f"V-line (along Y)\n X = {c * px / 1000.0:.2f} µm"}]
    PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]

    fig = plt.figure(figsize=(13.5, 5.4))
    ax = fig.add_subplot(1, 2, 1, projection="3d")
    surf = ax.plot_surface(X, Y, z, cmap="viridis", linewidth=0,
                           antialiased=True, rstride=1, cstride=1)
    lift = max(zr, 1e-9) * 0.04      # lift the rulers off the surface so the relief hides nothing
    profiles = []
    for n, spec in enumerate(lines):
        dist, hgt, xs, ys = _sample_line(z, px, pyv, spec)
        col_ = PALETTE[n % len(PALETTE)]
        ax.plot(xs, ys, hgt + lift, color=col_, ls="--", lw=1.7)
        ax.text(xs[0], ys[0], hgt[0] + lift, " " + spec.get("label", f"line {n + 1}"),
                color=col_, fontsize=7.5, zorder=10,
                bbox=dict(boxstyle="round,pad=0.18", facecolor="white", alpha=0.55,
                          edgecolor="none"))
        profiles.append((col_, spec.get("label", f"line {n + 1}").replace("\n", "   "), dist, hgt))
    ax.set_box_aspect((xr, yr, zr / 1000.0 * k))
    ticks_hidden = _apply_z_ticks(ax, z, xr, yr, zr, k)
    ax.set_xlabel("X (µm)", labelpad=10)
    ax.set_ylabel("Y (µm)", labelpad=10)
    ax.set_zlabel("" if ticks_hidden else "Height (nm)", labelpad=8)
    scale_tag = "z and XY at the same scale" if abs(k - 1.0) < 1e-9 else f"z x{k:.3g}"
    if ticks_hidden:
        scale_tag += "  ·  height scale: see colour bar"
    ax.set_title(f"{title or '3D surface'}   [{scale_tag}]", fontsize=10)
    ax.view_init(elev=42, azim=-60)
    # z 标线 (0 → 最高高度, 只标 0 与最大值) —— 必须放在 view_init **之后**:
    # 标线位置按投影算"屏幕上最左的角", 视角没定就会按默认视角选角 → 换个视角标线跑到图外
    if z_bar is None:
        z_bar = bool(ticks_hidden)
    if z_bar:
        _z_scale_bar(ax, X, Y, z)
    _cbar(fig, surf, ax=ax)

    ax2 = fig.add_subplot(1, 2, 2)
    for col_, label, dist, hgt in profiles:
        ax2.plot(dist, hgt, color=col_, lw=1.3, label=label)
        ax2.axhline(float(hgt.mean()), color=col_, lw=0.6, ls=":", alpha=0.55)
    ax2.set_xlabel("Distance (µm)", labelpad=8)
    ax2.set_ylabel("Height (nm)", labelpad=8)
    pv = "   |   ".join(f"{lbl.split('   ')[0]} P-V {np.ptp(hgt):.1f} nm"
                        for _c, lbl, _d, hgt in profiles)
    # 标题分两行 + 图例移到绘图区上方: 长标题不再压到左边 colorbar, 图例也不盖曲线 (两处实测重叠)
    ax2.set_title(f"Depth profile   |   Sa = {m['Sa_nm']:.2f} nm   |   {pv}", fontsize=10)
    ax2.grid(alpha=0.25)
    # 图例放到坐标区下方: 上方留给标题与跑分, 曲线不被遮, 图例也不与标题打架 (三处都实测过)
    ax2.legend(fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.14),
               ncol=min(2, max(1, len(profiles))), frameon=False, handlelength=1.6,
               columnspacing=1.2, borderaxespad=0.0)

    fig.tight_layout(pad=1.4)
    fig.subplots_adjust(wspace=0.30, bottom=0.24)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def profile_lines_for(z, px, py, mode="hv", stripe_angle=None, row=None, col=None,
                      stripe_band=None):
    """Decide which ruler(s) a figure gets, and describe them.

    mode: "hv"    = H-line + V-line (isotropic surfaces, nanopillar grids)
          "cross" = ONE line crossing the ripples (LIPSS) — direction from the 2D FFT,
                    or from ``stripe_angle`` when given
          "auto"  = "cross" when the surface really is corrugated (FFT peak stands out),
                    otherwise "hv"
    stripe_band: (lo, hi) nm — 只在该周期带内找条纹峰 (ZS/ZSR 数据必给, 否则会被 µm 级扫描伪影带偏)
    Returns (lines, info) — info carries the detected direction/period for the CSV/report.
    """
    info = {"profile_mode": mode, "stripe_cross_deg": None, "stripe_ridge_deg": None,
            "stripe_period_nm": None, "stripe_strength": None, "line_count": 0,
            "stripe_band_nm": list(stripe_band) if isinstance(stripe_band, (tuple, list)) else None}
    if mode in ("cross", "auto"):
        st = stripe_orientation(z, px, py, band_nm=stripe_band)
        info.update({"stripe_cross_deg": st["cross_deg"], "stripe_ridge_deg": st["ridge_deg"],
                     "stripe_period_nm": st["period_nm"], "stripe_strength": st["strength"]})
        use_cross = True if mode == "cross" else st["strength"] >= 8.0
        if use_cross:
            # 主人 2026-09-15: LIPSS 参考线角度**固定 90°** (沿 Y 走 = 正跨条纹), 不再用 FFT 角度;
            # 图上也不再显示 θ (标注只留 "Ruler across the ripples")。
            # FFT 量到的角度/周期仍写进 CSV (stripe_cross_deg / stripe_period_nm) 供追溯;
            # 显式传 stripe_angle 时仍以它为准 (probe 脚本的逃生口)
            deg = float(stripe_angle) if stripe_angle is not None else 90.0
            info["profile_mode"] = "cross"
            info["line_count"] = 1
            lbl = "Ruler across the ripples"
            return [{"kind": "angle", "deg": deg, "label": lbl}], info
        info["profile_mode"] = "hv"
    r = z.shape[0] // 2 if row is None else max(0, min(z.shape[0] - 1, int(row)))
    c = z.shape[1] // 2 if col is None else max(0, min(z.shape[1] - 1, int(col)))
    info["line_count"] = 2
    return [{"kind": "row", "pos": r, "label": f"H-line (along X)\n Y = {r * (py or px) / 1000.0:.2f} µm"},
            {"kind": "col", "pos": c, "label": f"V-line (along Y)\n X = {c * px / 1000.0:.2f} µm"}], info

def plot_grid(files_data, out, title=None, z_mode="auto"):
    """多文件 3D 网格图 (≤9 个); XY 等比例, z_mode 同 plot3d"""
    import matplotlib
    matplotlib.use("Agg")
    _setup_cjk_font()
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    n = len(files_data)
    cols = 3 if n > 4 else (2 if n > 1 else 1)
    rows = int(np.ceil(n / cols))
    fig = plt.figure(figsize=(6 * cols, 5 * rows))
    for idx, (name, z, px, m) in enumerate(files_data):
        ax = fig.add_subplot(rows, cols, idx + 1, projection="3d")
        h, w = z.shape
        py = px  # 网格数据统一按 px (方形扫描); 非方形用 px 近似
        xr = (w - 1) * px / 1000.0
        yr = (h - 1) * py / 1000.0
        zr = float(np.ptp(z))
        k = 1.0
        if z_mode == "auto":
            if zr > 0:
                k = max(0.25 * (xr + yr) / 2.0 / (zr / 1000.0), 1.0)
        elif z_mode != "real":
            k = float(z_mode)
        X, Y = np.meshgrid(np.arange(w) * px / 1000.0, np.arange(h) * py / 1000.0)
        surf = ax.plot_surface(X, Y, z, cmap="viridis", linewidth=0,
                               antialiased=True, rstride=1, cstride=1)
        ax.set_box_aspect((xr, yr, zr / 1000.0 * k))
        hidden = _apply_z_ticks(ax, z, xr, yr, zr, k)      # 网格每格也要收 z 刻度, 否则一排数字互叠
        ax.set_title("{}\\nSa={:.2f} nm | Sq={:.2f} nm | Sdr={:.2f}%".format(
            name, m['Sa_nm'], m['Sq_nm'], m['Sdr_pct']), fontsize=8, linespacing=1.35)
        ax.set_xlabel("µm", labelpad=1)
        ax.set_ylabel("µm", labelpad=1)
        ax.set_zlabel("" if hidden else "nm", labelpad=1)
        ax.tick_params(labelsize=6, pad=0.5)
    if title:
        fig.suptitle(title, fontsize=13)
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def _win2wsl(path):
    """Windows 路径 F:\\x\\y → WSL /mnt/f/x/y"""
    p = path.replace("\\", "/")
    drive = p[0].lower()
    return "/mnt/" + drive + p[2:]


def gwy_batch_wsl(paths, level=True, channel=None, timeout=600):
    """调 WSL Gwyddion 内核批处理 (pygwy)。返回 [{file, channel, mean_nm,
    Sa_nm, Sq_nm, Sz_nm, skew, kurt}]. 依赖: WSL Ubuntu + /usr/local/bin/gwy_batch.py
    (见 labtoolbox 技能 references/gwyddion-pygwy-wsl-batch.md)
    """
    import subprocess, tempfile, csv as _csv
    # gwy_batch.py 收单文件/目录 → 逐文件循环 (每次 ~2-4s JVM/模块启动)
    rows = []
    for p in paths:
        wp = _win2wsl(os.path.abspath(p))
        fd, tmp = tempfile.mkstemp(suffix=".csv", prefix="gwy_")
        os.close(fd)
        tmp_win = tmp.replace("\\", "/")
        tmp_wsl = _win2wsl(tmp_win)   # C:/... → /mnt/c/...
        cmd = ["wsl", "-d", "Ubuntu", "-u", "root", "--", "bash", "-lc",
               "/usr/local/bin/gwy_batch.py '%s' %s %s -o '%s' 2>/dev/null"
               % (wp, "--level" if level else "--raw",
                  ("--channel %d" % channel) if channel is not None else "",
                  "/root/" + os.path.basename(tmp))]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout, env=dict(os.environ))
        # 拷回 Windows 临时路径 (WSL 侧须用 /mnt/... 路径)
        subprocess.run(["wsl", "-d", "Ubuntu", "-u", "root", "--", "bash", "-lc",
                        "cp '/root/%s' '%s'" % (os.path.basename(tmp), tmp_wsl)],
                       capture_output=True, timeout=60)
        if os.path.exists(tmp):
            with open(tmp, encoding="utf-8") as f:
                for r in _csv.DictReader(f):
                    rows.append({
                        "file": r["file"], "channel": r["channel"],
                        "mean_nm": float(r["mean_nm"]), "Sa_nm": float(r["Sa_nm"]),
                        "Sq_nm": float(r["Sq_nm"]), "Sz_nm": float(r["Sz_nm"]),
                        "skew": float(r["skew"]), "kurt": float(r["kurt"]),
                    })
            os.unlink(tmp)
        if not rows or rows[-1].get("file") != os.path.basename(p):
            raise RuntimeError("gwy_batch 无输出: %s (err: %s)"
                               % (p, ((proc.stderr or "") + (proc.stdout or ""))[-300:]))
    return rows


def _profile_cells(r):
    """参考线/条纹那几列 (CSV 用): mode / 线条数 / 跨纹方向 / 条纹走向 / 周期 / 峰强"""
    def fmt(key, nd):
        v = r.get(key)
        return f"{v:.{nd}f}" if isinstance(v, (int, float)) and v == v else ""
    return [r.get("profile_mode") or "",
            r.get("line_count") if r.get("line_count") else "",
            fmt("stripe_cross_deg", 2), fmt("stripe_ridge_deg", 2),
            fmt("stripe_period_nm", 1), fmt("stripe_strength", 2)]


def channel_names(path):
    """通道名列表 (labels 优先, 空则退回 wave_note 的 ChannelNDataType)."""
    ext = os.path.splitext(path)[1].lower()
    if ext != ".ibw":
        return []
    from igor import binarywave
    w = binarywave.load(path)["wave"]
    labels = w.get("labels") or []
    flat = [l for grp in labels for l in (grp if isinstance(grp, list) else [grp])]
    names = [(l.decode("utf-8", "ignore") if isinstance(l, bytes) else str(l)).strip()
             for l in flat if l]
    if not any(names):
        note = w.get("note") or b""
        if isinstance(note, bytes):
            note = note.decode("utf-8", "ignore")
        names = [d for _i, d in re.findall(r"Channel(\d+)DataType:\s*([A-Za-z]+)", note)]
    return names


def resolve_channel(path, want):
    """把通道名/别名换成索引. want: "height" / "zsr"/"zsensor" / 索引(int 直接返回).

    ZSR = ZSensor Retrace (压电传感器原始反馈, 未滤波未展平) —— 表面粗糙度分析要求用这个通道,
    而不是软件处理过的 Height Retrace (后者已被平滑, 起伏会被低估)。labels 常为空, 所以
    channel_names() 会退回 wave_note 的 ChannelNDataType 表。
    """
    if want is None or isinstance(want, int):
        return want
    key = str(want).strip().lower()
    alias = {"zsr": "zsensor", "zsensor": "zsensor", "zs": "zsensor",
             "zsensorretrace": "zsensor", "height": "height",
             "heightretrace": "height"}
    key = alias.get(key, key)
    names = [n.lower() for n in channel_names(path)]
    for i, n in enumerate(names):
        if key in n:
            return i
    raise ValueError(f"{os.path.basename(path)}: 找不到通道 {want!r} (实际通道: {names})")


def plane_subtract(z):
    """最小二乘拟合 z = a·x + b·y + c 并减去 —— 未展平的 ZS 数据必需 (只减均值不够)."""
    h, w = z.shape
    yy, xx = np.mgrid[0:h, 0:w]
    A = np.column_stack([xx.ravel() / max(w - 1, 1), yy.ravel() / max(h - 1, 1), np.ones(h * w)])
    coef, *_ = np.linalg.lstsq(A, z.ravel(), rcond=None)
    return z - (A @ coef).reshape(h, w)


def despike_z(z, k=5.0, iters=3, size=3):
    """5σ 中值滤波去单点/小面积尖峰 (探针粘附/灰尘). 返回 (去尖峰后的 z, 被替换像素数).

    只治单点尖峰: 大块凸起 (数百像素宽的真实颗粒/夹杂) 识别不了, 会留在数据里 ——
    那种要靠人工 QC 判断是否剔除, 别指望这个滤镜。
    """
    from scipy import ndimage
    out = np.array(z, dtype=float)
    replaced = 0
    for _ in range(int(iters)):
        med = ndimage.median_filter(out, size=size, mode="nearest")
        resid = out - med
        s = float(resid.std())
        if s <= 0:
            break
        mask = np.abs(resid) > k * s
        n = int(mask.sum())
        if not n:
            break
        out[mask] = med[mask]
        replaced += n
    return out, replaced


def run(file=None, folder=None, channel=None, px=None, py=None, output_dir="output",
        z_mode="real", backend="python", level=True,
        profiles=True, profile_row=None, profile_col=None,
        profile_mode="hv", stripe_angle=None, stripe_band=None,
        plane=None, despike=None):
    """统一入口 (CLI/GUI 调用).

    file: 单个高度图文件 (或一组文件的 list); folder: 批量处理文件夹内所有 .ibw
    z_mode: 3D 图 z 轴显示模式 — "real" (默认, z 与 XY 同比例, 不做纵向夸张) /
            "auto" (z 显示为 xy 平均尺度的 ~25%, 起伏扁平时看得清楚) / 数值放大系数
    profiles: 是否额外输出"参考线剖面图" (左 3D 等比例 + 参考线虚线, 右 沿线的深度曲线);
              profile_row/profile_col 指定参考线所在的像素行列 (默认取正中)
    profile_mode: 参考线怎么画 — "hv" (默认, 横+纵两条: 各向同性面/纳米柱网格) /
              "cross" (只一条, 方向由 2D FFT 定, 横跨条纹: LIPSS) / "auto" (周期性明显才用单条)
    stripe_angle: 手动指定跨纹线方向 (度, 相对 +X), 不填则由 FFT 自动判
    stripe_band: (lo, hi) nm — 条纹周期搜索带 (ZS/ZSR 通道 + LIPSS 时给 (0.5λ, 1.5λ))
    channel: 通道索引, 或名字 — "height" / "zsr"(= ZSensor Retrace). AFM 表面粗糙度分析
             要求用 ZSR (传感器原始信号), 不要用被软件平滑过的 Height Retrace
    plane/despike: 出图用的 z 先做 2D 平面扣除 / 5σ 中值去尖峰。默认 None = 随通道自动:
              选到 ZSR 就开 (未展平必需), 选到 Height 就关; 显式 True/False 可强制
    backend: "python" (默认, 自研算法) / "gwyddion" (WSL Gwyddion 2.67 内核,
             真·Gwyddion 平面扣除+统计; level=True 时先平面扣除)
    返回 dict: {"results": [...], "csv": path, "figures": [...], "grid": path|None}
    """
    from labtoolbox.common.io_utils import ensure_output_dir
    out = ensure_output_dir(output_dir)
    paths = []
    if folder:
        paths = sorted(glob.glob(os.path.join(folder, "*.ibw")))
        if not paths:
            paths = sorted(glob.glob(os.path.join(folder, "*.tif")))
        if not paths:
            raise FileNotFoundError(f"文件夹内未找到 .ibw/.tif 文件: {folder}")
    elif file:
        paths = list(file) if isinstance(file, (list, tuple)) else [file]
    else:
        raise ValueError("必须提供 file 或 folder")
    if not paths:
        raise FileNotFoundError("未找到输入文件")

    names0 = channel_names(paths[0]) if paths else []
    zs_idx = next((i for i, n in enumerate(names0) if "zsensor" in n.lower()), None)
    ch_int = channel
    if isinstance(channel, str):
        resolved = {resolve_channel(p, channel) for p in paths}
        if len(resolved) != 1:
            raise ValueError(f"通道 {channel!r} 在不同文件里的索引不一致: {sorted(resolved)}")
        ch_int = resolved.pop()
        print(f"  通道: {channel} → 索引 {ch_int} ({channel_names(paths[0])})")

    if ch_int is None and zs_idx is not None:
        ch_int = zs_idx          # 自动 = ZSR, 显式传给 Gwyddion 内核 (否则它会自己去挑 Height)
        print(f"  自动选通道 → ZSR 索引 {zs_idx} ({names0[zs_idx] if zs_idx < len(names0) else ''})")
    # ZSR (未滤波未展平) 默认走 2D 平面扣除 + 去尖峰; 显式 True/False 覆盖
    auto_zs = (ch_int == zs_idx) if ch_int is not None else (zs_idx is not None)
    if plane is None:
        plane = auto_zs
    if despike is None:
        despike = auto_zs
    if auto_zs:
        print(f"  ZSR 通道 (索引 {zs_idx}) → 平面扣除={plane} 去尖峰={despike}")

    results, figures, grid_data = [], [], []
    if backend == "gwyddion":
        # ---- Gwyddion 内核后端: 数值来自真·Gwyddion (level + 统计) ----
        gwy_rows = gwy_batch_wsl(paths, level=level, channel=ch_int)
        gwy_by_file = {r["file"]: r for r in gwy_rows}
        for p in paths:
            name = os.path.splitext(os.path.basename(p))[0]
            g = gwy_by_file.get(os.path.basename(p), {})
            z, px_h, py_h = load_heightmap(p, channel=ch_int)
            if plane:
                z = plane_subtract(z)
            if despike:
                z, _n_spk = despike_z(z)
            pxf = px if px is not None else px_h          # 每份文件各自的像素尺寸
            pyf = py if py is not None else (py_h or pxf)
            m_py = surface_metrics(z, pxf, pyf or pxf) if pxf else None
            results.append({
                "file": name, "path": p, "backend": "gwyddion",
                "level": bool(level),
                "Sa_nm": g.get("Sa_nm"), "Sq_nm": g.get("Sq_nm"),
                "Sz_nm": g.get("Sz_nm"), "skew": g.get("skew"),
                "kurt": g.get("kurt"),
                "S3d_um2": m_py["S3d_um2"] if m_py else None,
                "Sproj_um2": m_py["Sproj_um2"] if m_py else None,
                "Sdr_pct": m_py["Sdr_pct"] if m_py else None,
            })
            if pxf:
                fig_p = os.path.join(out, f"{name}_3D.png")
                src_tag = "(Gwyddion level)" if level else "(Gwyddion raw)"
                plot3d(z, pxf, pyf or pxf, fig_p, z_mode=z_mode,
                       title=f"{name}  3D surface  {src_tag}")
                figures.append(fig_p)
                if profiles:
                    fig_pr = os.path.join(out, f"{name}_profile.png")
                    _lines, _pinfo = profile_lines_for(z, pxf, pyf or pxf, profile_mode,
                                                       stripe_angle=stripe_angle,
                                                       row=profile_row, col=profile_col,
                                                       stripe_band=stripe_band)
                    plot_profiles(z, pxf, pyf or pxf, fig_pr, title=name, z_mode=z_mode,
                                  lines=_lines)
                    figures.append(fig_pr)
                    results[-1].update(_pinfo)
                grid_data.append((name, z, pxf, {
                    "Sa_nm": g.get("Sa_nm"), "Sq_nm": g.get("Sq_nm"),
                    "Sdr_pct": m_py["Sdr_pct"] if m_py else 0.0}))
            print(f"  {name}: Sa={g.get('Sa_nm')} nm, Sq={g.get('Sq_nm')} nm, "
                  f"Sz={g.get('Sz_nm')} nm  [Gwyddion kernel]")
        csv_path = os.path.join(out, "surface_metrics_summary.csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            wtr = csv.writer(f)
            wtr.writerow(["file", "backend", "level", "Sa_nm", "Sq_nm", "Sz_nm",
                          "skew", "kurt", "S3d_um2", "Sproj_um2", "Sdr_pct",
                          "profile_mode", "n_lines", "stripe_cross_deg", "stripe_ridge_deg",
                          "stripe_period_nm", "stripe_strength"])
            for r in results:
                wtr.writerow([r["file"], r["backend"], r["level"],
                              f"{r['Sa_nm']:.4f}" if r["Sa_nm"] is not None else "",
                              f"{r['Sq_nm']:.4f}" if r["Sq_nm"] is not None else "",
                              f"{r['Sz_nm']:.4f}" if r["Sz_nm"] is not None else "",
                              f"{r['skew']:.4f}" if r.get("skew") is not None else "",
                              f"{r['kurt']:.4f}" if r.get("kurt") is not None else "",
                              f"{r['S3d_um2']:.4f}" if r["S3d_um2"] is not None else "",
                              f"{r['Sproj_um2']:.4f}" if r["Sproj_um2"] is not None else "",
                              f"{r['Sdr_pct']:.4f}" if r["Sdr_pct"] is not None else ""]
                             + _profile_cells(r))
        grid_path = None
        if len(grid_data) > 1:
            grid_path = os.path.join(out, "all_3D_grid.png")
            plot_grid(grid_data, grid_path, title="AFM surface analysis (3D)",
                      z_mode=z_mode)
        return {"results": results, "csv": csv_path, "figures": figures,
                "grid": grid_path}

    # ---- Python 自研后端 (原逻辑) ----
    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        z, px_h, py_h = load_heightmap(p, channel=ch_int)
        if plane:
            z = plane_subtract(z)
        if despike:
            z, _n_spk = despike_z(z)
        pxf = px if px is not None else px_h          # 每份文件各自的像素尺寸
        pyf = py if py is not None else (py_h or pxf)
        if pxf is None:
            raise ValueError(f"像素尺寸未知: {name} — 请用 --px/px 指定 (nm)")
        m = surface_metrics(z, pxf, pyf or pxf)
        results.append({"file": name, "path": p, **m})
        fig_p = os.path.join(out, f"{name}_3D.png")
        plot3d(z, pxf, pyf or pxf, fig_p, title=f"{name}  3D surface", z_mode=z_mode)
        figures.append(fig_p)
        if profiles:
            fig_pr = os.path.join(out, f"{name}_profile.png")
            _lines, _pinfo = profile_lines_for(z, pxf, pyf or pxf, profile_mode,
                                               stripe_angle=stripe_angle,
                                               row=profile_row, col=profile_col,
                                               stripe_band=stripe_band)
            plot_profiles(z, pxf, pyf or pxf, fig_pr, title=name, z_mode=z_mode, lines=_lines)
            figures.append(fig_pr)
            results[-1].update(_pinfo)
        grid_data.append((name, z, pxf, m))
        print(f"  {name}: Sa={m['Sa_nm']:.2f} nm, Sq={m['Sq_nm']:.2f} nm, "
              f"Sz={m['Sz_nm']:.1f} nm, Sdr={m['Sdr_pct']:.3f}%")

    csv_path = os.path.join(out, "surface_metrics_summary.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        wtr = csv.writer(f)
        wtr.writerow(["file", "Sa_nm", "Sq_nm", "Sz_nm", "S3d_um2", "Sproj_um2", "Sdr_pct",
                      "profile_mode", "n_lines", "stripe_cross_deg", "stripe_ridge_deg",
                      "stripe_period_nm", "stripe_strength"])
        for r in results:
            wtr.writerow([r["file"], f"{r['Sa_nm']:.4f}", f"{r['Sq_nm']:.4f}",
                          f"{r['Sz_nm']:.4f}", f"{r['S3d_um2']:.4f}",
                          f"{r['Sproj_um2']:.4f}", f"{r['Sdr_pct']:.4f}"]
                         + _profile_cells(r))

    grid_path = None
    if len(grid_data) > 1:
        grid_path = os.path.join(out, "all_3D_grid.png")
        plot_grid(grid_data, grid_path, title="AFM surface analysis (3D)", z_mode=z_mode)
    return {"results": results, "csv": csv_path, "figures": figures, "grid": grid_path}
