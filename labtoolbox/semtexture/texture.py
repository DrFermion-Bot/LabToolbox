# -*- coding: utf-8 -*-
"""SEM texture-uniformity / processing-consistency analyser.

Purpose
-------
Quantify how repeatable a laser-texturing process is **across coupons**: for a folder
of SEM images (one or more fields per coupon) it returns, per coupon and per batch,

* the ripple period  Λ  (nm)                — autocorrelation of the profile taken
                                              along the ripple normal, cross-checked
                                              against the 1-D spectral peak;
* the ripple orientation θ (deg)             — structure-tensor dominant direction,
                                              circular statistics (period 180 deg);
* the coherence C (0..1)                     — structure-tensor anisotropy, i.e. "how
                                              ordered" the texture is;
* the profile contrast K                     — visible ripple strength;
* the ordered / disordered / bare **area fractions** from a tile map;
* the debris (bright particle) density per mm².

and the batch-level consistency figures: between-coupon CV of Λ, circular SD of θ,
SD of C, area fractions, plus ICC(1,1) when more than one field per coupon exists.

Why autocorrelation and not the FFT maximum
-------------------------------------------
On 3 k images (31.25 nm/px) the ripple fundamental is ~12 px.  The 2-D FFT power in
that band is dominated by the slow illumination envelope at 80-90 px, so "take the
strongest peak" returns 450-500 nm instead of the true ~385 nm (this is the documented
v4 defect of the old DLOA pipeline).  Averaging the intensity samples along the ripple
tangent (which is phase-coherent) and autocorrelating the resulting 1-D profile
isolates the fundamental: on the six 515 nm coupons it returns 375-395 nm, matching the
AFM value 384.6 nm and the v5 ring analysis 378-396 nm.

Conventions
-----------
* pixel size     31.25 nm/px for the 3 k images (1 µm scale bar = 32 px),
                 7.8125 nm/px for the 12 k images (1 µm = 128 px).
                 Read automatically from a JSM ``*.txt`` sidecar when present.
* orientation    reported as the **grating (ripple) direction**?  No: it is the
                 gradient normal, i.e. the direction across the ripples, mod 180.
                 For "ridge direction" add 90 deg.
"""
from __future__ import annotations

import os
import re
import glob
import json
import math
import csv

import numpy as np
from scipy.ndimage import (gaussian_filter, gaussian_filter1d, rotate,
                          map_coordinates, label, binary_opening, grey_opening)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

from ..common.io_utils import ensure_output_dir, save_csv, save_figure

__all__ = ["run", "analyse_image", "annotate_image", "annotate_folder",
           "DEFAULT_QC", "DEFAULT_CRITERIA"]

# --------------------------------------------------------------------------- #
# Defaults (calibrated on the 515 nm coupon series, 2026-11-03)
# --------------------------------------------------------------------------- #
DEFAULT_PIXEL_NM = 31.25
BAND_NM = (240.0, 800.0)          # admissible ripple periods
TILE_PX = 256                      # fallback tile edge (px) when no physical size is given
DEFAULT_TILE_UM = 4.0              # classification window in µm (128 px on the 3 k images:
                                   # a quarter of the earlier 8 µm window)
TILE_STEP = None                   # non-overlapping: window fraction == area fraction
HP_SIGMA_PX = 20                   # high-pass: removes illumination > ~0.6 µm

#: tile acceptance thresholds -> ordered / disordered / bare.
#: Two presets, because the two structure types do not reach the same order: a grating
#: keeps long-range phase (high autocorrelation), a pillar lattice does not.
DEFAULT_QC = {
    "single": {                    # LIPSS-like, one ripple family
        "coherence_ordered": 0.45,
        "coherence_texture": 0.15,
        "period_tol": 0.10,
        "angle_tol_deg": 10.0,
        "ac_strength": 0.40,
    },
    "mixed": {                     # nanopillar / crossed lattice, periodic both ways
        "coherence_ordered": 0.38,
        "coherence_texture": 0.12,
        # wider than the grating tolerance on purpose: a pillar lattice has an intrinsic
        # spacing dispersion (measured p10-p90 = +-20 % over 128 px windows), so a +-12 %
        # band would flag good lattice as defective.  The lattice is judged mainly on C
        # and on the autocorrelation, which are the properties that actually degrade.
        "period_tol": 0.20,
        "angle_tol_deg": 15.0,
        "ac_strength": 0.15,
    },
}

#: batch-level consistency criteria (example values, editable per study)
DEFAULT_CRITERIA = {
    "cv_period_pct": 3.0,          # between-coupon CV of the period
    "theta_sd_deg": 3.0,           # between-coupon circular SD of the orientation
    "coherence_mean": 0.40,        # mean coherence
    "ordered_mean_pct": 70.0,      # mean ordered-area fraction (monitoring threshold)
    "ordered_spread_pts": 20.0,    # worst coupon may sit at most this far below the group mean
                                   # (a relative criterion: with ~15 windows per field an
                                   #  absolute floor would just measure sampling granularity)
    "bare_max_pct": 10.0,          # worst coupon
}

CLASS_ORDERED, CLASS_DISORDERED, CLASS_BARE = 2, 1, 0


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _load_gray(path):
    from PIL import Image
    im = Image.open(path)
    a = np.array(im)
    if a.ndim == 3:
        a = np.array(im.convert("L"))
    return a.astype(np.float64)


def _crop_scalebar(img, rel=0.90, max_frac=0.30):
    """Drop the bottom information / scale-bar band of a JSM micrograph.

    The band is darker than the field (typically 0.75-0.85 of the median) but not
    black, so an absolute threshold misses it.  Rows are removed from the bottom
    while their mean stays below ``rel`` x the image median.
    """
    h = img.shape[0]
    med = float(np.median(img))
    rows = img.mean(axis=1)
    flag = rows < rel * med
    floor = int(h * (1.0 - max_frac))
    i = h - 1
    # a bright 1-px frame line can sit below the band: skip up to 6 trailing bright rows
    while i > h - 7 and not flag[i]:
        i -= 1
    if not flag[i]:
        return img
    j = i
    while j > floor and flag[j]:
        j -= 1
    cut = j + 1
    return img[:cut, :] if 0 < cut < h else img


def _circ_mean_deg(deg, weights=None):
    """Circular mean of angles with period 180 deg."""
    a = np.radians(np.asarray(deg, dtype=float) * 2.0)
    w = np.ones_like(a) if weights is None else np.asarray(weights, dtype=float)
    z = np.sum(w * np.exp(1j * a))
    return float(np.degrees(np.angle(z)) / 2.0) % 180.0


def _circ_sd_deg(deg, weights=None):
    """Circular SD (deg) of angles with period 180 deg."""
    a = np.radians(np.asarray(deg, dtype=float) * 2.0)
    w = np.ones_like(a) if weights is None else np.asarray(weights, dtype=float)
    z = np.sum(w * np.exp(1j * a)) / max(np.sum(w), 1e-12)
    R = np.abs(z)
    R = min(max(R, 1e-12), 1.0)
    return float(np.degrees(np.sqrt(-2.0 * np.log(R))) / 2.0)


def _structure_tensor(img, grad_sigma=1.0, tensor_sigma=6.0):
    """Coherence C and gradient direction θ (deg, mod 180) of an image."""
    amp = np.percentile(np.abs(img), 99) + 1e-9
    x = img / amp
    gx = gaussian_filter1d(x, grad_sigma, axis=1, order=1)
    gy = gaussian_filter1d(x, grad_sigma, axis=0, order=1)
    Jxx = gaussian_filter(gx * gx, tensor_sigma)
    Jyy = gaussian_filter(gy * gy, tensor_sigma)
    Jxy = gaussian_filter(gx * gy, tensor_sigma)
    dif = np.sqrt((Jxx - Jyy) ** 2 + 4.0 * Jxy ** 2)
    coh = dif / (Jxx + Jyy + 1e-12)
    theta = 0.5 * np.degrees(np.arctan2(2.0 * Jxy, Jxx - Jyy)) % 180.0
    return coh, theta


def _mean_profile(img, theta_deg, margin=0.08):
    """Phase-coherent 1-D profile: average along the ripple tangent.

    The image is rotated so that the ripple normal becomes vertical, then the rows
    are averaged across columns.  Because the ripple phase is constant along the
    tangent, this averaging reinforces the fundamental and suppresses noise.
    """
    # rotate so that the gradient (normal) direction becomes +90 deg (vertical)
    ang = theta_deg - 90.0
    rot = rotate(img, ang, reshape=False, order=1, mode="nearest")
    h, w = rot.shape
    band = rot[int(margin * h):int((1 - margin) * h),
               int(margin * w):int((1 - margin) * w)]
    prof = band.mean(axis=1)
    return gaussian_filter1d(prof - prof.mean(), 1.5)


def _period_from_profile(prof, px_nm, band_nm=BAND_NM):
    """Period (nm) and autocorrelation strength from a 1-D profile."""
    pmin = max(int(math.floor(band_nm[0] / px_nm)), 3)
    pmax = max(int(math.ceil(band_nm[1] / px_nm)), pmin + 2)
    pmax = min(pmax, len(prof) // 2)

    ac = np.correlate(prof, prof, mode="full")[len(prof) - 1:]
    ac = ac / (ac[0] + 1e-12)
    seg = ac[pmin:pmax + 1]
    idx = np.where((seg[1:-1] > seg[:-2]) & (seg[1:-1] >= seg[2:]))[0] + 1
    lam_ac = np.nan
    strength = 0.0
    if len(idx):
        k = int(idx[np.argmax(seg[idx])])
        p0 = pmin + k
        y0, y1, y2 = ac[p0 - 1], ac[p0], ac[p0 + 1]
        den = y0 - 2 * y1 + y2
        pf = p0 + (0.5 * (y0 - y2) / den if den != 0 else 0.0)
        lam_ac = pf * px_nm
        strength = float(ac[p0])
        if strength < 0.05:          # degenerate local maximum
            lam_ac, strength = np.nan, float(strength)

    # 1-D spectral peak in the same band, for the cross-check
    n = len(prof)
    freq = np.fft.rfftfreq(n, d=px_nm)                # cycles / nm
    amp = np.abs(np.fft.rfft(prof * np.hanning(n)))
    m = (freq > 1.0 / band_nm[1]) & (freq < 1.0 / band_nm[0])
    lam_fft = np.nan
    prom = 0.0
    if np.any(m):
        j = int(np.argmax(np.where(m, amp, 0)))
        lam_fft = 1.0 / freq[j] if freq[j] > 0 else np.nan
        base = np.median(amp[m])
        prom = float((amp[j] - base) / (base + 1e-12))
    return dict(period_nm=float(lam_ac), ac_strength=strength,
                period_fft_nm=float(lam_fft), fft_prominence=prom,
                n_periods=float(len(prof) / max(lam_ac / px_nm, 1.0)) if np.isfinite(lam_ac) else np.nan)


def _debris(img, px_nm, min_area_px=20, threshold_mad=8.0):
    """Bright-particle (debris) count per mm² and area fraction."""
    hp = img - grey_opening(img, size=(15, 15))
    med = np.median(hp)
    mad = np.median(np.abs(hp - med)) + 1e-9
    mask = hp > med + threshold_mad * 1.4826 * mad
    mask[:6, :] = False                      # ignore the frame lines
    mask[-6:, :] = False
    mask[:, :6] = False
    mask[:, -6:] = False
    lab, n = label(mask)
    if n:
        areas = np.bincount(lab.ravel())[1:]
        keep = areas >= min_area_px
        n_keep = int(np.sum(keep))
        area_frac = float(areas[keep].sum() / mask.size) if n_keep else 0.0
    else:
        n_keep, area_frac = 0, 0.0
    mm2 = (img.shape[0] * px_nm * img.shape[1] * px_nm) * 1e-12   # nm² -> mm²
    return dict(debris_count=n_keep, debris_per_mm2=n_keep / max(mm2, 1e-12),
                debris_area_frac=area_frac)


def _sidecar_pixel_nm(path):
    """Read the pixel size from a JSM ``*.txt`` sidecar next to the image."""
    stem = os.path.splitext(path)[0]
    for cand in (stem + ".txt", stem + "_e.txt"):
        if os.path.exists(cand):
            try:
                txt = open(cand, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            bar = re.search(r"SM_MICRON_BAR\s+([0-9.]+)", txt)
            mk = re.search(r"SM_MICRON_MARKER\s+([0-9.]+)", txt)
            if bar and mk and float(bar.group(1)) > 0:
                return 1000.0 * float(mk.group(1)) / float(bar.group(1))
    return None


_COUPON_RE = re.compile(r"^(?P<coupon>[0-9]+)\s*[-_]\s*(?P<position>[0-9]+)", re.I)


def _coupon_id(path, alias=None):
    if alias:
        return str(alias)
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"_e$", "", stem, flags=re.I)
    m = _COUPON_RE.match(stem)
    if m:
        return f"{m.group('coupon')}-{m.group('position')}"
    m = re.match(r"^(\d+)", stem)
    return m.group(1) if m else stem


#: profile-autocorrelation strength that separates a grating from a lattice.  Calibrated
#: on the 515 nm series at both magnifications: gratings 0.71-0.83, pillar fields 0.19-0.48
#: (polished areas 0.19-0.27).  A factor-2 gap, and unlike the coherence it does not drift
#: with magnification, because it measures phase survival along the profile.
SINGLE_AC_SPLIT = 0.60


def _rasterise_classes(tiles, shape, tile):
    """Pixel-level class map of the tile grid (worst class wins where tiles overlap).

    Returns an int8 array: -2 = no tile covers this pixel, -1 = excluded tile,
    0 = bare, 1 = disordered, 2 = ordered.  Fractions computed from this array are
    true area fractions of the field — which is what the annotated copies paint —
    whereas counting tiles would over-weight isolated defects (one 256 px window is
    5 % of a 1280 x 1024 frame).
    """
    cls = np.full(shape, -2, dtype=np.int8)
    prio_map = {0: 3, 1: 2, -1: 1, 2: 0}       # higher wins: bare > disordered > excluded > ordered
    prio = np.full(shape, -1, dtype=np.int8)
    for t in tiles:
        y0, x0, v = t["y0"], t["x0"], int(t["class"])
        pr = prio_map.get(v, 0)
        sl = (slice(y0, min(y0 + tile, shape[0])), slice(x0, min(x0 + tile, shape[1])))
        upd = pr > prio[sl]
        cls[sl][upd] = v
        prio[sl][upd] = pr
    return cls


def _families(hp, theta0, px_nm, per0, c_img):
    """(families, mode) for one field.

    ``single`` — one ripple family dominates (a grating): the periodicity survives
    along the profile (autocorrelation strength >= SINGLE_AC_SPLIT).  ``mixed`` — the
    field is periodic in two roughly orthogonal directions (pillar lattice), so no
    single family keeps phase over long distances; the second reference direction is
    then placed at theta + 90 deg with the same lattice constant, which is what the
    12 k images of the same position show (both directions give ~320-345 nm).

    The decision is made from the measured profile autocorrelation, not from the folder
    name and not from the coherence (the coherence drifts with magnification).
    """
    fams = [dict(theta_deg=float(theta0), period_nm=float(per0["period_nm"]),
                 strength=float(per0["ac_strength"]))]
    mode = "single" if per0["ac_strength"] >= SINGLE_AC_SPLIT else "mixed"
    if mode == "mixed" and np.isfinite(per0["period_nm"]):
        fams.append(dict(theta_deg=float((theta0 + 90.0) % 180.0),
                         period_nm=float(per0["period_nm"]),
                         strength=float(per0["ac_strength"])))
    return fams, mode


# --------------------------------------------------------------------------- #
# single-image analysis
# --------------------------------------------------------------------------- #
def analyse_image(path, pixel_nm=None, tile=None, step=None, qc=None,
                  tile_um=DEFAULT_TILE_UM):
    """Full metric set for one micrograph.

    The classification window is given in **µm** (``tile_um``, default 4 µm) so that the
    same physical window is used at any magnification; ``tile`` overrides it in pixels.
    ``step`` defaults to the tile edge (non-overlapping), so the reported area fractions
    are exactly the painted area.
    """
    px = pixel_nm or _sidecar_pixel_nm(path) or DEFAULT_PIXEL_NM
    if tile is None:
        tile = int(round(tile_um * 1000.0 / px))
    tile = max(int(tile), 32)
    qc_override = qc or {}
    step = int(step or tile)

    raw = _load_gray(path)
    img = _crop_scalebar(raw)
    hp = img - gaussian_filter(img, HP_SIGMA_PX)      # remove illumination envelope

    coh, theta = _structure_tensor(hp)
    w = coh ** 2
    theta0 = _circ_mean_deg(theta, w)
    c_img = float(np.mean(coh))

    prof = _mean_profile(hp, theta0)
    per = _period_from_profile(prof, px)

    # second pass: match the structure-tensor window to the ripple wavelength, so that
    # the coherence means the same thing at 3 k and at 12 k (a fixed 6-px window sees
    # 187 nm at 3 k but only 47 nm at 12 k, which biases C downwards).
    lam_px = per["period_nm"] / px if np.isfinite(per["period_nm"]) else 0.0
    sig = float(max(6.0, 0.5 * lam_px))
    if sig > 6.5:
        coh, theta = _structure_tensor(hp, tensor_sigma=sig)
        w = coh ** 2
        theta0 = _circ_mean_deg(theta, w)
        c_img = float(np.mean(coh))
        prof = _mean_profile(hp, theta0)
        per = _period_from_profile(prof, px)
    contrast = float(np.std(prof) / (np.mean(img) + 1e-9))

    res = {
        "file": os.path.basename(path),
        "coupon": _coupon_id(path),
        "pixel_nm": px,
        "period_nm": per["period_nm"],
        "period_fft_nm": per["period_fft_nm"],
        "period_agree_pct": (100.0 * abs(per["period_nm"] - per["period_fft_nm"])
                             / per["period_nm"]) if np.isfinite(per["period_fft_nm"]) else np.nan,
        "ac_strength": per["ac_strength"],
        "fft_prominence": per["fft_prominence"],
        "n_periods_fov": per["n_periods"],
        "theta_deg": theta0,
        "theta_st_sd_deg": _circ_sd_deg(theta, w),
        "coherence": c_img,
        "contrast": contrast,
        "img_w_px": img.shape[1], "img_h_px": img.shape[0],
        "tensor_sigma_px": sig,
    }
    res.update(_debris(hp, px))
    res["mode"] = "single"

    # ---------------- tile map -------------------------------------------
    h, wdt = img.shape
    img_med = float(np.median(img))
    rows = []
    for y0 in range(0, max(h - tile, 1) + 1, step):
        for x0 in range(0, max(wdt - tile, 1) + 1, step):
            t = hp[y0:y0 + tile, x0:x0 + tile]
            if t.shape != (tile, tile):
                continue
            ct, tht = _structure_tensor(t, tensor_sigma=4.0)
            wt = ct ** 2
            th_t = _circ_mean_deg(tht, wt)
            c_t = float(np.mean(ct))
            pr = _mean_profile(t, th_t, margin=0.03)
            pt = _period_from_profile(pr, px)
            m_int = float(np.mean(img[y0:y0 + tile, x0:x0 + tile]))
            rows.append(dict(y0=y0, x0=x0, coherence=c_t, theta_deg=th_t,
                             period_nm=pt["period_nm"], ac_strength=pt["ac_strength"],
                             contrast=float(np.std(pr) / (np.mean(np.abs(t)) + 1e-9)),
                             mean_int=m_int,
                             valid=int(m_int >= 0.45 * img_med)))
    tiles = rows
    if tiles:
        valid = [t for t in tiles if t["valid"]]
        fams, mode = _families(hp, theta0, px, per, c_img)
        qc = dict(DEFAULT_QC[mode])
        qc.update({k: v for k, v in qc_override.items() if k in qc})
        res["mode"] = mode
        for t in tiles:
            if not t["valid"]:
                t["class"] = -1                      # excluded (dark border etc.)
                t["family"] = -1
                continue
            best = None
            for k, f in enumerate(fams):
                d_ang = abs(((t["theta_deg"] - f["theta_deg"] + 90.0) % 180.0) - 90.0)
                dlam = (abs(t["period_nm"] - f["period_nm"]) / f["period_nm"]
                        if np.isfinite(t["period_nm"]) and f["period_nm"] else np.inf)
                score = (min(d_ang / max(qc["angle_tol_deg"], 1e-6), 9.0)
                         + min(dlam / max(qc["period_tol"], 1e-6), 9.0))
                if best is None or score < best[0]:
                    best = (score, k, d_ang, dlam)
            if best is None:
                best = (np.inf, -1, 90.0, np.inf)
            _, k_fam, d_ang, dlam = best
            t["family"] = k_fam
            t["d_angle_deg"] = d_ang
            t["d_period_frac"] = dlam
            ordered = (k_fam >= 0
                       and t["coherence"] >= qc["coherence_ordered"]
                       and dlam <= qc["period_tol"]
                       and d_ang <= qc["angle_tol_deg"]
                       and t["ac_strength"] >= qc["ac_strength"])
            textured = (t["coherence"] >= qc["coherence_texture"]
                        and np.isfinite(t["period_nm"]))
            t["class"] = CLASS_ORDERED if ordered else (CLASS_DISORDERED if textured else CLASS_BARE)

        n = len(tiles)
        # ---- area fractions on the rasterised map (overlapping tiles counted once) ----
        cmap_px = _rasterise_classes(tiles, (h, wdt), tile)
        in_field = cmap_px != -2
        n_field_px = int(in_field.sum())
        n_ord = int(np.count_nonzero(cmap_px == CLASS_ORDERED))
        n_dis = int(np.count_nonzero(cmap_px == CLASS_DISORDERED))
        n_bar = int(np.count_nonzero(cmap_px == CLASS_BARE))
        n_val = n_ord + n_dis + n_bar
        cls = np.array([t["class"] for t in tiles])
        cls = cls[cls >= 0]
        # period statistics inside the dominant family
        dom = [t for t in valid if t.get("family") == 0] if fams else valid
        lam_dom = np.array([t["period_nm"] for t in dom], dtype=float)
        ok_dom = np.isfinite(lam_dom)
        res.update({
            "n_tiles": n,
            "n_tiles_valid": int(len(cls)),
            "invalid_frac": float(1.0 - n_val / max(h * wdt, 1)),
            "ordered_frac": (n_ord / n_val) if n_val else np.nan,
            "disordered_frac": (n_dis / n_val) if n_val else np.nan,
            "bare_frac": (n_bar / n_val) if n_val else np.nan,
            "tile_frac_ordered": float(np.mean(cls == CLASS_ORDERED)) if len(cls) else np.nan,
            "n_families": len(fams),
            "theta1_deg": fams[0]["theta_deg"] if fams else np.nan,
            "theta2_deg": fams[1]["theta_deg"] if len(fams) > 1 else np.nan,
            "period_family1_nm": fams[0]["period_nm"] if fams else np.nan,
            "period_family2_nm": fams[1]["period_nm"] if len(fams) > 1 else np.nan,
            "tile_period_median_nm": float(np.nanmedian(lam_dom)) if ok_dom.any() else np.nan,
            "period_sd_nm": (float(1.4826 * np.nanmedian(np.abs(lam_dom[ok_dom] - np.nanmedian(lam_dom[ok_dom]))))
                             if ok_dom.sum() > 2 else np.nan),
            "period_mad_frac": (float(np.nanmedian(np.abs(lam_dom[ok_dom] - np.nanmedian(lam_dom[ok_dom])))
                                      / np.nanmedian(lam_dom[ok_dom])) if ok_dom.sum() > 2 else np.nan),
            "tile_period_iqr_nm": (float(np.nanpercentile(lam_dom[ok_dom], 75)
                                         - np.nanpercentile(lam_dom[ok_dom], 25))
                                   if ok_dom.sum() > 1 else np.nan),
            "tile_period_cv": (float(np.nanstd(lam_dom[ok_dom]) / np.nanmean(lam_dom[ok_dom]))
                               if ok_dom.sum() > 1 else np.nan),
            "tile_theta_sd_deg": (_circ_sd_deg([t["theta_deg"] for t in valid])
                                  if len(valid) > 1 else np.nan),
            "tile_coherence_mean": float(np.mean([t["coherence"] for t in valid])) if valid else np.nan,
            "tile_contrast_mean": float(np.mean([t["contrast"] for t in valid])) if valid else np.nan,
        })
        if fams:
            res["period_profile_nm"] = res["period_nm"]
            res["period_nm"] = fams[0]["period_nm"]
            res["period2_nm"] = fams[1]["period_nm"] if len(fams) > 1 else np.nan
    res["tile_px"] = tile
    res["_tiles"] = tiles
    res["_qc"] = qc
    res["qc_mode"] = res.get("mode", "single")
    return res


# --------------------------------------------------------------------------- #
# batch driver
# --------------------------------------------------------------------------- #
def _discover(folder, exts=(".bmp", ".tif", ".tiff", ".png", ".jpg", ".jpeg")):
    """List images with their group (parent folder name)."""
    out = []
    for root, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if f.lower().endswith(exts) and not f.startswith("."):
                p = os.path.join(root, f)
                grp = os.path.basename(root)
                if os.path.abspath(root) == os.path.abspath(folder):
                    grp = os.path.basename(folder)
                out.append((grp, p))
    return out


def _batch_stats(df, criteria):
    rows = []
    for grp, sub in df.groupby("group"):
        lam = sub["period_nm"].to_numpy(float)
        lam = lam[np.isfinite(lam)]
        th = sub["theta_deg"].to_numpy(float)
        coh = sub["coherence"].to_numpy(float)
        cvs = 100.0 * np.nanstd(lam, ddof=1) / np.nanmean(lam) if len(lam) > 1 else np.nan
        th_sd = _circ_sd_deg(th) if len(th) > 1 else np.nan
        ordr = 100.0 * sub["ordered_frac"].to_numpy(float)
        bare = 100.0 * sub["bare_frac"].to_numpy(float)
        rows.append({
            "group": grp, "n_fields": len(sub), "n_coupons": sub["coupon"].nunique(),
            "period_mean_nm": np.nanmean(lam), "period_sd_nm": np.nanstd(lam, ddof=1) if len(lam) > 1 else np.nan,
            "period_cv_pct": cvs,
            "theta_mean_deg": _circ_mean_deg(th), "theta_sd_deg": th_sd,
            "coherence_mean": np.nanmean(coh), "coherence_sd": np.nanstd(coh, ddof=1) if len(coh) > 1 else np.nan,
            "contrast_mean": np.nanmean(sub["contrast"]),
            "ordered_mean_pct": float(np.nanmean(ordr)), "ordered_min_pct": float(np.nanmin(ordr)),
            "bare_mean_pct": float(np.nanmean(bare)), "bare_max_pct": float(np.nanmax(bare)),
            "disordered_mean_pct": 100.0 * float(np.nanmean(sub["disordered_frac"])),
            "debris_median_per_mm2": float(np.nanmedian(sub["debris_per_mm2"])),
        })
    st = rows[0] if rows else {}
    checks = [
        ("period CV (between coupons)", "period_cv_pct", "le", criteria["cv_period_pct"], "%"),
        ("orientation SD (between coupons)", "theta_sd_deg", "le", criteria["theta_sd_deg"], "deg"),
        ("mean coherence", "coherence_mean", "ge", criteria["coherence_mean"], ""),
        ("mean ordered area", "ordered_mean_pct", "ge", criteria["ordered_mean_pct"], "%"),
        ("worst coupon vs group mean", "ordered_min_pct", "ge", None, "%"),   # dynamic limit
        ("worst coupon bare area", "bare_max_pct", "le", criteria["bare_max_pct"], "%"),
    ]
    for r in rows:
        verdicts = []
        for label, key, op, lim, unit in checks:
            if lim is None:                       # relative-uniformity check
                lim = r["ordered_mean_pct"] - criteria["ordered_spread_pts"]
            r["limit_" + key] = lim
            v = r.get(key, np.nan)
            pass_ = (v <= lim) if op == "le" else (v >= lim)
            verdicts.append(bool(pass_) and np.isfinite(v))
            r["chk_" + key] = "PASS" if (pass_ and np.isfinite(v)) else "FAIL"
        r["verdict"] = "PASS" if all(verdicts) else "FAIL"
    return rows, checks


def _icc_1_1(values_by_coupon):
    """ICC(1,1) one-way random effects, from a dict coupon -> list of values."""
    groups = [np.asarray(v, float) for v in values_by_coupon.values() if len(v) > 1]
    if len(groups) < 2:
        return np.nan
    n = np.array([len(g) for g in groups], float)
    means = np.array([g.mean() for g in groups])
    k = n.mean()
    grand = np.average(means, weights=n)
    msb = np.sum(n * (means - grand) ** 2) / (len(groups) - 1)
    ss_within = sum(np.sum((g - g.mean()) ** 2) for g in groups)
    df_within = max(n.sum() - len(groups), 1)
    msw = ss_within / df_within
    denom = msb + (k - 1) * msw
    return float((msb - msw) / denom) if denom > 0 else np.nan


# --------------------------------------------------------------------------- #
# figures
# --------------------------------------------------------------------------- #
def _plot_tile_map(img_path, res, out_png, px_nm):
    raw = _crop_scalebar(_load_gray(img_path))
    tiles = res["_tiles"]
    fig, axes = plt.subplots(1, 3, figsize=(13.4, 4.2))

    axes[0].imshow(raw, cmap="gray")
    axes[0].set_title(f"{res['coupon']}  —  raw", fontsize=9)
    axes[0].axis("off")

    cmap = ListedColormap(["#6e6e6e", "#d62728", "#ff9f1a", "#2ca02c"])
    norm = BoundaryNorm([-1.5, -0.5, 0.5, 1.5, 2.5], cmap.N)
    canvas = np.full(raw.shape, CLASS_BARE, dtype=float)
    vals = np.full(raw.shape, np.nan)
    tile = int(max(res.get("tile_px", TILE_PX), 32))
    for t in tiles:
        canvas[t["y0"]:t["y0"] + tile, t["x0"]:t["x0"] + tile] = t["class"]
        vals[t["y0"]:t["y0"] + tile, t["x0"]:t["x0"] + tile] = t["period_nm"]
    axes[1].imshow(canvas, cmap=cmap, norm=norm, interpolation="nearest")
    axes[1].set_title("class map  (green ordered / orange disordered / red bare / grey excluded)", fontsize=9)
    axes[1].axis("off")

    im = axes[2].imshow(vals, cmap="viridis", interpolation="nearest")
    axes[2].set_title("local period (nm)", fontsize=9)
    axes[2].axis("off")
    cb = fig.colorbar(im, ax=axes[2], fraction=0.046, pad=0.02)
    cb.ax.tick_params(labelsize=7)

    fig.suptitle(f"Λ = {res['period_nm']:.1f} nm   θ = {res['theta_deg']:.1f}°   C = {res['coherence']:.3f}"
                 f"   ordered = {100*res.get('ordered_frac', np.nan):.0f} %", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_png, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return out_png


def _plot_summary(df, out_png):
    """Per-image period / orientation / ordered area, coloured by group."""
    d = df.sort_values(["group", "coupon", "file"]).reset_index(drop=True)
    groups = list(dict.fromkeys(d["group"]))
    palette = plt.cm.tab10(np.linspace(0, 1, max(len(groups), 2)))
    colors = {g: palette[i % len(palette)] for i, g in enumerate(groups)}
    x = np.arange(len(d))
    labels = [f"{r.coupon}" for r in d.itertuples()]

    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.0))
    metrics = [("period_nm", "period Λ (nm)", "period_sd_nm"),
               ("theta_deg", "orientation θ (deg)", None),
               ("ordered_frac", "ordered area (fraction)", None)]
    for ax, (col, ylab, errcol) in zip(axes, metrics):
        for g in groups:
            m = (d["group"] == g).to_numpy()
            y = d.loc[m, col].to_numpy(float)
            if col == "ordered_frac":
                y = 100.0 * y
            if errcol:
                ax.errorbar(x[m], y, yerr=d.loc[m, errcol].to_numpy(float), fmt="o", ms=5,
                            capsize=2.5, lw=0.9, color=colors[g], label=g)
            else:
                ax.plot(x[m], y, "o", ms=5, color=colors[g], label=g)
        ax.set_ylabel(ylab)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=90, fontsize=6.5)
        ax.grid(alpha=0.25, lw=0.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[2].set_ylim(-5, 105)
    axes[0].legend(frameon=False, fontsize=7, loc="best")
    fig.tight_layout()
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_png


# --------------------------------------------------------------------------- #
# annotated copies: the original micrograph with the poor areas marked
# --------------------------------------------------------------------------- #
_CLASS_STYLE = {
    CLASS_DISORDERED: dict(color=(0.98, 0.55, 0.05), alpha=0.42,
                           label="disordered  (texture present but off-spec)"),
    CLASS_BARE: dict(color=(0.78, 0.06, 0.18), alpha=0.52,
                     label="bare / unprocessed  (no periodic texture)"),
    -1: dict(color=(0.45, 0.45, 0.45), alpha=0.20, label="excluded  (frame line)"),
}


def annotate_image(path, out_path, res=None, linewidth=1.2, label=True):
    """Copy the micrograph and mark the areas whose processing quality is poor.

    Only the defective tiles are painted (semi-transparent colour + white outline;
    bare areas additionally hatched), so the texture stays readable everywhere else.
    The full frame — instrument footer and scale bar included — is preserved.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch

    if res is None:
        res = analyse_image(path)
    img = _load_gray(path)                      # full frame, scale bar included
    h, w = img.shape
    tile = int(res.get("tile_px", TILE_PX))

    fig = plt.figure(figsize=(w / 100.0, h / 100.0), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(img, cmap="gray", vmin=np.percentile(img, 1), vmax=np.percentile(img, 99.5),
              extent=(0, w, h, 0), interpolation="nearest")
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis("off")

    n_bad = 0
    for t in res.get("_tiles", []):
        cls = t["class"]
        if cls == CLASS_ORDERED:
            continue                            # good area: left untouched
        st = _CLASS_STYLE.get(cls, _CLASS_STYLE[CLASS_BARE])
        ax.add_patch(Rectangle((t["x0"], t["y0"]), tile, tile,
                               facecolor=st["color"], alpha=st["alpha"],
                               edgecolor="none", zorder=3))
        ax.add_patch(Rectangle((t["x0"], t["y0"]), tile, tile, fill=False,
                               edgecolor=(1, 1, 1), lw=linewidth, zorder=4))
        if cls >= 0:
            n_bad += 1
        if cls == CLASS_BARE:                   # hatch the unprocessed areas
            ax.add_patch(Rectangle((t["x0"], t["y0"]), tile, tile, fill=False,
                                   hatch="////", edgecolor=(1, 1, 1, 0.85), lw=0.0, zorder=5))

    # outline the analysed field (the tiled part of the frame; the instrument footer
    # below it is not analysed)
    tl = res.get("_tiles", [])
    if tl:
        x0 = min(t["x0"] for t in tl); x1 = max(t["x0"] for t in tl) + tile
        y0 = min(t["y0"] for t in tl); y1 = max(t["y0"] for t in tl) + tile
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ls=(0, (6, 4)),
                               edgecolor=(1, 1, 1, 0.75), lw=1.1, zorder=6))
        ax.text(x1 - 4, y1 + 14, "analysed field", color=(1, 1, 1, 0.85), fontsize=9,
                ha="right", va="bottom", zorder=6)

    if label:
        stats = (f"{res['coupon']}\n"
                 f"Λ = {res['period_nm']:.0f} nm    C = {res['coherence']:.2f}\n"
                 f"ordered {100*res.get('ordered_frac', np.nan):.0f} %   "
                 f"disordered {100*res.get('disordered_frac', np.nan):.0f} %   "
                 f"bare {100*res.get('bare_frac', np.nan):.0f} %")
        ax.text(0.015, 0.975, stats, transform=ax.transAxes, fontsize=13, color="white",
                va="top", ha="left", linespacing=1.45,
                bbox=dict(facecolor=(0, 0, 0, 0.72), edgecolor=(1, 1, 1, 0.45),
                          boxstyle="round,pad=0.45"), zorder=8)
        if n_bad == 0:
            ax.text(0.985, 0.975, "no defective region detected", transform=ax.transAxes,
                    fontsize=12, color=(0.75, 1, 0.75), va="top", ha="right",
                    bbox=dict(facecolor=(0, 0, 0, 0.72), edgecolor="none", pad=4), zorder=8)
        else:
            handles = [Patch(facecolor=_CLASS_STYLE[CLASS_DISORDERED]["color"],
                             edgecolor="white", lw=0.8, label=_CLASS_STYLE[CLASS_DISORDERED]["label"]),
                       Patch(facecolor=_CLASS_STYLE[CLASS_BARE]["color"], edgecolor="white", lw=0.8,
                             hatch="////", label=_CLASS_STYLE[CLASS_BARE]["label"]),
                       Patch(facecolor="none", edgecolor=(0.85, 0.85, 0.85), lw=1.0,
                             label="ordered  (not marked)")]
            leg = ax.legend(handles=handles, loc="upper right", fontsize=11, framealpha=0.80,
                            facecolor="black", labelcolor="white", borderpad=0.7,
                            handlelength=1.6, labelspacing=0.55)
            leg.set_zorder(9)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=100, facecolor="black")
    plt.close(fig)
    return out_path


def annotate_folder(folder, out_dir, pixel_nm=None, tile=None, step=None,
                    qc=None, suffix="_quality", verbose=True, tile_um=DEFAULT_TILE_UM):
    """Annotated copies (poor areas marked) of every image under *folder*.

    Keeps the group sub-folder structure, writes ``<stem><suffix>.png`` and returns
    the list of (source, annotated) pairs plus a summary DataFrame.
    """
    import pandas as pd
    rows = []
    for grp, path in _discover(folder):
        try:
            res = analyse_image(path, pixel_nm=pixel_nm, tile=tile, step=step, qc=qc,
                                tile_um=tile_um)
        except Exception as exc:
            if verbose:
                print(f"  !! {os.path.basename(path)}: {exc}")
            continue
        rel = os.path.relpath(os.path.dirname(path), os.path.abspath(folder))
        sub = os.path.join(out_dir, "" if rel == "." else rel)
        out = os.path.join(sub, os.path.splitext(os.path.basename(path))[0] + suffix + ".png")
        annotate_image(path, out, res=res)
        rows.append(dict(source=path, annotated=out, group=grp, coupon=res["coupon"],
                         period_nm=res["period_nm"], coherence=res["coherence"],
                         ordered_frac=res["ordered_frac"], disordered_frac=res["disordered_frac"],
                         bare_frac=res["bare_frac"], invalid_frac=res.get("invalid_frac", np.nan),
                         mode=res.get("mode"), n_tiles=res.get("n_tiles")))
        if verbose:
            print(f"  {os.path.basename(out):28s} ordered {100*res['ordered_frac']:5.1f} %  "
                  f"disordered {100*res['disordered_frac']:5.1f} %  bare {100*res['bare_frac']:5.1f} %")
    df = pd.DataFrame(rows)
    if len(df):
        save_csv(df, os.path.join(out_dir, "quality_map_summary.csv"))
    return dict(output_dir=out_dir, n=len(df), table=df)


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def run(folder, output_dir=None, pixel_nm=None, tile=None, step=None,
        qc=None, criteria=None, figures=True, verbose=True,
        tile_um=DEFAULT_TILE_UM):
    """Analyse every SEM image under *folder* and write the QC tables.

    Parameters
    ----------
    folder : str
        Root folder; sub-folders become groups (e.g. ``LIPSS_regions``,
        ``nanopillar_regions``).  Images directly inside are one group named after
        the folder.
    output_dir : str, optional
        Defaults to ``output/sem_texture_<YYYYMMDD>``.
    pixel_nm : float, optional
        nm per pixel; otherwise a JSM ``*.txt`` sidecar is used, else 31.25 nm.
    """
    import datetime
    folder = os.path.abspath(folder)
    out = ensure_output_dir(output_dir or os.path.join(
        "output", "sem_texture_" + datetime.date.today().strftime("%Y%m%d")))
    figdir = ensure_output_dir(os.path.join(out, "figures"))
    tiledir = ensure_output_dir(os.path.join(out, "tiles"))
    qc = dict(qc or {})                 # partial overrides, applied per structure mode
    criteria = dict(DEFAULT_CRITERIA, **(criteria or {}))

    items = _discover(folder)
    if not items:
        raise FileNotFoundError(f"no SEM images under {folder}")

    rows, tiles_all, imgs, tiles_by_img = [], [], {}, {}
    for grp, path in items:
        try:
            r = analyse_image(path, pixel_nm=pixel_nm, tile=tile, step=step, qc=qc,
                              tile_um=tile_um)
        except Exception as exc:                      # keep going, report at the end
            if verbose:
                print(f"  !! {os.path.basename(path)}: {exc}")
            continue
        r["group"] = grp
        r["path"] = path
        rows.append(r)
        imgs[(grp, r["file"])] = path
        tiles = r.pop("_tiles", [])
        tiles_by_img[(grp, r["file"])] = tiles
        for t in tiles:
            t.update(group=grp, file=r["file"], coupon=r["coupon"])
            tiles_all.append(t)
        if verbose:
            print(f"  {grp}/{r['file']:<16s} Λ={r['period_nm']:7.1f} nm  θ={r['theta_deg']:6.1f}°  "
                  f"C={r['coherence']:.3f}  ordered={100*r['ordered_frac']:5.1f}%  bare={100*r['bare_frac']:4.1f}%")

    if not rows:
        raise RuntimeError("every image failed to analyse")

    import pandas as pd
    df = pd.DataFrame(rows).sort_values(["group", "coupon", "file"]).reset_index(drop=True)
    tdf = pd.DataFrame(tiles_all)
    stats, checks = _batch_stats(df, criteria)

    # ICC needs >1 field per coupon
    icc = {}
    for grp, sub in df.groupby("group"):
        by = {c: g["period_nm"].dropna().tolist() for c, g in sub.groupby("coupon")}
        icc[grp] = _icc_1_1(by)

    public = [c for c in df.columns if not c.startswith("_") and c != "path"]
    save_csv(df[public], os.path.join(out, "sem_texture_metrics.csv"))
    if len(tdf):
        save_csv(tdf, os.path.join(out, "sem_texture_tiles.csv"))
    save_csv(pd.DataFrame(stats), os.path.join(out, "sem_texture_consistency.csv"))
    with open(os.path.join(out, "sem_texture_checks.json"), "w", encoding="utf-8") as fh:
        json.dump([list(c) for c in checks], fh, ensure_ascii=False, indent=1)

    made = []
    if figures:
        for (grp, fname), path in imgs.items():
            base = next(x for x in rows if x["file"] == fname and x["group"] == grp)
            r = dict(base)
            r["_tiles"] = tiles_by_img.get((grp, fname), [])
            try:
                made.append(_plot_tile_map(path, r, os.path.join(
                    figdir, (os.path.splitext(fname)[0] + "_map.png")), r["pixel_nm"]))
            except Exception as exc:
                if verbose:
                    print(f"  !! figure {fname}: {exc}")
        made.append(_plot_summary(df, os.path.join(figdir, "consistency_summary.png")))

    # markdown digest -------------------------------------------------------
    md = [f"# SEM texture consistency — {os.path.basename(folder)}", ""]
    px_vals = sorted({round(float(v), 3) for v in df["pixel_nm"]})
    md.append(f"Images analysed: **{len(df)}**  |  groups: **{df['group'].nunique()}**  |  "
              f"coupons: **{df['coupon'].nunique()}**  |  pixel size "
              + ", ".join(f"{v:g}" for v in px_vals) + " nm/px")
    md.append("")
    md.append("## Batch consistency")
    md.append("")
    md.append("| group | n fields | coupons | Λ mean ± SD (nm) | CV (%) | θ mean ± SD (°) | C | ordered (%) | bare (%) | verdict |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    for s in stats:
        md.append(f"| {s['group']} | {s['n_fields']} | {s['n_coupons']} | "
                  f"{s['period_mean_nm']:.1f} ± {s['period_sd_nm']:.1f} | {s['period_cv_pct']:.2f} | "
                  f"{s['theta_mean_deg']:.1f} ± {s['theta_sd_deg']:.1f} | {s['coherence_mean']:.3f} | "
                  f"{s['ordered_mean_pct']:.1f} | {s['bare_mean_pct']:.1f} | **{s['verdict']}** |")
    md.append("")
    md.append("## Criteria applied")
    md.append("")
    md.append("| check | limit | result |")
    md.append("|---|---|---|")
    for label, key, op, lim, unit in checks:
        if lim is None:                      # relative check: show the limit per group
            lim_txt = " vs group mean − " + f"{criteria['ordered_spread_pts']:g}" + " pts"
        else:
            lim_txt = f"{'≤' if op == 'le' else '≥'} {lim:g}{unit}"
        md.append(f"| {label} | {lim_txt} | "
                  + ", ".join(f"{s['group']}: {s['chk_' + key]}" for s in stats) + " |")
    md.append("")
    md.append("## Per-image results")
    md.append("")
    cols = ["group", "coupon", "file", "period_nm", "theta_deg", "coherence", "contrast",
            "ordered_frac", "disordered_frac", "bare_frac", "debris_per_mm2"]
    md.append("| " + " | ".join(cols) + " |")
    md.append("|" + "---|" * len(cols))
    for _, r in df.iterrows():
        md.append("| " + " | ".join(
            f"{r[c]:.3g}" if isinstance(r[c], (float, np.floating)) else str(r[c]) for c in cols) + " |")
    md.append("")
    md.append(f"ICC(1,1) of the period: " + ", ".join(
        f"{g}: {'n/a (single field per coupon)' if not np.isfinite(v) else f'{v:.3f}'}" for g, v in icc.items()))
    rp = os.path.join(out, "report_sem_texture.md")
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    result = {
        "output_dir": out,
        "metrics_csv": os.path.join(out, "sem_texture_metrics.csv"),
        "tiles_csv": os.path.join(out, "sem_texture_tiles.csv") if len(tdf) else None,
        "consistency_csv": os.path.join(out, "sem_texture_consistency.csv"),
        "markdown": rp,
        "figures": made,
        "stats": stats,
        "checks": checks,
        "icc": icc,
        "n_images": len(df),
        "df": df,
    }
    if verbose:
        print(f"\noutput: {out}")
        for s in stats:
            print(f"  {s['group']}: Λ {s['period_mean_nm']:.1f} ± {s['period_sd_nm']:.1f} nm "
                  f"(CV {s['period_cv_pct']:.2f} %), θ SD {s['theta_sd_deg']:.1f}°, "
                  f"ordered {s['ordered_mean_pct']:.0f} %  -> {s['verdict']}")
    return result
