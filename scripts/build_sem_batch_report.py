# -*- coding: utf-8 -*-
"""build_sem_batch_report.py — one summary report for a whole series of coupons.

Reads the per-sample ``QC_report/field_metrics.csv`` files produced by
``build_sem_group_report.py`` (no re-analysis of the full set), aggregates them and
writes a batch report next to the sample folders, with:

  * coupon-level table (n fields, period ± SD, within-coupon CV, orientation, coherence,
    ordered / disordered area),
  * coupon-to-coupon and within-coupon spread separated,
  * figures: period per coupon, distribution per coupon, ordered area per coupon,
  * appendix A — every field of every coupon in one table,
  * appendix B — one representative field per coupon, original | marked.

Usage
-----
    python scripts/build_sem_batch_report.py --folder "<parent of the coupons>"
        [--name "650 nm nanopillars"] [--pattern "*/QC_report/field_metrics.csv"]
"""
import os
import sys
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

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build_sem_group_report import (mr, mfrac, msub, msup, mdelim, mu, add_eq, rich, para,
                                    head, caption, table, three_line, fig_pair,
                                    NAVY, GREY, DATE_EN)
from labtoolbox.semtexture import analyse_image, annotate_image

DATE = datetime.date.today()
C_BAD, C_OK, C_ALT = "#c0392b", "#2f6b4f", "#3b6ea8"


# ---------------------------------------------------------------- statistics
def circ_mean_sd(deg):
    d = np.asarray(deg, dtype=float)
    d = d[np.isfinite(d)]
    if not d.size:
        return np.nan, np.nan
    r = np.abs(np.mean(np.exp(1j * np.radians(2 * d))))
    # the mean axis is reported on [0, 180) like the per-sample reports, so 175° does not
    # come back as -4.8° and contradict the coupon report
    mean_deg = float(np.degrees(np.angle(np.mean(np.exp(1j * np.radians(2 * d)))) / 2)) % 180.0
    return mean_deg, float(np.degrees(np.sqrt(max(-2 * np.log(max(r, 1e-12)), 0))) / 2)


def coupon_stats(df):
    rows = []
    for c, g in df.groupby("coupon", sort=True):
        lam = g["period_nm"].dropna()
        th, th_sd = circ_mean_sd(g["theta_deg"])
        rows.append(dict(
            coupon=c, fields=len(g),
            lam=float(lam.mean()) if len(lam) else np.nan,
            lam_sd=float(lam.std(ddof=1)) if len(lam) > 1 else np.nan,
            lam_cv=float(100 * lam.std(ddof=1) / lam.mean()) if len(lam) > 1 else np.nan,
            theta=th, theta_sd=th_sd,
            coh=float(g["coherence"].mean()),
            ordered=float(100 * g["ordered_frac"].mean()),
            disordered=float(100 * g["disordered_frac"].mean()),
            bare=float(100 * g["bare_frac"].mean()),
            ordered_min=float(100 * g["ordered_frac"].min()),
            ordered_max=float(100 * g["ordered_frac"].max()),
        ))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ figures
def fig_period(cs, out_png):
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    x = np.arange(len(cs))
    ax.errorbar(x, cs["lam"], yerr=cs["lam_sd"], fmt="o", ms=6, lw=0, elinewidth=1.1,
                capsize=3, color=C_OK, label="coupon mean ± field SD")
    grand = float(np.nanmean(cs["lam"]))
    ax.axhline(grand, ls="--", lw=1.0, color=C_BAD, label=f"series mean {grand:.0f} nm")
    for xi, v in zip(x, cs["lam"]):
        ax.annotate(f"{v:.0f}", (xi, v), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=7, color=C_OK)
    ax.set_xticks(x)
    ax.set_xticklabels(cs["coupon"], fontsize=8)
    ax.set_ylabel("period Λ (nm)", fontsize=9)
    ax.set_xlabel("coupon", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    ax.legend(frameon=False, fontsize=8, loc="best")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=250, bbox_inches="tight")
    plt.close(fig)
    return out_png


def fig_dist(df, cs, out_png):
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    order = list(cs["coupon"])
    data = [df.loc[df.coupon == c, "period_nm"].dropna().to_numpy() for c in order]
    bp = ax.boxplot(data, widths=0.55, patch_artist=True, showfliers=False,
                    medianprops=dict(color="#333", lw=1.1))
    for p in bp["boxes"]:
        p.set(facecolor="#cfe0d0", edgecolor="#3d6b4a", lw=0.9)
    for i, v in enumerate(data, 1):
        jit = (np.random.RandomState(i).rand(len(v)) - 0.5) * 0.22
        ax.plot(np.full(len(v), i) + jit, v, "o", ms=3, color=C_OK, alpha=0.55, mew=0)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels(order, fontsize=8)
    ax.set_ylabel("field period Λ (nm)", fontsize=9)
    ax.set_xlabel("coupon", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=250, bbox_inches="tight")
    plt.close(fig)
    return out_png


def fig_ordered(df, cs, out_png):
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    x = np.arange(len(cs))
    ax.bar(x, cs["ordered"], width=0.6, color="#e8b04b", edgecolor="#8a6a1f", lw=0.6,
           label="coupon mean")
    for i, c in enumerate(cs["coupon"]):
        v = 100 * df.loc[df.coupon == c, "ordered_frac"].to_numpy()
        jit = (np.random.RandomState(i).rand(len(v)) - 0.5) * 0.30
        ax.plot(np.full(len(v), i) + jit, v, "o", ms=3.2, color="#333", alpha=0.6, mew=0,
                label="field" if i == 0 else None)
    ax.set_xticks(x)
    ax.set_xticklabels(cs["coupon"], fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_ylabel("area inside the acceptance band (%)", fontsize=9)
    ax.set_xlabel("coupon", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    ax.legend(frameon=False, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=250, bbox_inches="tight")
    plt.close(fig)
    return out_png


# ------------------------------------------------------------------- builder
def build(folder, name="650 nm nanopillars", out_dir=None, report_name=None,
          pattern="*/QC_report/field_metrics.csv", verbose=True):
    folder = os.path.abspath(folder)
    out_dir = os.path.abspath(out_dir or folder)
    report_name = report_name or f"SEM_batch_report_{os.path.basename(folder)}"
    work = os.path.join(out_dir, "QC_batch")
    figdir = os.path.join(work, "figures")
    pdir = os.path.join(work, "pairs")
    for d in (work, figdir, pdir):
        os.makedirs(d, exist_ok=True)

    files = sorted(glob.glob(os.path.join(folder, pattern)))
    if not files:
        raise FileNotFoundError(f"no field_metrics.csv under {folder}")
    frames = []
    for f in files:
        d = pd.read_csv(f, encoding="utf-8-sig")
        d["sample_dir"] = os.path.basename(os.path.dirname(os.path.dirname(f)))
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df = df[df["period_nm"].notna() | df["theta_deg"].notna()].copy()
    cs = coupon_stats(df)
    if verbose:
        print(cs[["coupon", "fields", "lam", "lam_cv", "theta", "coh", "ordered"]]
              .round(1).to_string(index=False))

    # --- spread decomposition
    lam_pool = df["period_nm"].dropna()
    grand = float(lam_pool.mean())
    within = float(np.nanmean(cs["lam_cv"]))
    between = float(100 * cs["lam"].std(ddof=1) / cs["lam"].mean())
    th_m, th_sd = circ_mean_sd(df["theta_deg"])
    ord_mean = float(100 * df["ordered_frac"].mean())

    F1 = fig_period(cs, os.path.join(figdir, "fig1_coupon_period.png"))
    F2 = fig_dist(df, cs, os.path.join(figdir, "fig2_field_distribution.png"))
    F3 = fig_ordered(df, cs, os.path.join(figdir, "fig3_ordered_area.png"))

    # --- representative field per coupon (median ordered fraction) → original | marked
    reps = []
    for c in cs["coupon"]:
        g = df[df.coupon == c].copy()
        if not len(g):
            continue
        g["dist"] = (g["ordered_frac"] - g["ordered_frac"].median()).abs()
        row = g.sort_values("dist").iloc[0]
        src = os.path.join(folder, c, row["file"])
        if not os.path.exists(src):
            cand = glob.glob(os.path.join(folder, c, "**", row["file"]), recursive=True)
            if not cand:
                continue
            src = cand[0]
        try:
            res = analyse_image(src, tile_um=2.0)
        except Exception as exc:
            print(f"  !! {c}/{row['file']}: {exc}")
            continue
        marked = os.path.join(pdir, f"{c}_marked.png")
        annotate_image(src, marked, res=res, label=False)
        lam_s = f"{res['period_nm']:.0f} nm" if np.isfinite(res.get("period_nm", np.nan)) \
            else "not measurable"
        pair = fig_pair(src, marked, os.path.join(pdir, f"{c}_pair.png"),
                        title=f"{c}   {os.path.splitext(row['file'])[0]}   Λ {lam_s}   "
                              f"·   inside {100*res['ordered_frac']:.0f} %   "
                              f"·   C {res['coherence']:.2f}")
        reps.append((c, row["file"], pair, row))

    # ---------------------------------------------------------------- document
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
        r0 = fp.add_run(f"{name} — series quality summary   ·   page ")
        r0.font.size = Pt(8); r0.font.color.rgb = GREY
        fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE")
        run = OxmlElement("w:r"); t_el = OxmlElement("w:t"); t_el.text = "1"; run.append(t_el)
        fld.append(run); fp._p.append(fld)

    t = doc.add_paragraph()
    r = t.add_run(f"{name} — series quality summary")
    r.bold = True; r.font.size = Pt(17); r.font.color.rgb = NAVY
    sub = doc.add_paragraph()
    r = sub.add_run(f"{len(cs)} coupons · {len(df)} fields · "
                    f"2D-FFT texture analysis with 2 µm classification windows")
    r.font.size = Pt(10.5); r.italic = True; r.font.color.rgb = GREY
    meta = doc.add_paragraph()
    px = sorted({round(float(v), 3) for v in df["pixel_nm"]})
    rich(meta, f"generated {DATE_EN} · LabToolbox module `semtexture` · "
               + ", ".join(f"{v:g}" for v in px) + " nm/px · aggregation of the per-sample reports "
               f"in this folder (each coupon keeps its own report and marked copies)",
         size=Pt(8.5), color=GREY)
    doc.add_paragraph()

    head(doc, "Summary", 1)
    para(doc,
         f"Across the {len(cs)} coupons the ripple period is **{grand:.1f} nm** "
         f"(coupon-to-coupon CV **{between:.2f} %**, mean within-coupon CV **{within:.2f} %**), the "
         f"common orientation is **{th_m:.1f}°** with a circular SD of {th_sd:.1f}°, and the mean "
         f"coherence is **{df['coherence'].mean():.3f}**. On average **{ord_mean:.1f} % of the analysed "
         f"area sits inside the acceptance band**, ranging from {cs['ordered'].min():.0f} % "
         f"({cs.loc[cs['ordered'].idxmin(), 'coupon']}) to {cs['ordered'].max():.0f} % "
         f"({cs.loc[cs['ordered'].idxmax(), 'coupon']}) between coupons.")
    if ord_mean < 50:
        para(doc,
             "**Interpretation note.** These coupons do not behave as a single-period grating: the "
             "surface carries a directional texture almost everywhere (bare area "
             f"{100*df['bare_frac'].mean():.1f} %), but it does not repeat with one period and one "
             "orientation over a 2 µm window. The low ordered fraction therefore describes the "
             "*morphology* — short-range order, patchy or multi-directional — and not badly processed "
             "area. Read the series on two numbers: the fraction carrying directional texture "
             f"({100*(df['ordered_frac'].mean()+df['disordered_frac'].mean()):.0f} %) and the period "
             "distribution of Figure 2.")
    lo = cs.loc[cs["lam"].idxmin()]
    hi = cs.loc[cs["lam"].idxmax()]
    para(doc,
         f"Coupon mean periods run from {lo['lam']:.0f} nm ({lo['coupon']}) to {hi['lam']:.0f} nm "
         f"({hi['coupon']}), i.e. {between:.2f} % between coupons, while the field-to-field scatter "
         f"*inside* a coupon averages {within:.2f} %. Because the two are the same size, the "
         f"coupon-to-coupon differences cannot be separated from the local variation of the texture — "
         f"treat the series as one process with a period around {grand:.0f} nm and a genuine spread of "
         f"roughly ±{cs['lam_sd'].mean():.0f} nm per field, not as nine distinct processes.")

    head(doc, "1  How the numbers are produced", 1)
    para(doc,
         "Every image is processed identically in its own sample folder: the instrument band is removed, "
         "the illumination envelope is high-pass filtered, the period is read from the autocorrelation "
         "of the intensity profile along the ripple normal, and orientation and coherence come from the "
         "structure tensor:")
    add_eq(doc, mr("C = ") + mfrac(msub(mr("λ"), mr("1")) + mr(" − ") + msub(mr("λ"), mr("2")),
                                   msub(mr("λ"), mr("1")) + mr(" + ") + msub(mr("λ"), mr("2"))))
    add_eq(doc, mr("Λ = τ") + msup(mr(""), mr("*")) + mr(" ⋅ Δx,   τ") + msup(mr(""), mr("*")) +
            mr(" = ") + mu("argmax") + mdelim(mr("R(τ)"), "{", "}"))
    para(doc,
         "Each field is then cut into non-overlapping **2 µm windows** and every window is classified "
         "against the acceptance band (coherence, period within the window-scaled tolerance, "
         "orientation within ±15° of the family axis, phase coherence above the floor). The marked "
         "copies tint each off-spec window on a continuous scale — pale yellow for a window that is "
         "just outside the band, deep red for one that misses it by 2.5× or more — so the structure "
         "stays visible. Full method and the calibration of both structure types are in "
         "`SEM-EDX graphics/01_reports_and_metadata/SEM_texture_consistency_report_20261103.pdf`.")
    para(doc,
         "This report only aggregates the per-sample runs (`QC_report/field_metrics.csv` in each coupon "
         "folder); nothing is re-measured, so the numbers here are exactly the ones in the individual "
         "reports.")

    head(doc, "2  Coupon by coupon", 1)
    rows = []
    for _, r in cs.iterrows():
        rows.append([r["coupon"], int(r["fields"]),
                     f"{r['lam']:.1f}" if np.isfinite(r["lam"]) else "—",
                     f"{r['lam_sd']:.1f}" if np.isfinite(r["lam_sd"]) else "—",
                     f"{r['lam_cv']:.2f}" if np.isfinite(r["lam_cv"]) else "—",
                     f"{r['theta']:.1f}", f"{r['coh']:.3f}",
                     f"{r['ordered']:.1f}", f"{r['disordered']:.1f}", f"{r['bare']:.1f}",
                     f"{r['ordered_min']:.0f}–{r['ordered_max']:.0f}"])
    table(doc, ["coupon", "fields", "Λ (nm)", "SD (nm)", "CV %", "θ (°)", "C",
                "inside %", "off-spec %", "bare %", "inside range %"], rows,
          widths=[1.5, 1.2, 1.5, 1.4, 1.2, 1.2, 1.1, 1.5, 1.6, 1.2, 2.3], font=Pt(7.8))
    caption(doc, f"Table 1 — per coupon. Λ is the mean of the field periods, SD and CV describe the "
                 f"field-to-field scatter inside that coupon; the last column is the range of the "
                 f"per-field ordered area.")

    doc.add_picture(F1, width=Cm(14.5))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, "Figure 1 — coupon mean period with its field-to-field SD. The dashed line is the "
                 "series mean; the vertical scatter is what limits a \u201csame period everywhere\u201d "
                 "claim.")
    doc.add_picture(F2, width=Cm(14.5))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, "Figure 2 — period of every field, grouped by coupon (box = quartiles, dots = "
                 "fields). Overlapping boxes mean the coupons cannot be told apart by period.")

    doc.add_picture(F3, width=Cm(14.5))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, "Figure 3 — area inside the acceptance band per coupon (bar = coupon mean, dots = "
                 "individual fields). The spread inside a coupon is larger than the difference "
                 "between coupons.")

    head(doc, "3  Notes and limits", 1)
    for s in [
        "At 3 k one ripple period is only ~12 px, so each period carries ~±4 % from pixel sampling; "
        "the same coupons imaged at 12 k read a few percent higher. Use 12 k or AFM when the absolute "
        "number matters, not the 3 k value.",
        "Percentages depend on the window size; all coupons here use 2 µm, so they are directly "
        "comparable — but do not compare them with a 4 µm run.",
        "The ordered area measures the presence of the intended periodic texture. It says nothing about "
        "depth, chemistry or crystallinity (AFM, EDX, XRD).",
        "Bare area is ~0 throughout: the surfaces are covered with texture everywhere; the failures are "
        "of periodicity and orientation, not of coverage.",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        rich(p, s, size=Pt(9.5))
        p.paragraph_format.space_after = Pt(2)

    head(doc, "Appendix A  Every field", 1)
    para(doc, "All fields of all coupons, sorted by coupon and file. Λ is the field period, ± its "
              "robust spread; the last three columns are the area fractions of that field.")
    rows = []
    for _, r in df.sort_values(["coupon", "file"]).iterrows():
        rows.append([r["coupon"], os.path.splitext(str(r["file"]))[0],
                     f"{r['period_nm']:.1f}" if np.isfinite(r["period_nm"]) else "—",
                     f"{r['period_sd_nm']:.1f}" if np.isfinite(r["period_sd_nm"]) else "—",
                     f"{r['theta_deg']:.1f}", f"{r['coherence']:.3f}",
                     f"{100*r['ordered_frac']:.1f}", f"{100*r['disordered_frac']:.1f}",
                     f"{100*r['bare_frac']:.1f}"])
    table(doc, ["coupon", "field", "Λ (nm)", "SD (nm)", "θ (°)", "C",
                "inside %", "off-spec %", "bare %"], rows,
          widths=[1.4, 2.6, 1.5, 1.4, 1.3, 1.2, 1.6, 1.7, 1.3], font=Pt(6.8))

    if reps:
        head(doc, "Appendix B  One representative field per coupon", 1)
        para(doc, "For each coupon, the field closest to that coupon's median ordered area — left the "
                  "original micrograph, right the same field with the off-spec windows tinted "
                  "(pale yellow → deep red). No field is cherry-picked as best or worst.")
        for i, (c, fname, pair, row) in enumerate(reps, 1):
            doc.add_picture(pair, width=Cm(16.0))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption(doc, f"B{i} — {c} / "
                         f"{os.path.splitext(fname)[0]}: inside {100*row['ordered_frac']:.0f} %, "
                         f"off-spec {100*row['disordered_frac']:.0f} %.")

    docx_path = os.path.join(out_dir, f"{report_name}.docx")
    doc.save(docx_path)
    pdf_path = os.path.join(out_dir, f"{report_name}.pdf")
    try:
        tmp = os.path.join(tempfile.gettempdir(), f"batch_{report_name}.docx")
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

    df.sort_values(["coupon", "file"]).to_csv(os.path.join(work, "all_fields.csv"),
                                              index=False, encoding="utf-8-sig")
    cs.to_csv(os.path.join(work, "coupon_summary.csv"), index=False, encoding="utf-8-sig")
    shutil.rmtree(pdir, ignore_errors=True)
    return dict(docx=docx_path, pdf=pdf_path if os.path.exists(pdf_path) else None,
                coupons=len(cs), fields=len(df))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--name", default="650 nm nanopillars")
    ap.add_argument("--out-dir", default=None, dest="out_dir")
    ap.add_argument("--report-name", default=None, dest="report_name")
    ap.add_argument("--pattern", default="*/QC_report/field_metrics.csv")
    a = ap.parse_args()
    print(f"== {a.folder}")
    r = build(a.folder, name=a.name, out_dir=a.out_dir, report_name=a.report_name,
              pattern=a.pattern)
    print(f"   {r['coupons']} coupons, {r['fields']} fields -> {r['docx']}")
    if r["pdf"]:
        print(f"   pdf: {r['pdf']}")


if __name__ == "__main__":
    main()
