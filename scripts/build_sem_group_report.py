# -*- coding: utf-8 -*-
"""build_sem_group_report.py — one quality report per sample folder.

For a folder of SEM images (one coupon with many fields, or several coupons) it

  1. measures every image with labtoolbox.semtexture,
  2. writes annotated copies (original + poor areas marked) into ``QC_report/annotated``,
  3. draws consistency, tile-period, class-map and per-image comparison figures,
  4. builds an English docx (OMML equations) whose appendix shows **every image as a
     left/right pair: original | marked**,
  5. exports the PDF and drops docx+pdf in the sample folder itself.

Usage
-----
    python scripts/build_sem_group_report.py --folder "<sample dir>" [--tile-um 2]
        [--pixel-nm 31.25] [--title "..."] [--report-dir "<dir>"]
"""
import os
import sys
import csv
import glob
import json
import shutil
import argparse
import tempfile
import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.colors import ListedColormap, BoundaryNorm

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement, parse_xml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from labtoolbox.semtexture import (analyse_image, annotate_folder, annotate_image,
                                   _discover, _load_gray, _crop_scalebar,
                                   DEFAULT_TILE_UM, DEFAULT_PIXEL_NM)
from labtoolbox.semtexture.texture import CLASS_ORDERED, CLASS_DISORDERED, CLASS_BARE

DATE = datetime.date.today()
DATE_EN = f"{DATE.day} {DATE.strftime('%B %Y')}"
NAVY = RGBColor(0x1F, 0x2A, 0x44)
GREY = RGBColor(0x55, 0x5B, 0x66)
M = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


# --------------------------------------------------------------------- docx bits
def mr(t):
    return f'<m:r><m:t xml:space="preserve">{t}</m:t></m:r>'


def mu(t):
    return f'<m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t xml:space="preserve">{t}</m:t></m:r>'


def msub(b, s):
    return f'<m:sSub><m:e>{b}</m:e><m:sub>{s}</m:sub></m:sSub>'


def msup(b, s):
    return f'<m:sSup><m:e>{b}</m:e><m:sup>{s}</m:sup></m:sSup>'


def mfrac(n, d):
    return f'<m:f><m:num>{n}</m:num><m:den>{d}</m:den></m:f>'


def mrad(x):
    return f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{x}</m:e></m:rad>'


def mdelim(x, beg="(", end=")"):
    return (f'<m:d><m:dPr><m:begChr m:val="{beg}"/><m:endChr m:val="{end}"/></m:dPr>'
            f'<m:e>{x}</m:e></m:d>')


def add_eq(doc, inner):
    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(5)
    p._p.append(parse_xml(f'<m:oMathPara {M}><m:oMath>{inner}</m:oMath></m:oMathPara>'))
    return p


def _italic_runs(text):
    import re
    pos = 0
    for m in re.finditer(r"(?<![*\w])\*(?!\*)([^*\n]+?)\*(?![*\w])", text):
        if m.start() > pos:
            yield text[pos:m.start()], False
        yield m.group(1), True
        pos = m.end()
    if pos < len(text):
        yield text[pos:], False


def rich(p, text, size=None, color=None, bold=False, italic=False):
    import re
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if not part:
            continue
        is_bold = part.startswith("**") and part.endswith("**") and len(part) > 4
        body = part[2:-2] if is_bold else part
        for chunk, is_it in _italic_runs(body):
            if not chunk:
                continue
            r = p.add_run(chunk)
            if size:
                r.font.size = size
            if color is not None:
                r.font.color.rgb = color
            if is_bold or bold:
                r.bold = True
            if is_it or italic:
                r.italic = True
    return p


def para(doc, text, size=Pt(10), align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=5):
    p = doc.add_paragraph()
    rich(p, text, size=size)
    p.paragraph_format.alignment = align
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.13
    return p


def head(doc, text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    r = p.add_run(text)
    r.font.color.rgb = NAVY
    r.bold = True
    r.font.size = Pt(13.5 if level == 1 else 11.5)
    p.paragraph_format.space_before = Pt(10 if level == 1 else 7)
    p.paragraph_format.space_after = Pt(3)
    return p


def caption(doc, text):
    p = doc.add_paragraph()
    rich(p, text, size=Pt(8.5), color=GREY)
    p.paragraph_format.space_after = Pt(7)
    return p


def three_line(tbl):
    tblPr = tbl._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for tag, val, sz in (("top", "single", "10"), ("bottom", "single", "10"),
                         ("left", "none", None), ("right", "none", None),
                         ("insideH", "none", None), ("insideV", "none", None)):
        el = OxmlElement(f"w:{tag}")
        el.set(qn("w:val"), val)
        if sz:
            el.set(qn("w:sz"), sz)
        borders.append(el)
    tblPr.append(borders)


def table(doc, header, rows, widths=None, font=Pt(8.2)):
    tbl = doc.add_table(rows=1, cols=len(header))
    for i, h in enumerate(header):
        c = tbl.rows[0].cells[i]
        c.text = ""
        p = c.paragraphs[0]
        r = p.add_run(str(h))
        r.bold = True
        r.font.size = font
        p.paragraph_format.space_after = Pt(1)
    for row in rows:
        cells = tbl.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            r = p.add_run("" if v is None else str(v).replace("**", ""))
            r.font.size = font
            p.paragraph_format.space_after = Pt(1)
    if widths:
        for row in tbl.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    for cell in tbl.rows[-1].cells:
        for p in cell.paragraphs:
            p.paragraph_format.keep_with_next = True
    trPr = tbl.rows[0]._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)
    three_line(tbl)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return tbl


# ------------------------------------------------------------------- figures
def fig_consistency(df, out_png):
    d = df.sort_values(["coupon", "file"]).reset_index(drop=True)
    labels = [f"{r.coupon}:{os.path.splitext(r.file)[0].replace('_e','')}" for r in d.itertuples()]
    x = np.arange(len(d))
    fig, axes = plt.subplots(1, 3, figsize=(11.6, 3.4))
    for ax, (col, ylab, err, scale) in zip(axes, [
            ("period_nm", "period Λ (nm)", "period_sd_nm", 1.0),
            ("theta_deg", "orientation θ (deg)", None, 1.0),
            ("ordered_frac", "ordered area (%)", None, 100.0)]):
        y = d[col].to_numpy(float) * scale
        if err:
            ax.errorbar(x, y, yerr=d[err].to_numpy(float), fmt="o", ms=5, capsize=2.5,
                        lw=0.9, color="#2f6b4f")
        else:
            ax.plot(x, y, "o", ms=5, color="#2f6b4f")
        m = float(np.nanmean(y))
        ax.axhline(m, ls=":", lw=0.9, color="#2f6b4f", alpha=0.8)
        ax.set_ylabel(ylab, fontsize=8.5)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=90, fontsize=6.4)
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(alpha=0.25, lw=0.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[2].set_ylim(-5, 105)
    axes[0].set_xlabel("field", fontsize=8.5)
    axes[1].set_xlabel("field", fontsize=8.5)
    axes[2].set_xlabel("field", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(out_png, dpi=250, bbox_inches="tight")
    plt.close(fig)
    return out_png


def fig_tile_hist(til, out_png):
    fig, ax = plt.subplots(figsize=(5.6, 3.1))
    lam = til["period_nm"].dropna()
    ax.hist(lam, bins=np.arange(180, 900, 15), color="#3b6ea8", alpha=0.8)
    med = float(np.median(lam)) if len(lam) else np.nan
    if np.isfinite(med):
        ax.axvline(med, ls="--", lw=1.0, color="#c0392b", label=f"median {med:.0f} nm")
        ax.legend(fontsize=7.5, frameon=False)
    ax.set_xlabel("local period per window (nm)", fontsize=8.5)
    ax.set_ylabel("window count", fontsize=8.5)
    ax.tick_params(labelsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=250, bbox_inches="tight")
    plt.close(fig)
    return out_png


def fig_maps(res_list, out_png, n_max=4):
    picks = res_list[:n_max]
    cmap = ListedColormap(["#6e6e6e", "#d62728", "#ff9f1a", "#2ca02c"])
    norm = BoundaryNorm([-1.5, -0.5, 0.5, 1.5, 2.5], cmap.N)
    fig, axes = plt.subplots(1, len(picks), figsize=(3.2 * len(picks), 3.0))
    if len(picks) == 1:
        axes = [axes]
    for ax, (path, r) in zip(axes, picks):
        canvas = np.full((int(r["img_h_px"]), int(r["img_w_px"])), 2.0)
        t_px = int(r["tile_px"])
        for t in r["_tiles"]:
            canvas[t["y0"]:t["y0"] + t_px, t["x0"]:t["x0"] + t_px] = t["class"]
        ax.imshow(canvas, cmap=cmap, norm=norm, interpolation="nearest")
        ax.set_title(f"{os.path.splitext(r['file'])[0]}\nΛ {r['period_nm']:.0f} nm · "
                     f"ordered {100*r['ordered_frac']:.0f} %", fontsize=7.5)
        ax.axis("off")
    handles = [Patch(color="#2ca02c", label="ordered"), Patch(color="#ff9f1a", label="disordered"),
               Patch(color="#d62728", label="bare"), Patch(color="#6e6e6e", label="excluded")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=7.5,
               bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(out_png, dpi=250, bbox_inches="tight")
    plt.close(fig)
    return out_png


def fig_pair(orig_path, ann_png, out_png, title=""):
    """Left = original micrograph, right = annotated copy, same scale."""
    a = _load_gray(orig_path)
    from PIL import Image
    # the marked panel keeps its colour: in greyscale the orange/pink tints collapse to a
    # faint grey shading and the whole point of the appendix is lost in print
    b = np.array(Image.open(ann_png).convert("RGB"))
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.4))
    axes[0].imshow(a, cmap="gray", vmin=np.percentile(a, 1), vmax=np.percentile(a, 99.5))
    axes[0].set_title("original", fontsize=8.5)
    axes[1].imshow(b)
    axes[1].set_title("marked (orange = off-spec texture)", fontsize=8.5)
    for ax in axes:
        ax.axis("off")
    if title:
        fig.suptitle(title, fontsize=10.5, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_png, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_png


# ------------------------------------------------------------------- builder
def build(folder, report_dir=None, title=None, tile_um=DEFAULT_TILE_UM,
          pixel_nm=None, verbose=True, mixed=False, coupon=None, keep_pairs=False):
    folder = os.path.abspath(folder)
    report_dir = os.path.abspath(report_dir or folder)
    name = os.path.basename(folder.rstrip("\\/")) or "sample"
    work = os.path.join(report_dir, "QC_report")
    figdir = os.path.join(work, "figures")
    anndir = os.path.join(work, "annotated")
    pdir = os.path.join(work, "pairs")
    plaindir = os.path.join(pdir, "_marked_plain")
    for d in (work, figdir, anndir, pdir, plaindir):
        os.makedirs(d, exist_ok=True)

    items = _discover(folder)
    if not items:
        raise FileNotFoundError(f"no images under {folder}")

    rows, res_by_path, res_list = [], {}, []
    for grp, path in items:
        try:
            r = analyse_image(path, pixel_nm=pixel_nm, tile_um=tile_um)
        except Exception as exc:
            print(f"  !! {os.path.basename(path)}: {exc}")
            continue
        r["group"] = grp
        r["path"] = path
        if coupon:                      # one coupon per folder: file names are field ids
            r["coupon"] = str(coupon)
        res_by_path[path] = r
        res_list.append((path, r))
        rows.append({k: v for k, v in r.items() if not k.startswith("_")})
        if verbose:
            print(f"  {os.path.basename(path):16s} Λ={r['period_nm']:7.1f}  θ={r['theta_deg']:6.1f}"
                  f"  C={r['coherence']:.3f}  ordered={100*r['ordered_frac']:5.1f} %"
                  f"  bare={100*r['bare_frac']:4.1f} %")

    df = pd.DataFrame(rows).sort_values(["coupon", "file"]).reset_index(drop=True)
    df.drop(columns=["path"], errors="ignore").to_csv(os.path.join(work, "field_metrics.csv"),
                                                      index=False, encoding="utf-8-sig")

    # annotated copies + pairs
    annotate_folder(folder, anndir, tile_um=tile_um, pixel_nm=pixel_nm,
                    results=res_by_path, verbose=False)
    pairs = []
    for path, r in res_list:
        stem = os.path.splitext(os.path.basename(path))[0]
        ann = os.path.join(anndir, stem + "_quality.png")
        if not os.path.exists(ann):
            continue
        # the appendix pair carries no stats box or legend: the caption has the numbers,
        # and stripping them keeps the marked structure readable at print size
        plain = os.path.join(plaindir, stem + "_marked.png")
        annotate_image(path, plain, res=r, label=False)
        pair = fig_pair(path, plain, os.path.join(pdir, stem + "_pair.png"),
                        title=f"{os.path.splitext(os.path.basename(path))[0]}   "
                              f"Λ {r['period_nm']:.0f} nm · θ {r['theta_deg']:.1f}° · "
                              f"ordered {100*r['ordered_frac']:.0f} % · bare {100*r['bare_frac']:.0f} %")
        pairs.append((pair, r))

    til = pd.DataFrame([{**{k: v for k, v in t.items()}, "file": r["file"], "coupon": r["coupon"]}
                        for _p, r in res_list for t in r["_tiles"]])
    if len(til):
        til.to_csv(os.path.join(work, "window_classes.csv"), index=False, encoding="utf-8-sig")

    F1 = fig_consistency(df, os.path.join(figdir, "fig1_consistency.png"))
    F2 = fig_tile_hist(til, os.path.join(figdir, "fig2_window_periods.png"))
    F3 = fig_maps([(p, r) for p, r in res_list], os.path.join(figdir, "fig3_class_maps.png"))

    # ------------------------------------------------------------ statistics
    n_coupons = 1 if mixed else df["coupon"].nunique()
    lam = df["period_nm"].to_numpy(float)
    lam_ok = lam[np.isfinite(lam)]
    th = np.radians(df["theta_deg"].to_numpy(float) * 2.0)
    R = np.abs(np.mean(np.exp(1j * th))) if len(th) else np.nan
    th_sd = float(np.degrees(np.sqrt(max(-2 * np.log(max(R, 1e-12)), 0))) / 2.0) if len(th) else np.nan
    cv = 100.0 * np.nanstd(lam_ok, ddof=1) / np.nanmean(lam_ok) if lam_ok.size > 1 else np.nan
    single = (n_coupons == 1)
    basis = "field-to-field" if single else "coupon-to-coupon"

    # ------------------------------------------------------------ document
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    for s in doc.sections:
        s.top_margin = Cm(2.0); s.bottom_margin = Cm(2.0)
        s.left_margin = Cm(2.2); s.right_margin = Cm(2.2)
        fp = s.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r0 = fp.add_run(f"{name} — processing-quality report   ·   page ")
        r0.font.size = Pt(8); r0.font.color.rgb = GREY
        fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE")
        run = OxmlElement("w:r"); t_el = OxmlElement("w:t"); t_el.text = "1"; run.append(t_el)
        fld.append(run); fp._p.append(fld)

    t = doc.add_paragraph()
    r = t.add_run(title or f"Processing-quality report — {name}")
    r.bold = True; r.font.size = Pt(17); r.font.color.rgb = NAVY
    sub = doc.add_paragraph()
    scope = ("reference set" if mixed else
             f"{n_coupons} coupon{'s' if n_coupons > 1 else ''}")
    r = sub.add_run(f"{len(df)} fields · {scope} · "
                    f"2D-FFT texture analysis with {tile_um:g} µm classification windows")
    r.font.size = Pt(10.5); r.italic = True; r.font.color.rgb = GREY
    meta = doc.add_paragraph()
    px_vals = sorted({round(float(v), 3) for v in df["pixel_nm"]})
    ppw_med = float(df["periods_per_window"].median())
    rich(meta, f"generated {DATE_EN} · LabToolbox module `semtexture` · pixel size "
               + ", ".join(f"{v:g}" for v in px_vals) + " nm/px · "
               f"window {tile_um:g} µm (≈{ppw_med:.1f} ripple periods) · "
               f"marked copies in `QC_report/annotated/`", size=Pt(8.5), color=GREY)
    doc.add_paragraph()

    head(doc, "Summary", 1)
    worst = df.loc[df["ordered_frac"].idxmin()] if len(df) else None
    para(doc,
         f"The ripple period of this set is **{np.nanmean(lam_ok):.1f} ± {np.nanstd(lam_ok, ddof=1):.1f} nm** "
         f"({basis} CV {cv:.2f} %), the orientation **{df['theta_deg'].mean():.1f}°** with a circular SD of "
         f"{th_sd:.1f}°, and the mean coherence **{df['coherence'].mean():.3f}**. "
         f"Of the analysed area **{100*df['ordered_frac'].mean():.1f} % satisfies the texture acceptance "
         f"test**, {100*df['disordered_frac'].mean():.1f} % carries a texture that misses it and "
         f"{100*df['bare_frac'].mean():.1f} % shows no periodic texture at all; the weakest field is "
         f"**{worst['file'] if worst is not None else '—'}** at {100*worst['ordered_frac']:.0f} % ordered.")
    # surfaces that carry texture but no single period do not fit the grating criterion;
    # say so rather than letting a low ordered fraction read as "unprocessed area"
    if not mixed and df["ordered_frac"].mean() < 0.5 and df["bare_frac"].mean() < 0.10:
        para(doc,
             "**Interpretation note.** Only "
             f"{100*df['ordered_frac'].mean():.0f} % of the area passes the *grating* test, yet only "
             f"{100*df['bare_frac'].mean():.1f} % is bare: the surface carries a directional texture "
             "almost everywhere, but it does not repeat with one period and one orientation over a "
             "2 µm window. The low ordered fraction therefore describes the **morphology** (short-range "
             "order, patchy or multi-directional) rather than badly processed area. For this coupon the "
             "numbers to quote are the fraction with directional texture "
             f"({100*(df['ordered_frac'].mean()+df['disordered_frac'].mean()):.0f} %) together with the "
             "local-period distribution of Figure 2.")
    if mixed:
        para(doc, "This folder is a **reference set**: it mixes structure types (LIPSS, nanopillar and "
                  "polished areas, at two magnifications), so the numbers describe each field rather than a "
                  "reproducibility figure. The per-field table and the marked copies are the useful output; "
                  "the spread across this set is not a process statistic.")
    elif single:
        para(doc, "Because the folder holds a single coupon, the spread quoted above is the **field-to-field "
                  "repeatability inside that coupon** (how uniform the treated area is), not a "
                  "coupon-to-coupon reproducibility.")
    else:
        para(doc, f"The folder holds {n_coupons} coupons, so the spread is a **coupon-to-coupon "
                  f"reproducibility** figure; the field-to-field spread is in Figure 1.")

    head(doc, "1  What was measured", 1)
    para(doc,
         "Every image is analysed on the same route: the bottom information band is removed, the "
         "illumination envelope is high-pass filtered, and the ripple period is read from the "
         "autocorrelation of the intensity profile taken **along the ripple normal** (the strongest peak of "
         "the 2D spectrum is *not* used — on 3 k images it lands on the illumination envelope). Orientation "
         "and coherence come from the structure tensor:")
    add_eq(doc, mr("C = ") + mfrac(msub(mr("λ"), mr("1")) + mr(" − ") + msub(mr("λ"), mr("2")),
                                   msub(mr("λ"), mr("1")) + mr(" + ") + msub(mr("λ"), mr("2"))))
    add_eq(doc, mr("Λ = τ") + msup(mr(""), mr("*")) + mr(" ⋅ Δx,   τ") + msup(mr(""), mr("*")) +
            mr(" = ") + mu("argmax") + mdelim(mr("R(τ)"), "{", "}"))
    para(doc,
         f"Each field is then cut into a non-overlapping grid of **{tile_um:g} µm windows** "
         f"({int(df['tile_px'].median())} px here, ≈{ppw_med:.1f} periods per "
         f"window) and every window is classified as *ordered* (coherence, period and orientation all inside "
         f"the acceptance band, and phase coherence at least 0.55 × the field median), *disordered* (a "
         f"texture is there but off-spec) or *bare* (no periodic texture). The ordered fraction is the area "
         f"of the field that passed; the annotated copies paint exactly that classification.")
    para(doc,
         "Acceptance thresholds, the calibration of both structure types and the full method are documented "
         "once in `SEM-EDX graphics/01_reports_and_metadata/SEM_texture_consistency_report_20261103.pdf`; "
         "this report applies the same settings to one sample folder.")

    head(doc, "2  Results", 1)
    rows_t = []
    for _, r in df.iterrows():
        rows_t.append([os.path.splitext(r["file"])[0], r["coupon"], r["mode"],
                       f"{r['period_nm']:.1f}" if np.isfinite(r["period_nm"]) else "—",
                       f"{r['period_sd_nm']:.1f}" if np.isfinite(r["period_sd_nm"]) else "—",
                       f"{r['theta_deg']:.1f}", f"{r['coherence']:.3f}",
                       f"{100*r['ordered_frac']:.1f}", f"{100*r['disordered_frac']:.1f}",
                       f"{100*r['bare_frac']:.1f}"])
    table(doc, ["field", "coupon", "type", "Λ (nm)", "± (nm)", "θ (°)", "C",
                "ordered %", "disordered %", "bare %"], rows_t,
          widths=[3.1, 1.3, 1.3, 1.5, 1.4, 1.3, 1.2, 1.7, 2.0, 1.5], font=Pt(7.6))
    caption(doc, f"Table 1 — every field in `{name}`. Λ is the period from the profile autocorrelation, "
                 f"± the robust spread of the local periods inside that field.")

    doc.add_picture(F1, width=Cm(16.2))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, "Figure 1 — period (with the within-field spread), orientation and ordered area for every "
                 "field; the dotted lines mark the set mean.")

    doc.add_picture(F2, width=Cm(12.2))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, f"Figure 2 — distribution of the local period over all {len(til)} classification windows "
                 f"of this set. A narrow distribution means the texture repeats with the same spacing "
                 f"everywhere at the {tile_um:g} µm scale.")

    doc.add_picture(F3, width=Cm(16.2))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, "Figure 3 — window classification for the first fields (green ordered / orange disordered / "
                 "red bare / grey excluded).")

    head(doc, "3  Notes and limits", 1)
    for s in [
        f"Absolute period: at 3 k one ripple period is only ~12 px, so the value carries ±4 % from pixel "
        f"sampling alone; the same coupon imaged at 12 k reads ~3 % higher. Use 12 k or AFM when the absolute "
        f"number matters.",
        f"Percentages are **window-size dependent** (a finer window resolves more small defects). Compare "
        f"fields and coupons only within one window size; this report uses {tile_um:g} µm throughout.",
        "Passing the acceptance test means the surface carries the intended periodic texture; it says "
        "nothing about depth, chemistry or crystallinity (those come from AFM, EDX, XRD).",
        "The marked copies are just that — copies. The images in the sample folder are untouched.",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        rich(p, s, size=Pt(9.5))
        p.paragraph_format.space_after = Pt(2)

    head(doc, "Appendix  Original vs marked, field by field", 1)
    para(doc, "Every field of this set, left = the original micrograph, right = the same field with the "
              "poorly-processed windows marked (orange = disordered, pink = bare; no hatching, so the "
              "structure stays visible). Full-resolution copies of the marked images are in "
              "`QC_report/annotated/`.")
    for i, (pair, r) in enumerate(pairs, 1):
        doc.add_picture(pair, width=Cm(16.4))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption(doc, f"A{i} — {os.path.splitext(r['file'])[0]}: ordered {100*r['ordered_frac']:.0f} %, "
                     f"disordered {100*r['disordered_frac']:.0f} %, bare {100*r['bare_frac']:.0f} %.")

    docx_path = os.path.join(report_dir, f"SEM_quality_report_{name}.docx")
    doc.save(docx_path)

    # PDF through Word (copy to an ASCII scratch path first — Word cannot open some OneDrive paths)
    pdf_path = os.path.join(report_dir, f"SEM_quality_report_{name}.pdf")
    try:
        tmp = os.path.join(tempfile.gettempdir(), f"qq_{name}.docx")
        shutil.copy2(docx_path, tmp)
        tmp_pdf = os.path.splitext(tmp)[0] + ".pdf"
        import win32com.client as win32
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        d = word.Documents.Open(tmp)
        d.ExportAsFixedFormat(tmp_pdf, 17)
        d.Close(False)
        word.Quit()
        shutil.copy2(tmp_pdf, pdf_path)
    except Exception as exc:
        print("  !! PDF failed:", exc)

    # the appendix pairs are embedded in the docx; keeping the standalone PNGs would add
    # ~40 MB per sample to OneDrive for nothing
    if not keep_pairs:
        shutil.rmtree(pdir, ignore_errors=True)

    return dict(report_dir=report_dir, docx=docx_path,
                pdf=pdf_path if os.path.exists(pdf_path) else None,
                n_fields=len(df), n_pairs=len(pairs), work=work)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--report-dir", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--tile-um", type=float, default=DEFAULT_TILE_UM, dest="tile_um")
    ap.add_argument("--pixel-nm", type=float, default=None, dest="pixel_nm")
    a = ap.parse_args()
    print(f"== {a.folder}")
    r = build(a.folder, report_dir=a.report_dir, title=a.title, tile_um=a.tile_um,
              pixel_nm=a.pixel_nm)
    print(f"   fields {r['n_fields']}, pairs {r['n_pairs']} -> {r['docx']}")
    if r["pdf"]:
        print(f"   pdf: {r['pdf']}")


if __name__ == "__main__":
    main()
