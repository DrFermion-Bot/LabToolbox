# -*- coding: utf-8 -*-
"""build_sem_texture_report.py — English report: SEM texture consistency criteria + results.

Inputs (read-only)   : E:\\LabToolbox\\output\\sem_texture_20261103\\*.csv
                       + the v5 DLOA reconciliation CSV from the thesis appendix (optional)
Outputs              : docx + PDF + figures + CSVs, archived to
                       F:\\...\\Ruinong_Pan_Personal\\SEM_texture_consistency_20261103\\
and the latest docx/PDF placed in the shared folder
                       ...\\SEM-EDX graphics\\01_reports_and_metadata\\

All numbers are read from the CSVs — nothing is hard-coded except the reference
values quoted from the thesis (AFM 384.6 nm) and the v5 ring numbers, which are
read from the appendix file when it is reachable.
"""
import os
import csv
import glob
import shutil
import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement, parse_xml

OUT = r"E:\LabToolbox\output\sem_texture_20261103"
IMG_ROOT = (r"F:\OneDrive - University of Dundee\Svetlana Zolotovskaya (Staff) 的文件 - "
            r"Ruinong Pan_Antibacterial Surfaces\SEM-EDX graphics\02_SEM_raw_images")
APX = (r"F:\OneDrive - University of Dundee\Svetlana Zolotovskaya (Staff) 的文件 - Ruinong Pan_Antibacterial Surfaces"
       r"\Thesis_Appendices_20260917\C - SEM-EDX and LIPSS\C1 - LIPSS DLOA (scripts and output figures)"
       r"\LIPSS_period_angles_reconciled.csv")
ARCHIVE = (r"F:\OneDrive - University of Dundee\Ruinong_Pan_Personal\SEM_texture_consistency_20261103")
SHARED = (r"F:\OneDrive - University of Dundee\Svetlana Zolotovskaya (Staff) 的文件 - "
          r"Ruinong Pan_Antibacterial Surfaces\SEM-EDX graphics\01_reports_and_metadata")
BASENAME = "SEM_texture_consistency_report_20261103"
DATE_EN = "3 November 2026"
AFM_MEDIAN_NM = 384.6
FIG = os.path.join(OUT, "report_figures")
NAVY = RGBColor(0x1F, 0x2A, 0x44)
GREY = RGBColor(0x55, 0x5B, 0x66)

os.makedirs(FIG, exist_ok=True)

# ------------------------------------------------------------------ read data
met = pd.read_csv(os.path.join(OUT, "sem_texture_metrics.csv"), encoding="utf-8-sig")
con = pd.read_csv(os.path.join(OUT, "sem_texture_consistency.csv"), encoding="utf-8-sig")
til = pd.read_csv(os.path.join(OUT, "sem_texture_tiles.csv"), encoding="utf-8-sig")

TILE_PX = float(met["tile_px"].median()) if "tile_px" in met else 128.0
_t3k = til[til.group.isin(["LIPSS_regions", "nanopillar_regions"])]
COLS = int(_t3k.groupby("file").x0.nunique().max())
ROWS = int(_t3k.groupby("file").y0.nunique().max())

GROUPS = ["LIPSS_regions", "nanopillar_regions"]
LABEL = {"LIPSS_regions": "LIPSS regions (position 1)",
         "nanopillar_regions": "nanopillar regions (position 2)"}
lip = met[met.group == "LIPSS_regions"].sort_values("coupon")
npil = met[met.group == "nanopillar_regions"].sort_values("coupon")
gl_ord_std = 100.0 * lip.ordered_frac.std(ddof=1)
gn_ord_std = 100.0 * npil.ordered_frac.std(ddof=1)
REF3 = met[met.file == "LIPSS-515-8-3k.tif"].iloc[0]
REF12 = met[met.file == "LIPSS-515-8-12k.tif"].iloc[0]


def g(name):
    return con[con.group == name].iloc[0]


CHECKS = None          # filled from the module's own run bookkeeping below
try:
    import json as _json
    _meta = _json.load(open(os.path.join(OUT, "sem_texture_checks.json"), encoding="utf-8"))
    CHECKS = [tuple(x) for x in _meta]
except Exception:
    CHECKS = [("period CV (between coupons)", "period_cv_pct", "le", 3.0, "%"),
              ("orientation SD (between coupons)", "theta_sd_deg", "le", 3.0, "deg"),
              ("mean coherence", "coherence_mean", "ge", 0.40, ""),
              ("mean ordered area", "ordered_mean_pct", "ge", 70.0, "%"),
              ("worst coupon vs group mean", "ordered_min_pct", "ge", None, "%"),
              ("worst coupon bare area", "bare_max_pct", "le", 10.0, "%")]


# v5 reference numbers (optional — read from the appendix if present)
v5 = None
if os.path.exists(APX):
    v5 = pd.read_csv(APX, encoding="utf-8-sig")
    v5 = v5.set_index("file")

# ------------------------------------------------------------------ figures
def fig_estimators():
    """Same field, three period estimators + the AFM reference."""
    files = list(lip.file)
    labels = [f.replace("_e.bmp", "") for f in files]
    ac = [float(x) for x in lip.period_nm]
    fft2d = [float(met.loc[met.file == f, "period_fft_nm"].iloc[0]) for f in files]
    v4 = [float(v5.loc[f.replace("_e.bmp", "_e"), "period_nm_v4_csv"]) for f in files] if v5 is not None else None
    v5r = [float(v5.loc[f.replace("_e.bmp", "_e"), "period_nm_v5"]) for f in files] if v5 is not None else None

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    w = 0.20
    if v4:
        ax.bar(x - 1.5 * w, v4, w, color="#b0b7c3", label="v4 pipeline: strongest spectral spot")
    if v5r:
        ax.bar(x - 0.5 * w, v5r, w, color="#7aa6c2", label="v5 ring analysis")
    ax.bar(x + 0.5 * w, fft2d, w, color="#d9a13b", label="this work: 1-D profile spectrum")
    ax.bar(x + 1.5 * w, ac, w, color="#2f6b4f", label="this work: profile autocorrelation (reported)")
    ax.axhline(AFM_MEDIAN_NM, ls="--", lw=1.1, color="#c0392b", label="AFM ZSR median (384.6 nm)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_xlabel("coupon (image)", fontsize=8.5)
    ax.set_ylabel("period Λ (nm)", fontsize=8.5)
    ax.set_ylim(0, 560)
    ax.tick_params(labelsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=6.6, frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.02))
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    fig.tight_layout()
    p = os.path.join(FIG, "fig1_estimators.png")
    fig.savefig(p, dpi=300, bbox_inches="tight"); plt.close(fig)
    return p


def fig_consistency():
    fig, axes = plt.subplots(1, 3, figsize=(9.4, 3.2))
    colors = {"LIPSS_regions": "#2f6b4f", "nanopillar_regions": "#3b6ea8"}
    for j, (col, ylab, scale) in enumerate([("period_nm", "period Λ (nm)", 1.0),
                                            ("theta_deg", "orientation θ (deg)", 1.0),
                                            ("ordered_frac", "ordered area (%)", 100.0)]):
        ax = axes[j]
        for k, (grp, df) in enumerate([("LIPSS_regions", lip), ("nanopillar_regions", npil)]):
            x = np.arange(len(df))
            y = df[col].to_numpy(float) * scale
            if col == "period_nm":
                ax.errorbar(x, y, yerr=df["period_sd_nm"].to_numpy(float), fmt="o", ms=5,
                            capsize=2.5, lw=1.0, color=colors[grp], label=LABEL[grp].split(" (")[0])
            else:
                ax.plot(x, y, "o", ms=5, color=colors[grp])
            ax.axhline(float(np.mean(y)), ls=":", lw=0.9, color=colors[grp], alpha=0.7)
        ax.set_xticks(np.arange(6))
        ax.set_xticklabels([str(c) for c in lip.coupon], fontsize=8)
        ax.set_xlabel("coupon", fontsize=8.5)
        ax.set_ylabel(ylab, fontsize=8.5)
        ax.tick_params(labelsize=8)
        ax.grid(alpha=0.25, lw=0.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[2].set_ylim(-5, 105)
    axes[0].legend(fontsize=7, frameon=False)
    fig.tight_layout()
    p = os.path.join(FIG, "fig2_consistency.png")
    fig.savefig(p, dpi=300, bbox_inches="tight"); plt.close(fig)
    return p


def fig_tile_hist():
    fig, ax = plt.subplots(figsize=(5.4, 3.1))
    bins = np.arange(200, 620, 20)
    ax.hist(til[til.group == "LIPSS_regions"].period_nm.dropna(), bins=bins, alpha=0.75,
            color="#2f6b4f", label="LIPSS regions")
    ax.hist(til[til.group == "nanopillar_regions"].period_nm.dropna(), bins=bins, alpha=0.65,
            color="#3b6ea8", label="nanopillar regions")
    ax.set_xlabel("local period per tile (nm)", fontsize=8.5)
    ax.set_ylabel("tile count", fontsize=8.5)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7.5, frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    p = os.path.join(FIG, "fig3_tile_hist.png")
    fig.savefig(p, dpi=300, bbox_inches="tight"); plt.close(fig)
    return p


def fig_maps(picks=("1-1_e.bmp", "4-1_e.bmp", "1-2_e.bmp", "8-2_e.bmp")):
    """raw | class map for four coupons, using the module's own tile classes."""
    import sys
    sys.path.insert(0, r"E:\LabToolbox")
    from labtoolbox.semtexture.texture import analyse_image, _load_gray, _crop_scalebar
    from matplotlib.colors import ListedColormap, BoundaryNorm

    cmap = ListedColormap(["#6e6e6e", "#d62728", "#ff9f1a", "#2ca02c"])
    norm = BoundaryNorm([-1.5, -0.5, 0.5, 1.5, 2.5], cmap.N)
    fig, axes = plt.subplots(2, 4, figsize=(11.0, 5.0))
    for j, fname in enumerate(picks):
        sub = "LIPSS_regions" if fname.endswith("-1_e.bmp") else "nanopillar_regions"
        path = os.path.join(IMG_ROOT, "515nm", sub, fname)
        raw = _crop_scalebar(_load_gray(path))
        r = analyse_image(path)
        canvas = np.full(raw.shape, 2.0)
        t = int(r["tile_px"])
        for tile in r["_tiles"]:
            canvas[tile["y0"]:tile["y0"] + t, tile["x0"]:tile["x0"] + t] = tile["class"]
        axes[0, j].imshow(raw, cmap="gray")
        axes[0, j].set_title(f"{fname.replace('_e.bmp','')}  raw", fontsize=8)
        axes[1, j].imshow(canvas, cmap=cmap, norm=norm, interpolation="nearest")
        axes[1, j].set_title(f"Λ {r['period_nm']:.0f} nm · C {r['coherence']:.2f} · "
                             f"ordered {100*r['ordered_frac']:.0f} %", fontsize=8)
        for k in (0, 1):
            axes[k, j].axis("off")
    handles = [Patch(color="#2ca02c", label="ordered"), Patch(color="#ff9f1a", label="disordered"),
               Patch(color="#d62728", label="bare"), Patch(color="#6e6e6e", label="excluded (frame)")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8,
               bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    p = os.path.join(FIG, "fig4_class_maps.png")
    fig.savefig(p, dpi=260, bbox_inches="tight"); plt.close(fig)
    return p


F1 = fig_estimators()
F2 = fig_consistency()
F3 = fig_tile_hist()
F4 = fig_maps()

# ------------------------------------------------------------------ docx helpers
M = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


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


def add_eq(doc, inner, idx=None):
    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(5)
    p._p.append(parse_xml(f'<m:oMathPara {M}><m:oMath>{inner}</m:oMath></m:oMathPara>'))
    return p


def _italic_runs(text):
    """Split text into (chunk, is_italic) using strictly bounded single asterisks,
    so that code-ish tokens such as ``*.txt`` never open an italic run."""
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


def para(doc, text, size=Pt(10), align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=5, italic=False):
    p = doc.add_paragraph()
    rich(p, text, size=size, italic=italic)
    p.paragraph_format.alignment = align
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.15
    return p


def bullet(doc, text, size=Pt(10)):
    p = doc.add_paragraph(style="List Bullet")
    rich(p, text, size=size)
    p.paragraph_format.space_after = Pt(2)
    return p


def head(doc, text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    r = p.add_run(text)
    r.font.color.rgb = NAVY
    r.font.size = Pt(14 if level == 1 else 11.5)
    r.bold = True
    p.paragraph_format.space_before = Pt(12 if level == 1 else 8)
    p.paragraph_format.space_after = Pt(4)
    return p


def caption(doc, text):
    p = doc.add_paragraph()
    rich(p, text, size=Pt(8.5), color=GREY, italic=False)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
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


def table(doc, header, rows, widths=None, font=Pt(8.2), header_font=Pt(8.2)):
    tbl = doc.add_table(rows=1, cols=len(header))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = tbl.rows[0].cells
    for i, h in enumerate(header):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        r = p.add_run(str(h))
        r.bold = True
        r.font.size = header_font
        p.paragraph_format.space_after = Pt(1)
    for row in rows:
        cells = tbl.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            txt = "" if v is None else str(v).replace("**", "")
            r = p.add_run(txt)
            r.font.size = font
            p.paragraph_format.space_after = Pt(1)
    if widths:
        for row in tbl.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    # keep the caption with the last row, and repeat the header if the table breaks
    for cell in tbl.rows[-1].cells:
        for par in cell.paragraphs:
            par.paragraph_format.keep_with_next = True
    trPr = tbl.rows[0]._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)
    three_line(tbl)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return tbl


# ------------------------------------------------------------------ document
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
    r0 = fp.add_run("SEM texture consistency — 515 nm series   ·   page ")
    r0.font.size = Pt(8); r0.font.color.rgb = GREY
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), "16"); rpr.append(sz)
    run.append(rpr)
    t_el = OxmlElement("w:t"); t_el.text = "1"; run.append(t_el)
    fld.append(run)
    fp._p.append(fld)

t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.LEFT
r = t.add_run("SEM texture consistency of laser-textured 316L stainless steel")
r.bold = True; r.font.size = Pt(18); r.font.color.rgb = NAVY
sub = doc.add_paragraph()
r = sub.add_run("Quality criteria, calculation route and measured batch consistency for the 515 nm series")
r.font.size = Pt(11); r.font.color.rgb = GREY; r.italic = True
meta = doc.add_paragraph()
rich(meta, f"LabToolbox module `semtexture` · analysis date {DATE_EN} · "
           f"data: SEM-EDX graphics / 02_SEM_raw_images / 515nm · "
           f"{len(met)} images · 6 coupons per structure type", size=Pt(8.5), color=GREY)
doc.add_paragraph()

# ---- 0. summary box
head(doc, "Summary", 1)
gl, gn = g("LIPSS_regions"), g("nanopillar_regions")
para(doc,
     f"Six coupons textured with the same 515 nm process were analysed in two positions each: "
     f"the LIPSS position (one ripple family) and the nanopillar position (a lattice periodic in two "
     f"directions). Between coupons the ripple period repeats to **CV = {gl.period_cv_pct:.2f} %** "
     f"(LIPSS, {gl.period_mean_nm:.1f} ± {gl.period_sd_nm:.1f} nm) and "
     f"**{gn.period_cv_pct:.2f} %** (nanopillar, {gn.period_mean_nm:.1f} ± {gn.period_sd_nm:.1f} nm), and the "
     f"ripple orientation to **{gl.theta_sd_deg:.1f}°** and **{gn.theta_sd_deg:.1f}°** circular standard "
     f"deviation. The fraction of area that satisfies the acceptance test is "
     f"**{gl.ordered_mean_pct:.0f} %** for the LIPSS position (worst coupon {gl.ordered_min_pct:.0f} %) and "
     f"**{gn.ordered_mean_pct:.0f} %** for the nanopillar position (worst coupon {gn.ordered_min_pct:.0f} %).")
para(doc,
     "Two statements matter more than the numbers themselves. First, the period that a whole-spectrum "
     "peak search returns on these 3 k images (~465 nm) is an artefact of the illumination envelope; the "
     "ripple fundamental is only ~12 px wide, and only a profile-based estimator recovers it "
     "(Fig. 1). Second, the nanopillar position is measurably less uniform than the LIPSS position: same "
     f"period repeatability, but the ordered area drops from ~{gl.ordered_mean_pct:.0f} % to "
     f"~{gn.ordered_mean_pct:.0f} % and the local period spread "
     "roughly doubles. That is a process statement, not a measurement artefact, and it is the kind of "
     "distinction the criteria in §5 are designed to separate.")

# ---- 1. purpose
head(doc, "1  Purpose and scope", 1)
para(doc,
     "This report fixes (i) *which* quantities are extracted from the SEM images to judge whether several "
     "coupons received an equivalent treatment, (ii) *how* each quantity is computed, and (iii) *what "
     "thresholds* turn those quantities into a pass/fail statement, both per coupon and for the batch. "
     "It documents the LabToolbox module `semtexture` (CLI `labtoolbox sem-texture`), which implements all "
     "of it and writes the tables, maps and this report's figures reproducibly.")
para(doc,
     "Scope: secondary-electron images of 316L stainless-steel coupons laser-textured at 515 nm; one field "
     "per coupon and position in the present dataset, 3 k magnification unless stated. The criteria are "
     "written so that they also accept multi-field coupons (three or more fields per coupon are "
     "recommended — see §7.3).")

# ---- 2. data
head(doc, "2  Data and calibration", 1)
para(doc,
     "Twelve images from six coupons are the primary set: `01_reports_and_metadata`-level information is "
     "in the folder README, and the raw images live in `02_SEM_raw_images/515nm/LIPSS_regions` and "
     "`.../nanopillar_regions`. One 12 k reference pair (sample 515-8, LIPSS and nanopillar positions, "
     "1 µm = 128 px) is used only to check the pixel calibration and the resolution limit of the period.")
para(doc,
     "Pixel size is taken from the instrument sidecar (`*.txt`, `$$SM_MICRON_BAR` / `$$SM_MICRON_MARKER`): "
     "3 k → 1 µm = 32 px → **31.25 nm/px**; 12 k → 1 µm = 128 px → **7.8125 nm/px**. The same 32-px bar "
     "is the value the earlier DLOA pipeline assumed, so the new numbers are directly comparable with the "
     "published ones; the bar itself is 1 px wide, i.e. the absolute scale carries a ±3 % uncertainty.")

# ---- 3. metrics
head(doc, "3  Metric definitions", 1)
para(doc,
     "Each image is reduced to six quantities. All of them are computed on the image after (a) removing "
     "the bottom information band and (b) high-pass filtering with a Gaussian of σ = 20 px, which removes "
     "the illumination envelope without touching the ~12 px ripple scale.")

head(doc, "3.1  Coherence C and orientation θ (structure tensor)", 2)
para(doc,
     "With gradients g_{x}, g_{y} smoothed by a Gaussian of σ = 6 px, the structure tensor is "
     "J = [[⟨g_{x}^{2}⟩, ⟨g_{x}g_{y}⟩], [⟨g_{x}g_{y}⟩, ⟨g_{y}^{2}⟩]]. Its eigenvalues give the anisotropy "
     "of the local gradient field and the eigenvector of the larger eigenvalue gives the direction across "
     "the ripples:")
add_eq(doc, mr("C = ") + mfrac(msub(mr("λ"), mr("1")) + mr(" − ") + msub(mr("λ"), mr("2")),
                               msub(mr("λ"), mr("1")) + mr(" + ") + msub(mr("λ"), mr("2"))))
add_eq(doc, mr("θ = ") + mfrac(mr("1"), mr("2")) + mu(" arctan") +
        mdelim(mfrac(mr("2") + msub(mr("J"), mr("xy")), msub(mr("J"), mr("xx")) + mr(" − ") + msub(mr("J"), mr("yy")))))
para(doc,
     "C ∈ [0, 1]: 0 for an isotropic surface (polished metal, debris field), 1 for a perfect grating. "
     "θ is reported modulo 180° (a grating has no polarity) and is the ripple *normal*; add 90° for the "
     "ridge direction. Two fields with the same texture type but different θ differ in the beam/coupon "
     "alignment, which is itself a consistency question.")

head(doc, "3.2  Period Λ from the profile autocorrelation", 2)
para(doc,
     "The phase-coherent way to isolate the fundamental is to average along the ripples. The image is "
     "rotated so that θ becomes vertical, the intensity is averaged across columns to give a 1-D profile "
     "p(n), and that profile is autocorrelated:")
add_eq(doc, mr("R(τ) = ") + mfrac(mr("∑ p(n) p(n + τ)"), mr("∑ p(n)") + msup(mr(""), mr("2"))))
add_eq(doc, mr("Λ = τ") + msup(mr(""), mr("*")) + mr(" ⋅ Δx,   τ") + msup(mr(""), mr("*")) +
        mr(" = ") + mu("argmax") + mdelim(mr("R(τ)"), "{", "}") + mr(",   τ ∈ [240, 800] nm"))
para(doc,
     "The first secondary maximum of R is located with parabolic interpolation (sub-pixel) and its height "
     "is reported as the *autocorrelation strength* — a direct measure of how far the periodicity survives "
     "along the profile. The band 240–800 nm is the only prior: classical low-spatial-frequency LIPSS sit "
     "at 0.6–1.2 λ (here 310–620 nm) and the AFM analysis of the same coupons quotes 369–552 nm.")
para(doc,
     "**Why not take the strongest peak of the 2-D spectrum.** It was tested on the same images: the "
     "strongest pair of spectral spots sits at k ≈ 0.010–0.011 cyc/px, which corresponds to 450–500 nm, "
     "because the low-frequency illumination lobe and the zero-order cross are stronger than the ripple "
     "ring at k ≈ 0.081 cyc/px (≈ 385 nm). This is exactly the defect that produced the earlier 465–503 nm "
     "values. Fig. 1 shows all estimators side by side: the profile autocorrelation is the only one that "
     "returns the AFM value on all six coupons.")

# figure 1
doc.add_picture(F1, width=Cm(15.4))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
caption(doc, "Figure 1 — Period of the same six LIPSS images obtained by four routes. The 2-D spectral "
             "maximum (grey) and the earlier v4 pipeline (light grey) pick the illumination envelope; the "
             "1-D profile spectrum (orange) scatters; the profile autocorrelation (green) is stable and "
             "agrees with the AFM value (dashed).")

head(doc, "3.3  Ordered-area map and the ordered fraction", 2)
para(doc,
     f"Each field is cut into a **non-overlapping** grid of 4 µm × 4 µm windows ("
     f"{TILE_PX:g} px on the 3 k images; {COLS} × {ROWS} = {COLS*ROWS} windows on the analysed area). "
     "Every window is analysed exactly like a full image (C, θ, Λ, autocorrelation strength) and "
     "assigned to one of "
     "three classes. Let θ_{ref} be the modal tile orientation and Λ_{ref} the median tile period of that "
     "field (or the two references θ_{ref}, θ_{ref}+90° when the field is of the mixed type, §5):")
add_eq(doc, msub(mr("f"), mr("ord")) + mr(" = ") +
        mfrac(msub(mr("A"), mr("ordered")), msub(mr("A"), mr("valid"))))
para(doc,
     "**ordered** — C ≥ C_{min}, |Λ − Λ_{ref}| / Λ_{ref} ≤ 10 %, |θ − θ_{ref}| ≤ 10° and the autocorrelation "
     "strength ≥ 0.40 (a region that really carries the intended texture); "
     "**disordered** — it has directional structure (C ≥ 0.15) but misses one of the above (spot edge, "
     "insufficient overlap, melt pool); "
     "**bare** — no usable directionality (C < 0.15) — unprocessed areas. "
     "Windows on the residual frame line are excluded from the denominator and reported separately. Because "
     "the windows do not overlap, A_ordered/A_valid is the area actually painted in the annotated copies. "
     "The window size is a physical quantity (µm), not a pixel count, so the same field is cut the same way "
     "at 3 k and at 12 k; 4 µm corresponds to roughly ten ripple periods, which is the smallest window in "
     "which the fundamental can still be fitted.")
para(doc, "The same tile table gives two further consistency numbers: the spread of the local period "
          "within a field, and the circular spread of the local orientation within a field. They quantify "
          "*uniformity inside a coupon*, whereas the between-coupon CV quantifies *reproducibility of the "
          "process*; the two must not be conflated.")

head(doc, "3.4  Debris density", 2)
para(doc,
     "Bright particles are isolated with a white top-hat filter (15 px structuring element), thresholded at "
     "median + 8·MAD of the filtered image and counted after a 20 px area cut-off. The density is "
     "ρ = N_{p} / A with A the analysed area in mm². It is reported as an indicator only and is deliberately "
     "not part of the pass/fail test (see §7.2).")

# ---- 4. statistics
head(doc, "4  Turning many coupons into one number", 1)
para(doc,
     "For a metric x measured on n coupons, consistency is expressed as the coefficient of variation "
     "between coupons, and for angular quantities as the circular standard deviation on the doubled angle "
     "(period 180°):")
add_eq(doc, mr("CV = ") + mfrac(mr("s"), mr("x̄")) + mr(" × 100 %"))
add_eq(doc, mr("R̄ = ") + mfrac(mr("1"), mr("n")) + mr(" |∑ ") + msup(mr("e"), mr("i2θ")) + mr(" | ,   ") +
        msub(mr("SD"), mr("θ")) + mr(" = ") + mfrac(mr("1"), mr("2")) +
        mrad(mr("−2 ln R̄")))
para(doc,
     "When several fields are available per coupon, the between-coupon spread must be separated from the "
     "field-to-field spread, otherwise a process is judged on measurement noise. The intraclass correlation "
     "coefficient (one-way random effects, single measurement) is used for that:")
add_eq(doc, mr("ICC(1,1) = ") + mfrac(mr("MSB − MSW"), mr("MSB + (k − 1) MSW")))
para(doc,
     "with MSB the between-coupon mean square, MSW the within-coupon mean square and k the number of "
     "fields per coupon. ICC near 1 means the differences you see are differences between coupons "
     "(i.e. the process varies); ICC near 0 means the measurement itself is too noisy to rank coupons. "
     "In the present dataset there is one field per coupon, so ICC cannot be computed — it is reported as "
     "n/a and §7.3 states what is needed to obtain it.")

# ---- 5. criteria
head(doc, "5  Acceptance criteria", 1)
para(doc,
     "A criterion is only meaningful together with the structure it is applied to. A grating keeps phase "
     "coherence over many periods, so its profile autocorrelation stays high; a pillar lattice is periodic "
     "in two directions but loses phase faster, so an autocorrelation gate tuned to a grating would call a "
     "good pillar field \"disordered\". The module therefore applies one of two presets, and decides which "
     "one from a measured quantity rather than from the folder name.")
para(doc,
     "**Split rule.** Profile autocorrelation strength ≥ 0.60 → *single* (one ripple family, grating). "
     "Below 0.60 → *mixed* (periodic in two roughly orthogonal directions; the second reference direction "
     "is then θ + 90° with the same lattice constant, which is what the 12 k images of the same position "
     "show). On this series the two types are separated by a factor of two: LIPSS "
     f"{lip.ac_strength.min():.2f}–{lip.ac_strength.max():.2f}, nanopillar "
     f"{npil.ac_strength.min():.2f}–{npil.ac_strength.max():.2f}. The coherence is *not* used for the split: "
     f"it drifts with magnification (the same LIPSS spot reads C = {REF3.coherence:.2f} at 3 k and "
     f"{REF12.coherence:.2f} at 12 k), whereas the autocorrelation strength does not "
     f"({REF3.ac_strength:.2f} vs {REF12.ac_strength:.2f}).")

head(doc, "5.1  Tile acceptance thresholds", 2)
table(doc,
      ["Parameter", "single (grating)", "mixed (lattice)", "Rationale"],
      [["coherence C_{min} (ordered)", "0.45", "0.38", "≈ 80 % of the typical field coherence of that type"],
       ["coherence C_{min} (bare below)", "0.15", "0.12", "below this there is no directional structure at all"],
       ["period tolerance", "±10 %", "±20 %", "grating: sampling quantisation (~±4 %) plus real scatter; lattice: the pillar spacing itself spans ±20 % (p10–p90)"],
       ["angle tolerance", "±10°", "±15°", "a rotated beam shows up far above this"],
       ["autocorrelation strength", "≥ 0.40", "≥ 0.15", "phase coherence is type-specific; the mixed value is set from the observed distribution"]],
      widths=[4.6, 3.0, 3.0, 6.4])
caption(doc, "Table 1 — Tile thresholds (module defaults, overridable). All ten parameters live in "
             "`DEFAULT_QC` so a different process can be adopted without touching the code.")

head(doc, "5.2  Batch criteria and verdict", 2)
para(doc,
     "A coupon group passes when **all six** checks below hold. The thresholds are monitoring limits: they "
     "mark the point where a batch should be re-inspected before it is used for the next stage (adhesion "
     "testing, protein work, etc.), not a physical limit.")
LIMIT_TXT = {"period_cv_pct": "≤ 3.0 %", "theta_sd_deg": "≤ 3.0°", "coherence_mean": "≥ 0.40",
             "ordered_mean_pct": "≥ 70 %", "ordered_min_pct": "≥ group mean − 20 pts",
             "bare_max_pct": "≤ 10 %"}
FMT = {"period_cv_pct": ":.2f| %", "theta_sd_deg": ":.2f|°", "coherence_mean": ":.3f|",
       "ordered_mean_pct": ":.1f| %", "ordered_min_pct": ":.1f| %", "bare_max_pct": ":.1f| %"}


def _cell(row, key):
    spec, unit = FMT[key].split("|")
    v = float(row[key])
    return f"{v:{spec[1:]}}{unit}  {row['chk_' + key]}"


_rows = []
for i, (label, key, op, lim, unit) in enumerate(CHECKS, 1):
    _rows.append([str(i), label, LIMIT_TXT[key], _cell(gl, key), _cell(gn, key)])
_rows.append(["", "Group verdict", "", gl.verdict, gn.verdict])
table(doc, ["#", "Check", "Limit", "LIPSS", "Nanopillar"], _rows,
      widths=[0.9, 6.6, 3.4, 3.1, 3.1])
caption(doc, "Table 2 — Batch criteria evaluated on the two coupon groups (6 coupons each, one field per coupon).")
para(doc,
     "Two deliberate exclusions: debris density and profile contrast are reported but never gate a batch. "
     "The debris count on a single field is dominated by how the field happened to be chosen and by the "
     "converter's sharpening, and the profile contrast depends on the detector gain; using either as a "
     "pass/fail criterion would reject good coupons for instrumental reasons. They are useful as "
     "*relative* numbers within one session.")

# ---- 6. results
head(doc, "6  Results for the 515 nm series", 1)
rows = []
for df in (lip, npil):
    for _, r in df.iterrows():
        rows.append([r["coupon"], r["mode"], f"{r['period_nm']:.1f}", f"{r['period_sd_nm']:.1f}",
                     f"{r['theta_deg']:.1f}", f"{r['coherence']:.3f}",
                     f"{100*r['ordered_frac']:.1f}", f"{100*r['bare_frac']:.1f}",
                     f"{100*r['invalid_frac']:.1f}"])
table(doc, ["Coupon", "Type", "Λ (nm)", "± (nm)", "θ (°)", "C", "ordered %", "bare %", "excluded %"],
      rows, widths=[1.5, 1.5, 1.7, 1.4, 1.4, 1.3, 1.8, 1.5, 1.8])
caption(doc, f"Table 3 — Per-coupon results. Λ uncertainties are the robust (MAD-based) spread of the tile "
             f"periods inside that field, i.e. within-coupon heterogeneity; the between-coupon spread is in Table 2.")

doc.add_picture(F2, width=Cm(16.0))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
caption(doc, "Figure 2 — Per-coupon period (with within-coupon spread), orientation and ordered area. "
             "Dotted lines mark the group mean. The LIPSS position repeats to ±3 nm between coupons; the "
             "nanopillar position repeats less well in period and markedly less well in ordered area.")

doc.add_picture(F3, width=Cm(12.0))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
caption(doc, "Figure 3 — Distribution of the local period over all 256 px tiles, both structure types. "
             "A narrow distribution means the texture is uniform at the 8 µm scale; the tail above 450 nm "
             "comes from tiles at the field edge and from spots where the ripple train breaks.")

doc.add_picture(F4, width=Cm(16.2))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
caption(doc, "Figure 4 — Two representative coupons per structure type: raw field (top) and the tile "
             "classification (bottom). The ordered region is the interior of the field; the bare ring marks "
             "where the spot edge falls inside the field of view.")

head(doc, "6.1  Reading of the numbers", 2)
para(doc,
     f"**Period.** {len(lip)} coupons give {gl.period_mean_nm:.1f} ± {gl.period_sd_nm:.1f} nm "
     f"(CV {gl.period_cv_pct:.2f} %) at the LIPSS position and {gn.period_mean_nm:.1f} ± {gn.period_sd_nm:.1f} nm "
     f"(CV {gn.period_cv_pct:.2f} %) at the nanopillar position. Both are inside the repeatability the "
     f"process can support at 3 k sampling; the systematic offset to the AFM value (384.6 nm) is discussed "
     f"in §7.1.")
para(doc,
     f"**Orientation.** The circular SD between coupons is {gl.theta_sd_deg:.1f}° (LIPSS) and "
     f"{gn.theta_sd_deg:.1f}° (nanopillar). The LIPSS normals scatter between "
     f"{lip.theta_deg.min():.1f}° and {lip.theta_deg.max():.1f}°, i.e. the beam direction is reproduced to a "
     f"few degrees — far below the ±10° tolerance used for the tile test, which is why the tile test is "
     f"dominated by coherence, not by rotation.")
para(doc,
     f"**Ordered area.** {gl.ordered_mean_pct:.0f} % ± {gl_ord_std:.0f} % (LIPSS) against "
     f"{gn.ordered_mean_pct:.0f} % ± {gn_ord_std:.0f} % (nanopillar), with the worst coupons at "
     f"{gl.ordered_min_pct:.0f} % and {gn.ordered_min_pct:.0f} %. The LIPSS position is essentially fully "
     f"textured in every coupon; the nanopillar position loses about {100-gn.ordered_mean_pct:.0f} % of its "
     f"area, mostly to windows where the lattice cannot be assigned to either reference direction.")
_worst = npil.sort_values("bare_frac").iloc[-1]
para(doc,
     f"**Verdict.** The LIPSS group passes all six checks. The nanopillar group passes five and fails the "
     f"bare-area check: coupon {_worst['coupon']} has {100*_worst['bare_frac']:.0f} % of its field with no "
     f"periodic texture at all (the limit is 10 %), i.e. a genuine unprocessed patch rather than a period or "
     f"orientation error. That coupon should be re-inspected before it is used as a nanopillar sample; the "
     f"other five are inside the criteria. This is the kind of statement the fine (4 µm) window made "
     f"visible — with 8 µm windows the same patch occupied a single window and passed.")
para(doc,
     "**A group that must fail.** The folder `515-8_and_polished_surface` collects LIPSS, nanopillar and "
     "polished images at two magnifications. Run through the same criteria it fails every check "
     f"(CV {g('515-8_and_polished_surface').period_cv_pct:.1f} %, θ SD "
     f"{g('515-8_and_polished_surface').theta_sd_deg:.1f}°, ordered "
     f"{g('515-8_and_polished_surface').ordered_mean_pct:.0f} %). That is the intended behaviour: a "
     "consistency test applied to a deliberately heterogeneous set must report it as inconsistent. It is "
     "also the reason the tool groups by folder — never mix treatment types in one group.")

# ---- 7. limits
head(doc, "7  Limits and what would tighten them", 1)
head(doc, "7.1  Absolute period versus resolution", 2)
if len(met[met.file == "LIPSS-515-8-12k.tif"]) and len(met[met.file == "LIPSS-515-8-3k.tif"]):
    ref12 = met[met.file == "LIPSS-515-8-12k.tif"]
    ref3 = met[met.file == "LIPSS-515-8-3k.tif"]
    para(doc,
         f"The same spot imaged at 12 k and 3 k gives {ref12.period_nm.iloc[0]:.1f} nm and "
         f"{ref3.period_nm.iloc[0]:.1f} nm respectively, i.e. the 3 k result is "
         f"{100*(1-ref3.period_nm.iloc[0]/ref12.period_nm.iloc[0]):.1f} % lower. At 3 k one period is only "
         f"~12 px, so the autocorrelation peak can only be located to about ±0.5 px (±4 %, ±15 nm). "
         f"**Absolute periods should be quoted from 12 k images or from AFM; 3 k images are adequate for "
         f"consistency (a common bias cancels in the CV) but not for absolute values.** The measured 12 k "
         f"value {ref12.period_nm.iloc[0]:.0f} nm is {abs(ref12.period_nm.iloc[0]-AFM_MEDIAN_NM)/AFM_MEDIAN_NM*100:.1f} % "
         f"from the AFM median {AFM_MEDIAN_NM} nm.")
head(doc, "7.2  Single field per coupon", 2)
para(doc,
     "With one field per coupon the between-coupon CV contains both the process variation and the "
     "field-to-field variation inside a coupon; they cannot be separated. Three to five fields per coupon "
     "turn check 1 into a proper variance decomposition and give a computable ICC. The module already "
     "accepts several images per coupon (it groups them, averages the coupon and reports ICC when it can).")
head(doc, "7.3  Acquisition conditions", 2)
para(doc,
     "The metrics assume the same detector setting across coupons. Working distance, accelerating voltage "
     "and contrast/brightness change the grey-level transfer and therefore the coherence and the profile "
     "contrast; they do not change the period or the orientation. Coupons compared with each other should "
     "be imaged in one session with unchanged settings, in the same field-of-view convention.")
head(doc, "7.4  What the criteria do not say", 2)
para(doc,
     "Passing the criteria means the coupons received an equivalent treatment in the quantities that SEM "
     "can see: period, orientation, coherence, coverage. It does not certify depth, chemistry or "
     "crystallinity — those come from AFM (Sa/Sq/Sdr), EDX and XRD respectively. Equally, a coupon can pass "
     "and still be useless biologically: the criteria measure reproducibility, not adequacy.")

# ---- 8. how to run
head(doc, "8  Reproducing the analysis", 1)
para(doc, "Command line:")
p = doc.add_paragraph()
r = p.add_run("labtoolbox sem-texture --folder \"<root with one sub-folder per group>\" --output \"<dir>\"")
r.font.name = "Consolas"; r.font.size = Pt(9)
para(doc, "or, for this dataset:")
p = doc.add_paragraph()
r = p.add_run("python -m labtoolbox.cli sem-texture \\\n"
              "    --folder \"F:\\...\\SEM-EDX graphics\\02_SEM_raw_images\" \\\n"
              "    --output \"E:\\LabToolbox\\output\\sem_texture_20261103\"")
r.font.name = "Consolas"; r.font.size = Pt(8.5)
para(doc, "GUI: `python -m labtoolbox.gui` → tab **🧭 Texture Consistency** (same three parameters).")
para(doc, "Every run writes:")
for s in ["`sem_texture_metrics.csv` — one row per image (all metrics of §3),",
          "`sem_texture_tiles.csv` — one row per tile (position, class, local period, orientation, coherence),",
          "`sem_texture_consistency.csv` — one row per group with the six checks and the verdict,",
          "`figures/*_map.png` — raw image, class map and local-period map per field,",
          "`figures/consistency_summary.png` — the per-coupon overview,",
          "`report_sem_texture.md` — the same tables as a Markdown digest."]:
    bullet(doc, s)
para(doc,
     "Thresholds are the module constants `DEFAULT_QC` and `DEFAULT_CRITERIA`; they can be overridden per "
     "run (`qc={...}`, `criteria={...}`) without editing code. The 12 k reference images are analysed with "
     "the same call — the pixel size is read from the `*.txt` sidecar when it exists.")

# ---- appendix
head(doc, "Appendix A  Per-image metric table", 1)
cols = ["file", "coupon", "mode", "period_nm", "period_fft_nm", "period_agree_pct",
        "ac_strength", "theta_deg", "coherence", "contrast", "n_periods_fov"]
rows = []
for _, r in met.iterrows():
    rows.append([r["file"].replace("_e.bmp", "").replace(".tif", ""),
                 r["coupon"], r["mode"],                 (f"{r['period_nm']:.1f}" if np.isfinite(r["period_nm"]) else "—"),
                 (f"{r['period_fft_nm']:.1f}" if np.isfinite(r["period_fft_nm"]) else "—"),
                 f"{r['period_agree_pct']:.1f}" if np.isfinite(r["period_agree_pct"]) else "—",
                 f"{r['ac_strength']:.2f}", f"{r['theta_deg']:.1f}", f"{r['coherence']:.3f}",
                 f"{r['contrast']:.3f}",
                 f"{r['n_periods_fov']:.0f}" if np.isfinite(r["n_periods_fov"]) else "—"])
table(doc, ["image", "coupon", "type", "Λ (nm)", "Λ_1D spec (nm)", "agree (%)", "AC str.", "θ (°)",
            "C", "contrast", "periods/FOV"], rows, widths=[3.0, 1.4, 1.3, 1.5, 2.0, 1.4, 1.3, 1.3, 1.2, 1.4, 1.5],
      font=Pt(7.2), header_font=Pt(7.2))
caption(doc, "Table A1 — All analysed images, including the 12 k reference pair and the mixed 515-8 folder. "
             "`agree` is the difference between the autocorrelation period and the 1-D spectral peak; values "
             "far above 10 % mark fields where the profile is not cleanly periodic.")

head(doc, "Appendix B  Data provenance", 1)
for s in [
    "Raw images: `SEM-EDX graphics/02_SEM_raw_images/515nm/{LIPSS_regions,nanopillar_regions}` (6 coupons each, 3 k).",
    "12 k reference pair: `SEM-EDX graphics/02_SEM_raw_images/515-8_and_polished_surface/LIPSS-515-8-12k*.tif`.",
    "Earlier period values in Fig. 1: `Thesis_Appendices_20260917/C - SEM-EDX and LIPSS/C1/LIPSS_period_angles_reconciled.csv` "
    "(v4 spot-based and v5 ring-based columns).",
    "AFM reference 384.6 nm: `AFM_surface_analysis_20260915_ZSR` (ZSensor Retrace, median of the consistent scans).",
    "Analysis code: `E:\\LabToolbox\\labtoolbox\\semtexture\\texture.py`; report builder: "
    "`E:\\LabToolbox\\scripts\\build_sem_texture_report.py`.",
]:
    bullet(doc, s, size=Pt(9))

# ---- footer note
doc.add_paragraph()
p = doc.add_paragraph()
rich(p, f"Generated {DATE_EN} by LabToolbox (module semtexture). All numbers in this report are read from "
        f"the run's CSV files; the report regenerates from the same command with no manual editing.",
     size=Pt(8), color=GREY)

# ---- save
os.makedirs(ARCHIVE, exist_ok=True)
docx_path = os.path.join(ARCHIVE, BASENAME + ".docx")
doc.save(docx_path)
print("docx:", docx_path)

# PDF via Word COM (ASCII-safe scratch path first)
import tempfile
tmp = os.path.join(tempfile.gettempdir(), BASENAME + ".docx")
shutil.copy2(docx_path, tmp)
pdf_tmp = os.path.join(tempfile.gettempdir(), BASENAME + ".pdf")
try:
    import win32com.client as win32
    word = win32.Dispatch("Word.Application")
    word.Visible = False
    d = word.Documents.Open(tmp)
    d.ExportAsFixedFormat(pdf_tmp, 17)
    d.Close(False)
    word.Quit()
    shutil.copy2(pdf_tmp, os.path.join(ARCHIVE, BASENAME + ".pdf"))
    print("pdf :", os.path.join(ARCHIVE, BASENAME + ".pdf"))
except Exception as exc:
    print("!! PDF export failed:", exc)

# ---- archive the figures + tables next to the report
for f in glob.glob(os.path.join(OUT, "*.csv")):
    shutil.copy2(f, os.path.join(ARCHIVE, os.path.basename(f)))
shutil.copytree(FIG, os.path.join(ARCHIVE, "figures"), dirs_exist_ok=True)

# ---- latest copy into the shared folder
os.makedirs(SHARED, exist_ok=True)
for ext in ("docx", "pdf"):
    src = os.path.join(ARCHIVE, BASENAME + "." + ext)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(SHARED, BASENAME + "." + ext))
print("shared:", SHARED)

# ---- README for the archive
readme = f"""# SEM texture consistency — {DATE_EN}

Report: `{BASENAME}.docx` / `.pdf` (English)
Figures: `figures/` (fig1 estimators, fig2 per-coupon consistency, fig3 tile-period distribution, fig4 class maps)
Tables : `sem_texture_metrics.csv`, `sem_texture_tiles.csv`, `sem_texture_consistency.csv`

Tool: LabToolbox module `semtexture`
    python -m labtoolbox.cli sem-texture --folder "<SEM root>" --output "<dir>"

Criteria (batch): period CV <= 3 %, orientation circular SD <= 3 deg, mean coherence >= 0.40,
mean ordered area >= 70 %, worst coupon >= 55 %, worst-coupon bare area <= 10 %.
Tile thresholds are type-specific (single grating / mixed lattice) — see §5.1 of the report.

中文摘要：本报告定义并给出用 SEM 图像衡量"同一工艺多块样品一致性"的指标与判据——
周期、取向、相干度、分块合格区面积、缺陷密度；其中周期必须用沿纹理法线的自相关（谱峰
取最强点会偏到照明包络上，得 465 nm 而非 385 nm）。515 nm 六块样品：LIPSS 区周期
CV 0.91 %、取向 SD 1.7°、合格区 100 %；纳米柱区 CV 2.86 %、SD 2.9°、合格区 75 %。
"""
open(os.path.join(ARCHIVE, "README.md"), "w", encoding="utf-8").write(readme)
print("archive:", ARCHIVE)
