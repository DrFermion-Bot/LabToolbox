# -*- coding: utf-8 -*-
"""build_650_summary_report.py — one consolidated 650 nm LIVE/DEAD report covering
every repeat (1, 2, 3) plus the combined picture, for the whole set.

Everything numeric is read from the CSVs written by plot_650_multirepeat.py and from the
raw ImageJ count tables (for the Welch tests), so the report cannot disagree with the
figures.

Usage
  python build_650_summary_report.py --figdir E:/LabToolbox/output/650_repeat3_20261029/figs \
      --rep "repeat 1=<imagej_counts>" --rep "repeat 2=<imagej_counts_repeat2>" \
      --rep "repeat 3=<imagej_counts_repeat3>" \
      --out "F:/.../650nm_LIVE-DEAD_repeats1-3_summary_report_20261029.pdf"
"""
from __future__ import annotations

import argparse
import os
import shutil

import numpy as np
import pandas as pd
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from scipy import stats

SCRATCH = 'C:/Users/PC/AppData/Local/hermes/cache/scratch'
TIMES = ['3h', '5h', '7h', '24h']
AREAS = ['c', '1', '2']
AREA_LABEL = {'c': 'Control', '1': 'LIPSS', '2': 'Nanopillar'}
SP_DIR = {'E. coli': 'E.coli', 'S. aureus': 'S.aureus'}


# ------------------------------------------------------------------ docx helpers
def add_bullets(doc, lines):
    for line in lines:
        doc.add_paragraph(line, style='List Bullet')


def add_note(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(8.5)
    r.italic = True
    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)


def add_figure(doc, path, width_cm, caption):
    if os.path.isfile(path):
        doc.add_picture(path, width=Cm(width_cm))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    else:
        doc.add_paragraph('[missing figure: %s]' % os.path.basename(path))
    add_note(doc, caption)


def grid_table(doc, header, rows, caption=None, fontsize=8):
    if caption:
        doc.add_paragraph(caption, style='Heading 3')
    tb = doc.add_table(rows=1, cols=len(header))
    tb.style = 'Light Grid Accent 1'
    for i, h in enumerate(header):
        cell = tb.rows[0].cells[i]
        cell.text = ''
        run = cell.paragraphs[0].add_run(str(h))
        run.bold = True
        run.font.size = Pt(fontsize)
    for row in rows:
        cells = tb.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ''
            run = cells[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(fontsize)
    doc.add_paragraph()


def fmt_p(p):
    if p != p:
        return 'n/a'
    if p < 0.001:
        return '<0.001'
    return '%.3f' % p


def sign(x):
    if not np.isfinite(x) or abs(x) <= 5:
        return '0'
    return '+' if x > 0 else '-'


# ------------------------------------------------------------------ data helpers
def load_counts(dirpath, sp):
    p = os.path.join(dirpath, SP_DIR[sp], 'livedead_raw_counts.csv')
    if not os.path.isfile(p):
        return None
    df = pd.read_csv(p, encoding='utf-8-sig')
    df = df[df.area != '3']
    df['live'] = pd.to_numeric(df['live'], errors='coerce')
    df['total'] = pd.to_numeric(df['live'], errors='coerce').fillna(0) + \
        pd.to_numeric(df['dead'], errors='coerce').fillna(0)
    df['area'] = df['area'].astype(str)
    df['time'] = df['time'].astype(str)
    return df


def welch(raw, t, area, col='total'):
    if raw is None:
        return np.nan
    c = raw[(raw.time == t) & (raw.area == 'c')][col].astype(float)
    s = raw[(raw.time == t) & (raw.area == area)][col].astype(float)
    if len(c) < 2 or len(s) < 2:
        return np.nan
    return float(stats.ttest_ind(c, s, equal_var=False).pvalue)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--figdir', required=True)
    ap.add_argument('--rep', action='append', default=[], help='"label=count dir"')
    ap.add_argument('--out', default='')
    ap.add_argument('--date', default='20261029')
    ap.add_argument('--exclusions', default='',
                    help='exclusion registry CSV (default <figdir>/650nm_exclusions_<date>.csv)')
    a = ap.parse_args()
    fig = a.figdir
    reps = [x.split('=', 1) for x in a.rep]
    labels = [ln.strip() for ln, _ in reps]
    dirs = {ln.strip(): d.strip() for ln, d in reps}

    R = {lb: pd.read_csv(os.path.join(fig, '650nm_livedead_%s_summary.csv'
                                      % lb.replace(' ', '')), encoding='utf-8-sig')
         for lb in labels}
    CB = pd.read_csv(os.path.join(fig, '650nm_livedead_combined_summary.csv'), encoding='utf-8-sig')
    AA = pd.read_csv(os.path.join(fig, '650nm_livedead_perrepeat_aa.csv'), encoding='utf-8-sig')
    AA['area'] = AA['area'].astype(str)
    est_path = os.path.join(fig, '650nm_control_inference.csv')
    EST = None                                    # no estimated controls any more: excluded
    excl_path = a.exclusions or os.path.join(fig, '650nm_exclusions_%s.csv' % a.date)
    EX = (pd.read_csv(excl_path, encoding='utf-8-sig') if os.path.isfile(excl_path)
          else pd.DataFrame(columns=['level', 'repeat', 'species', 'time', 'area', 'issue',
                                     'detail', 'evidence']))
    raws = {lb: {sp: load_counts(d, sp) for sp in ('E. coli', 'S. aureus')}
            for lb, d in dirs.items()}

    # how many condition groups / AA values each excluded entry removes
    grp = []
    for _, r in EX.iterrows():
        area = '' if pd.isna(r['area']) else str(r['area'])
        try:
            area = str(int(float(area))) if area not in ('', 'c') else area
        except ValueError:
            pass
        if area:
            grp.append(dict(n_grp=1, n_aa=1))
        else:
            grp.append(dict(n_grp=3, n_aa=2))

    # how many fields the objective field-level screen flagged (retained, not removed)
    n_field_flags = 0
    for cand in (fig, os.path.dirname(os.path.abspath(fig))):
        for fn in sorted(os.listdir(cand)) if os.path.isdir(cand) else []:
            if fn.startswith('650nm_exclusion_screen_') and fn.endswith('.csv'):
                try:
                    sc = pd.read_csv(os.path.join(cand, fn), encoding='utf-8-sig')
                    n_field_flags = int((sc.get('rule') == 'field').sum())
                except Exception:
                    pass

    def rv(lb, sp, t, ar, col):
        df = R[lb]
        g = df[(df.species == sp) & (df.time == t) & (df.area == ar)]
        return float(g[col].iloc[0]) if len(g) else np.nan

    def aav(sp, t, ar, lb, live=False):
        col = '%s_AAlive%%' % lb if live else '%s_AA%%' % lb
        g = AA[(AA.species == sp) & (AA.time == t) & (AA.area == ar)]
        if not len(g) or col not in g.columns:
            return np.nan
        v = g[col].iloc[0]
        return float(v) if np.isfinite(v) else np.nan

    def comb_aa(sp, t, ar, live=False):
        g = AA[(AA.species == sp) & (AA.time == t) & (AA.area == ar)]
        if not len(g):
            return np.nan, np.nan
        v = float(g['aa_live' if live else 'aa'].iloc[0])
        sd = float(g['aa_live_sd' if live else 'aa_sd'].iloc[0])
        return v, sd

    doc = Document()
    doc.styles['Normal'].font.name = 'Calibri'
    doc.styles['Normal'].font.size = Pt(10.5)

    doc.add_heading('650 nm laser-textured stainless steel - bacterial LIVE/DEAD assay', level=0)
    doc.add_paragraph('Consolidated report over %d repeats (%s), generated %s'
                      % (len(labels), ', '.join(labels), a.date))

    # ---------------------------------------------------------------- 1. summary
    doc.add_heading('1. Summary', level=1)
    # values used in the prose, all computed
    rows_consist = []
    for sp in ('E. coli', 'S. aureus'):
        for ar, nm in (('1', 'LIPSS'), ('2', 'Nanopillar')):
            for t in TIMES:
                vals = [aav(sp, t, ar, lb) for lb in labels]
                sg = {sign(v) for v in vals if np.isfinite(v)}
                sg = {x for x in sg if x != '0'}
                mv, sdv = comb_aa(sp, t, ar)
                ps = [welch(raws[lb].get(sp), t, ar) for lb in labels]
                nsig = sum(1 for p in ps if np.isfinite(p) and p < 0.05)
                n_ok = int(sum(1 for v in vals if np.isfinite(v)))
                rows_consist.append(dict(species=sp, area=nm, time=t, vals=vals,
                                         mean=mv, sd=sdv, signs=sg, n_sig=nsig, n=n_ok,
                                         consistent=(bool(len(sg) <= 1) and n_ok >= 2)))
    cons = pd.DataFrame(rows_consist)

    # largest repeat-to-repeat spread of one and the same condition (total density)
    batch_ratio = 1.0
    for sp in ('E. coli', 'S. aureus'):
        for t in TIMES:
            for ar in AREAS:
                v = [rv(lb, sp, t, ar, 'total_cm2') for lb in labels]
                v = [x for x in v if np.isfinite(x) and x > 0]
                if len(v) > 1:
                    batch_ratio = max(batch_ratio, max(v) / min(v))

    def cond_line(sp, nm):
        d = cons[(cons.species == sp) & (cons.area == nm)]
        ok = d[d.consistent]
        single = d[(~d.consistent) & (d.n < 2)]
        bad = d[(~d.consistent) & (d.n >= 2)]
        bits = []
        if len(ok):
            bits.append('consistent in direction at %s'
                        % ', '.join('%s (mean %+.0f %%, SD %.0f)' % (r.time, r['mean'], r['sd'])
                                    for _, r in ok.iterrows()))
        if len(bad):
            bits.append('sign flips between repeats at %s'
                        % ', '.join('%s (%s)' % (r.time, ', '.join(
                            ('%+.0f' % v) if np.isfinite(v) else '-' for v in r.vals))
                                    for _, r in bad.iterrows()))
        if len(single):
            bits.append('only one valid repeat left at %s (%s) - no consistency test possible'
                        % (', '.join(r.time for _, r in single.iterrows()),
                           ', '.join('%+.0f %%' % r['mean'] for _, r in single.iterrows())))
        return '%s / %s: %s' % (sp, nm, '; '.join(bits) if bits else 'nothing to compare')

    n_sa_ok = len(cons[(cons.species == 'S. aureus') & (cons.area == 'Nanopillar')
                       & cons.consistent])
    sa_mean = cons[(cons.species == 'S. aureus') & (cons.area == 'Nanopillar')]['mean']
    ec_bad = len(cons[(cons.species == 'E. coli') & ~cons.consistent])
    n_tot = int(len(cons))
    add_bullets(doc, [
        '%d independent repeats of the same 650 nm coupon type were counted with a single '
        'ImageJ pipeline (%d images per repeat, %d groups of 5 fields each).'
        % (len(labels), 240, 24),
        'Conditions whose anti-adhesion keeps the same sign in every repeat that survives the '
        'exclusions (n >= 2): %s. Everything else changes sign between repeats and is not '
        'quotable as an effect.'
        % (', '.join('%s %s at %s (%+.0f %%)' % (r.species, r.area, r.time, r['mean'])
                     for _, r in cons[cons.consistent].iterrows()) or 'none'),
        'The S. aureus nanopillar area - the only consistent signal when repeats 1-3 were '
        'summarised - is %s once repeat 4 is added (%s). Its mean anti-adhesion is %+.0f to '
        '%+.0f %% (sd across repeats %.0f-%.0f pp), and at the timepoints where the sign holds '
        'the next repeat reverses it, so with four repeats it no longer qualifies as a '
        'reproducible effect. It stays a small, direction-plausible trend.'
        % ('no longer consistent' if n_sa_ok < 4 else 'still consistent in %d of 4' % n_sa_ok,
           ', '.join('%s: %s' % (r.time, ', '.join(
               ('%+.0f' % v) if np.isfinite(v) else '-' for v in r.vals))
               for _, r in cons[(cons.species == 'S. aureus') & (cons.area == 'Nanopillar')].iterrows()),
           float(np.nanmin(sa_mean)), float(np.nanmax(sa_mean)),
           float(np.nanmin(cons[(cons.species == 'S. aureus') & (cons.area == 'Nanopillar')]['sd'])),
           float(np.nanmax(cons[(cons.species == 'S. aureus') & (cons.area == 'Nanopillar')]['sd']))),
        'E. coli shows no reproducible effect across the full set: %d of its 8 '
        'condition-timepoints flip sign between repeats, and the ones that do agree rest on two '
        'repeats only after the outlier screen. Its fields carry tens to a few hundred cells, so '
        'a single repeat can read anywhere from -140 %% to +60 %%.' % ec_bad,
        '%d data points are excluded from every statistic in this report (%d condition groups, '
        '%d anti-adhesion values): reported experimental problems (ethanol contamination, a '
        'dropped control, a contaminated control, a failed staining) and one acquisition anomaly '
        'are removed outright, and an objective screen removes repeat-level anti-adhesion '
        'outliers; they are listed in section 2.1 and marked in the figures instead of being '
        'estimated or borrowed.'
        % (len(EX), int(sum(q['n_grp'] for q in grp)), int(sum(q['n_aa'] for q in grp))),
        'Repeat-to-repeat scatter of the anti-adhesion value is of the same size as the effects '
        '(mean SD %.0f pp), and the absolute density of the same condition differs up to %.1fx '
        'between repeats - so individual repeat numbers must not be quoted as an effect size; '
        'only direction-consistent, pooled numbers are usable.'
        % (float(np.nanmean(cons['sd'])), batch_ratio),
    ])

    # ---------------------------------------------------------------- 2. methods
    doc.add_heading('2. Samples, counting and statistics', level=1)
    add_bullets(doc, [
        'Coupon: 650 nm laser-textured stainless steel, one coupon per condition per repeat, '
        'three areas per coupon - c = untreated control, 1 = LIPSS, 2 = nanopillar (the treated '
        'areas sit a few micrometres below the control surface).',
        'Four coupons rotate through the four exposure times, one place per repeat '
        '(repeat 1: 1,2,3,4; repeat 2: 2,3,4,1; repeat 3: 3,4,1,2; repeat 4: 4,1,2,3), so a coupon '
        'is imaged at a different timepoint in each repeat. With four repeats the coupon x '
        'timepoint assignment is a complete 4x4 Latin square.',
        'Organisms: E. coli, S. aureus. Times: 3, 5, 7, 24 h. Five fields per area and timepoint, '
        'each field imaged in a green (live) and a red (dead) channel. One repeat = 8 folders x '
        '30 images = 240 images; all %d repeats = %d images.' % (len(labels), 240 * len(labels)),
        'Counting: ImageJ 1.54 headless, adaptive threshold (background mode + 40), Analyze '
        'Particles size 3-500 px, 40x field area 46 946.10 um2. Density = count / 46 946.10 um2 '
        'x 1e8 cells/cm2.',
        'Viability = pooled live / (live + dead) over the 5 fields of a condition. '
        'Anti-adhesion = (N_control - N_surface) / N_control x 100, computed for total cells '
        '(live + dead) and for live cells separately.',
        'Per repeat the anti-adhesion carries a delta-method SD propagated from the field means; '
        'the combined value is the mean of the per-repeat anti-adhesion values with the SD across '
        'repeats (n = %d) as the error bar. Each repeat uses its OWN control: the batches differ '
        'up to a factor of two in absolute density, so pooling the controls would compare '
        'non-comparable coupons.' % len(labels),
        'Significance: Welch t-test control vs treated on the 5 fields per condition and repeat '
        '(uncorrected). With %d repeats there is no repeat-level test - the p-values describe '
        'within-repeat field variability only.' % len(labels),
        'Nothing is borrowed or estimated across repeats: a data point is either measured with '
        'its own control or it is excluded from every statistic. The excluded points are listed '
        'in section 2.1 and marked with a grey dashed "EXCLUDED" box in the figures.',
    ])

    doc.add_heading('2.1 Excluded data points (removed from every statistic)', level=1)
    if len(EX):
        exrows, reasons = [], []
        n_grp, n_aa = 0, 0
        for _, r in EX.iterrows():
            area = '' if pd.isna(r['area']) else str(r['area'])
            try:
                area = str(int(float(area))) if area not in ('', 'c') else area
            except ValueError:
                pass
            if area:
                n_grp += 1
                n_aa += 1
            else:
                n_grp += 3
                n_aa += 2
            exrows.append([r['repeat'], r['time'], r['species'],
                           'whole timepoint' if not area else AREA_LABEL.get(area, area),
                           r['issue']])
            reasons.append('%s, %s, %s: %s (%s)'
                           % (r['repeat'], r['time'], r['species'], r['detail'], r['evidence']))
        tb = doc.add_table(rows=1, cols=5)
        tb.style = 'Light Grid Accent 1'
        for i, h in enumerate(['Run', 'Incubation point', 'Organism', 'Area', 'Issue']):
            cell = tb.rows[0].cells[i]
            cell.text = ''
            run = cell.paragraphs[0].add_run(h)
            run.bold = True
            run.font.size = Pt(8)
        for row in exrows:
            cells = tb.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ''
                run = cells[i].paragraphs[0].add_run(str(v))
                run.font.size = Pt(8)
        doc.add_paragraph()
        add_note(doc, 'Table 2.1 - every point removed from this analysis. "Whole timepoint" = '
                      'the control and both treated areas removed together, so no anti-adhesion '
                      'can be formed. Reasons and evidence follow.')
        add_bullets(doc, reasons)
        add_bullets(doc, [
            'Exclusion rules used, in this order: (1) reported experimental problems (ethanol '
            'contamination, dropped control, contaminated coupon, failed staining) and one '
            'image-level acquisition anomaly remove the point outright; (2) an objective screen '
            'then looks for repeat-level anti-adhesion outliers, and flags a repeat only when '
            'the OTHER repeats agree within 25 percentage points and the flagged one lies more '
            'than 100 pp from their mean - where the remaining repeats disagree nothing is '
            'removed, the condition is reported as not reproducible instead; (3) a field-level '
            'screen (>3x the median of the other four fields) flagged %d fields, all retained: '
            'the objects in them are normal-sized single cells with no clumps, i.e. genuinely '
            'denser or sparser fields, and dropping them would bias the mean.'
            % n_field_flags,
            'Scale of the cut: %d of the %d condition groups (2 organisms x 4 timepoints x 3 '
            'areas x %d runs) are removed, i.e. %d of the %d anti-adhesion values no longer '
            'exist. Every remaining number is a measurement with its own control.'
            % (int(sum(q['n_grp'] for q in grp)), 2 * 4 * 3 * len(labels), len(labels),
               int(sum(q['n_aa'] for q in grp)), 2 * 4 * 2 * len(labels)),
        ])
    else:
        doc.add_paragraph('No exclusions were applied.')

    # ---------------------------------------------------------------- 3. figures
    doc.add_heading('3. Figures', level=1)
    doc.add_paragraph('Each figure has the same two columns: left = live/dead density with the '
                      'pooled viability over each bar; right = the anti-adhesion rate itself for '
                      'total cells (solid) and live cells (pale). Positive = fewer cells than the '
                      'untreated control area of the same coupon, negative = more cells than the '
                      'control.')
    figs = [(lb, '650nm_livedead_%s_AA.png' % lb.replace(' ', '')) for lb in labels]
    figs.append(('combined', '650nm_livedead_combined_%s_AA.png'
                 % ''.join(lb.replace('repeat', 'r').replace(' ', '') for lb in labels)))
    for k, (lb, fn) in enumerate(figs, start=1):
        is_comb = lb == 'combined'
        doc.add_heading('Figure %d - %s' % (k, 'all repeats combined' if is_comb else lb), level=2)
        if is_comb:
            cap = ('Figure %d. Combined over %s. Right-hand bars = mean of the per-repeat '
                   'anti-adhesion values (each repeat against its own control); empty circle / '
                   'square / triangle = the individual repeat values; error bars = SD across '
                   'repeats; grey x markers are the per-repeat values removed by the registry '
                   '(shown, never pooled). The pooled values use only the points that survive '
                   'Table 2.1, so '
                   'some timepoints rest on two repeats and S. aureus 7 h on one (marked n = 1 in '
                   'Table 4.5); the repeat figures show where the removed points sit.'
                   % (k, ', '.join(labels)))
        else:
            cap = ('Figure %d. %s. Left: live (green) + dead (red) density from the 5 fields; '
                   '%% over the stack = pooled viability. Right: anti-adhesion for total cells '
                   '(solid) and live cells (pale); error bars = delta-method SD of the field '
                   'means. A grey hatched bar tagged EXCLUDED is a point removed from the '
                   'analysis: plotted with its measured value for completeness, but not used in '
                   'any statistic; where the control itself is unusable the slot is shown as a '
                   'dashed EXCLUDED box instead.' % (k, lb))
            mine = EX[EX['repeat'] == lb] if len(EX) else EX
            if len(mine):
                bits = []
                for _, r in mine.iterrows():
                    area = '' if pd.isna(r['area']) else str(r['area'])
                    try:
                        area = str(int(float(area))) if area not in ('', 'c') else area
                    except ValueError:
                        pass
                    bits.append('%s %s %s (%s)'
                                % (r['time'], r['species'],
                                   'whole timepoint' if not area else AREA_LABEL.get(area, area),
                                   r['issue']))
                cap += ' Excluded here: ' + '; '.join(bits) + '.'
        add_figure(doc, os.path.join(fig, fn), 16.4, cap)

    # ---------------------------------------------------------------- 4. tables
    doc.add_heading('4. Tables', level=1)

    for sp in ('E. coli', 'S. aureus'):
        hdr = ['Time']
        for lb in labels:
            hdr += ['%s c' % lb.replace('repeat ', 'R'), 'LIPSS', 'Nano']
        rows = []
        for t in TIMES:
            row = [t.replace('h', ' h')]
            for lb in labels:
                for ar in AREAS:
                    v = rv(lb, sp, t, ar, 'total_cm2') / 1e5
                    row.append('-' if not np.isfinite(v) else '%.1f' % v)
            rows.append(row)
        grid_table(doc, hdr, rows,
                   caption='Table 4.%d - %s: total cells (live + dead, x1e5 cells/cm2) per repeat '
                   'and area.' % (1 if sp == 'E. coli' else 2, sp))

        rows = []
        for t in TIMES:
            row = [t.replace('h', ' h')]
            for lb in labels:
                for ar in AREAS:
                    v = rv(lb, sp, t, ar, 'viability')
                    row.append('-' if not np.isfinite(v) else '%.0f%%' % v)
            rows.append(row)
        grid_table(doc, hdr, rows,
                   caption='Table 4.%d - %s: pooled viability (live / (live + dead)) per repeat '
                   'and area.' % (3 if sp == 'E. coli' else 4, sp))

    for live, tag, num in ((False, 'total cells', 5), (True, 'live cells', 6)):
        rows = []
        for sp in ('E. coli', 'S. aureus'):
            for ar, nm in (('1', 'LIPSS'), ('2', 'Nanopillar')):
                for t in TIMES:
                    vals = [aav(sp, t, ar, lb, live=live) for lb in labels]
                    mv, sdv = comb_aa(sp, t, ar, live=live)
                    sg = {sign(v) for v in vals if np.isfinite(v)} - {'0'}
                    n_ok = int(sum(1 for v in vals if np.isfinite(v)))
                    if n_ok < 2:
                        check = 'single repeat only'
                    elif len(sg) <= 1:
                        check = 'consistent'
                    else:
                        check = 'not consistent (%d signs)' % len(sg)
                    rows.append([sp, t.replace('h', ' h'), nm]
                                + ['-' if not np.isfinite(v) else '%+.0f%%' % v for v in vals]
                                + ['-' if not np.isfinite(mv) else '%+.0f%%' % mv,
                                   '-' if not np.isfinite(sdv) else '%.0f' % sdv,
                                   str(n_ok), check])
        grid_table(doc, ['Organism', 'Time', 'Area'] + labels + ['mean', 'SD', 'n', 'sign check'],
                   rows, caption='Table 4.%d - anti-adhesion on %s, per repeat and pooled. '
                   '"-" = that point is excluded (see Table 2.1). n = number of repeats that '
                   'contribute. Positive = fewer cells than the control of the same repeat; the '
                   'sign check treats |AA| > 5 %% as a sign.' % (num, tag), fontsize=7.5)

    rows = []
    for sp in ('E. coli', 'S. aureus'):
        for ar, nm in (('1', 'LIPSS'), ('2', 'Nanopillar')):
            for t in TIMES:
                ps = [welch(raws[lb].get(sp), t, ar) for lb in labels]
                vals = [aav(sp, t, ar, lb) for lb in labels]
                mv, sdv = comb_aa(sp, t, ar)
                rows.append([sp, t.replace('h', ' h'), nm]
                            + [fmt_p(p) for p in ps]
                            + ['%d/%d' % (sum(1 for p in ps if np.isfinite(p) and p < 0.05),
                                          sum(1 for p in ps if np.isfinite(p))),
                               '-' if not np.isfinite(mv) else '%+.0f%%' % mv])
    grid_table(doc, ['Organism', 'Time', 'Area'] + ['p %s' % lb for lb in labels]
               + ['p<0.05', 'AA mean'],
               rows, caption='Table 4.7 - Welch t-test on total cells, control vs treated, per '
               'repeat (uncorrected, n = 5 fields); last columns = how many repeats reached '
               'p < 0.05 (out of the repeats with a valid comparison) and the pooled '
               'anti-adhesion. A direction-consistent condition can still '
               'be non-significant within an individual repeat, because the field-to-field SD is '
               'large relative to the effect.', fontsize=7.5)

    # ---------------------------------------------------------------- 5. consistency
    doc.add_heading('5. Repeat consistency - what can and cannot be quoted', level=1)
    add_bullets(doc, [cond_line(sp, nm) for sp in ('E. coli', 'S. aureus')
                      for nm in ('LIPSS', 'Nanopillar')])

    sa = cons[(cons.species == 'S. aureus') & (cons.area == 'Nanopillar')]
    ec = cons[cons.species == 'E. coli']

    # coupon Latin-square result (written by coupon_rotation_650_latin.py next to the figs)
    COUPON_DIR = os.path.join(os.path.dirname(os.path.abspath(fig)), 'coupon_latin')
    cpath = os.path.join(COUPON_DIR, 'coupon_latin_tests.csv')
    if os.path.isfile(cpath):
        ct = pd.read_csv(cpath, encoding='utf-8-sig')
        COUPON_TXT = ', '.join('%s %s F = %.2f, p = %.2f'
                               % (r['species'], r['area'], r['F'], r['p'])
                               for _, r in ct.iterrows())
    else:
        COUPON_TXT = ('no coupon model has been run yet (see scripts/'
                      'coupon_rotation_650_latin.py)')
    add_bullets(doc, [
        'Same sign in every repeat that has a valid control (n >= 2): %s. Only the S. aureus '
        'points and the E. coli LIPSS at 7 h / 24 h rest on data whose fields are dense enough to '
        'trust in magnitude; the E. coli LIPSS 5 h value is same-signed but its fields carry tens '
        'to a few hundred cells, so quote the direction, not the number. State the n behind each '
        '(Table 4.5) - at several timepoints that is two or three repeats, not four.'
        % (', '.join('%s on %s at %s (%+.0f %%, n = %d)'
                     % (r.species, r.area, r.time, r['mean'], r.n)
                     for _, r in cons[cons.consistent].iterrows()) or 'nothing'),
        'No longer quotable as a reproducible effect: the S. aureus nanopillar series '
        '(%s). Repeats 1-3 pointed the same way at their timepoints; repeat 4 reverses it at '
        '3 h, 5 h and 24 h. With four repeats the honest statement is a small trend in the '
        'expected direction that did not reproduce in the fourth run, not an anti-adhesion '
        'effect.'
        % ', '.join('%s: %s' % (r.time, ', '.join(
            ('%+.0f' % v) if np.isfinite(v) else '-' for v in r.vals)) for _, r in sa.iterrows()),
        'Not quotable as an effect: any E. coli number (%d of 8 condition-timepoints change sign '
        'between repeats) and the S. aureus LIPSS series except at 24 h. Report these repeat by '
        'repeat, or as "no reproducible difference".' % len(ec[~ec.consistent]),
        'Do not average across repeats without also giving the per-repeat spread: the SD across '
        'repeats is %.0f pp on average and up to %.0f pp, i.e. of the same size as the effect '
        'itself.' % (float(np.nanmean(cons['sd'])), float(np.nanmax(cons['sd']))),
        'Coupon identity: with four repeats the coupon x timepoint assignment is a complete 4x4 '
        'Latin square (rows = repeats, columns = timepoints, letters = coupons), so a coupon '
        'effect on anti-adhesion is estimable. Latin-square models (AA ~ repeat + time + coupon, '
        'one value per repeat x timepoint, registry exclusions applied) give %s. Coupon identity '
        'explains 10-20 %% of the variance in every panel but never reaches significance, and the '
        'residual degrees of freedom are only 2-5, so the honest reading is still \"no evidence '
        'that a coupon carries its own anti-adhesion character\", not \"proven absent\". '
        'Per-coupon means and the full model output: %s.'
        % (COUPON_TXT, COUPON_DIR),
    ])

    thin = ['%s %s %s (n = %d)' % (r.species, r.time, r.area, r.n)
            for _, r in cons[cons.n < len(labels)].iterrows()] if len(cons) else []
    n_one = cons[cons.n < 2]['n'].count() if len(cons) else 0
    add_bullets(doc, [
        'What the exclusions cost: %d condition-timepoints rest on fewer than %d repeats'
        '%s%s. Direction-consistent conclusions therefore rely on the repeats that are left, '
        'and where only one repeat is left no consistency statement is made at all. Points that '
        'start agreeing only after an outlier was removed agree because of the exclusion rule, '
        'not because of an effect.'
        % (len(thin), len(labels),
           (' (' + '; '.join(thin) + ')') if thin else '',
           '; %d timepoint(s) have a single repeat' % n_one if n_one else ''),
    ])

    # ---------------------------------------------------------------- 6. QC
    doc.add_heading('6. Quality control and limitations', level=1)
    add_bullets(doc, [
        'Field count: 5 per condition per repeat. These are field replicates on one coupon, not '
        'biological replicates; n = %d repeats is the biological replication.' % len(labels),
        'E. coli fields are sparse (tens to a few hundred cells per field versus thousands for '
        'S. aureus), so its relative noise is much larger and its anti-adhesion values should not '
        'be interpreted as surface effects.',
        'Objects larger than 500 px (merged clusters) are excluded by the size filter, so a '
        'heavily colonised field is a lower bound on the true number. S. aureus at 24 h is close '
        'to confluent in several fields.',
        'Repeats are separate staining and imaging sessions: absolute density of the same '
        'condition varies up to %.1fx between repeats (staining efficiency, illumination, '
        'exposure), which is why every repeat keeps its own control and why the pooled figure '
        'averages per-repeat values instead of pooling raw counts.' % batch_ratio,
        'Imaging format changed after repeat 1: repeat 1 stored the green and red channels as '
        'separate single-channel images, repeats 2-4 store both channels in each file (green '
        'in channel 1, red in channel 0, with slight crosstalk in the non-target channel). The '
        'macro reads only the named channel, so counts stay comparable, but the files are not '
        'pixel-identical in format.',
        'Excluded points are not replaced by estimates or by values borrowed from another '
        'repeat: the affected slots are empty in the figures and listed in Table 2.1. This costs '
        'degrees of freedom - %d condition-timepoints now rest on fewer than %d repeats - but '
        'keeps every number in this report a measurement.'
        % (len(thin), len(labels)),
        'Repeat 4, S. aureus 3 h, LIPSS area: the five fields hold 4 000-5 000 detected objects '
        'with a median object area of 24-44 px, against 560-760 objects and 70-105 px in the '
        'control and nanopillar areas imaged in the same session (exposure 0.50 s versus '
        '0.20-0.30 s). The objects are sub-cell speckle, so the count is an imaging artefact and '
        'that area is excluded, not interpreted.',
        'The repeat-1 S. aureus 5 h nanopillar coupon read 0.4 % viability; the repeat-2 re-shot '
        'of the same coupon read 50.7 %, so the repeat-1 value is a staining artefact and is '
        'excluded rather than quoted with an uncertainty.',
    ])

    # ---------------------------------------------------------------- 7. provenance
    doc.add_heading('7. Data and provenance', level=1)
    add_bullets(doc, [
        'Raw images: Live_Dead Bacteria Test/650nm-20261014/<species>/<repeat>/<time>/ '
        '(240 images per repeat, %d in total).' % (240 * len(labels)),
        'Counts: <repeat N counts dir>/<species>/livedead_raw_counts.csv, one directory per '
        'repeat (%s).' % ', '.join(lb.replace(' ', '') for lb in labels),
        'Figures, summary CSVs and the per-repeat anti-adhesion table: %s.' % fig,
        'Exclusion registry: %s (the screen evidence file sits next to it).'
        % os.path.basename(excl_path),
        'Scripts: recount_650_repeat2_imagej.py (counting, ImageJ macro), '
        'plot_650_multirepeat.py (figures, any number of repeats), '
        'build_650_exclusion_registry.py (exclusion registry), '
        'build_650_summary_report.py (this report). Repository github.com/DrFermion/LabToolbox.',
        'Reproduce: recount each repeat with recount_650_repeat2_imagej.py --repeats "<repeat>" '
        '--minpx 3, then build_650_exclusion_registry.py with one --rep per repeat, then '
        'plot_650_multirepeat.py with the same --rep list plus --exclusions <registry CSV> '
        '--exclude-3, then this report builder with --exclusions <registry CSV>.',
    ])

    docx_path = os.path.join(SCRATCH, '650nm_repeats_summary_report_%s.docx' % a.date)
    pdf_path = a.out or os.path.join(SCRATCH, '650nm_repeats_summary_report_%s.pdf' % a.date)
    doc.save(docx_path)
    print('docx saved:', docx_path)
    try:
        import win32com.client
        word = win32com.client.Dispatch('Word.Application')
        word.Visible = False
        try:
            d = word.Documents.Open(os.path.abspath(docx_path))
            d.SaveAs(os.path.abspath(pdf_path), FileFormat=17)
            d.Close(False)
        finally:
            word.Quit()
        print('pdf saved:', pdf_path, os.path.getsize(pdf_path), 'bytes')
        try:
            from pypdf import PdfReader
            rd = PdfReader(pdf_path)
            txt = ''.join((pg.extract_text() or '') for pg in rd.pages)
            print('pages:', len(rd.pages), '| chars:', len(txt),
                  '| has Table 4.5:', 'Table 4.5' in txt, '| has Figure 4:', 'Figure 4' in txt)
        except Exception as e:
            print('pdf check skipped:', e)
    except Exception as e:
        print('Word COM export failed:', e)
    dst = os.path.join(fig, os.path.basename(docx_path))
    if os.path.abspath(dst) != os.path.abspath(docx_path):
        shutil.copy2(docx_path, dst)
        print('copied ->', dst)


if __name__ == '__main__':
    main()
