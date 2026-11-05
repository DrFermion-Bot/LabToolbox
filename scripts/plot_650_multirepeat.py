# -*- coding: utf-8 -*-
"""plot_650_multirepeat.py — 650 nm LIVE/DEAD figures for the NEWEST repeat plus an
N-repeat combined figure (replaces the 2-repeat-only plot_650_repeat2.py going forward).

Why this exists: plot_650_repeat2.py hard-codes "repeat 1 vs repeat 2". Repeat 3 is in,
so the combined figure has to average three repeats while still exposing each repeat's
own mean. Same counting rule, same colours, same layout; the plotting primitives are
imported from plot_650_repeat2 so the two never drift apart.

Counting rule: ImageJ 1.54, adaptive threshold (background mode + 40), size 3-500 px,
40x field area 46 946.10 um2 -> density = count / 46 946.10 um2 * 1e8.

Figures
  A  650nm_livedead_<focus>.png
     2 rows (species) x 2 cols: left = live/dead stacked density, right = total-cell
     density with anti-adhesion % over the treated bars.
  B  650nm_livedead_combined_<all>.png
     same layout, bars = mean of the per-repeat means, empty markers = each repeat.
  C  650nm_livedead_validation_<coupon>.png  (only when an area-3 coupon exists)

Data model: <count dir>/<species>/livedead_raw_counts.csv, columns
  repeat,time,area,num,g_image,r_image,live,dead,total,dead_rate
area codes: c = Control, 1 = LIPSS, 2 = Nanopillar, 3 = extra re-shot coupon (never
pooled, only figure C).

Per-repeat fixups (all optional, keyed by the repeat LABEL you pass in --rep):
  --drop     "species|time|area|label"      remove a superseded measurement from that repeat
  --borrow   "species|time|label=donor"     that repeat's control is missing -> borrow the
                                            whole control (total + viability) from donor
  --viabfrom "species|time|label=donor"     that repeat's control has no green channel
                                            (red counted as total): total stays local,
                                            viability/live-dead come from donor

Usage
  python plot_650_multirepeat.py --out <dir> --focus "repeat 3" \
      --rep "repeat 1=<...>/imagej_counts" \
      --rep "repeat 2=<...>/imagej_counts_repeat2" \
      --rep "repeat 3=<...>/imagej_counts_repeat3" \
      --borrow "S.aureus|7h|repeat 2=repeat 1" \
      --viabfrom "S.aureus|24h|repeat 2=repeat 1" \
      --drop "S.aureus|5h|2|repeat 1" --exclude-3
"""
from __future__ import annotations

import argparse
import os
import sys
import textwrap

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plot_650_repeat2 as base          # noqa: E402  (shared primitives / constants)

SPECIES = base.SPECIES
TIMES = base.TIMES
AREAS = base.AREAS
AREA_SHORT = base.AREA_SHORT
SURF_COLOR = base.SURF_COLOR
C_LIVE, C_DEAD = base.C_LIVE, base.C_DEAD
K = base.K
load_raw = base.load_raw
group_stats = base.group_stats
_xmap = base._xmap
_time_labels = base._time_labels
footer = base.footer
display_table = base.display_table

MARKERS = ['o', 's', '^', 'D', 'v']


# ---------------------------------------------------------------- helpers
def norm(x):
    return x.replace('.', '').replace(' ', '').lower()


def parse_rep(spec):
    if '=' not in spec:
        raise SystemExit('--rep wants "label=dir", got %r' % spec)
    lbl, d = spec.split('=', 1)
    return lbl.strip(), d.strip()


def parse_trip(spec, n=3):
    parts = spec.split('|')
    if len(parts) != n:
        raise SystemExit('%r: expected %d |-separated fields, got %d' % (spec, n, len(parts)))
    return [p.strip() for p in parts]


def load_repeat(dirpath, exclude_3):
    out = {}
    for sp_dir, sp_label in SPECIES:
        p = os.path.join(dirpath, sp_dir, 'livedead_raw_counts.csv')
        if not os.path.isfile(p):
            print('  ! missing %s' % p)
            continue
        raw = load_raw(p)
        if exclude_3:
            raw = raw[raw.area != '3']
        out[sp_label] = raw
    return out


def apply_drop(store, label, drops):
    for sp_b, t_b, ar_b, lb in drops:
        if lb != label or sp_b not in store:
            continue
        d0 = store[sp_b]
        keep = ~((d0.time == t_b) & (d0.area == ar_b))
        n = int((~keep).sum())
        if n:
            store[sp_b] = d0[keep]
            print('  [%s] dropped %s %s area %s (%d rows) - superseded measurement'
                  % (label, sp_b, t_b, ar_b, n))


def panel_stacked_n(ax, cd, times, title, labels, marks=True, excluded=(), excl_rows=None):
    """Stacked live/dead density. Excluded slots are still PLOTTED (grey, hatched) so the
    reader sees the measurement, but they never enter a statistic."""
    xs, groups = _xmap(times, AREAS)
    excluded = set(excluded)
    ymax = 0.0
    for col in ('live_cm2', 'dead_cm2', 'total_cm2'):
        v = cd[col].max(skipna=True)
        if np.isfinite(v):
            ymax = max(ymax, float(v))
    for col in cd.columns:
        if col.startswith('r_') and col.endswith('_live'):
            v = cd[col].max(skipna=True)
            if np.isfinite(v):
                ymax = max(ymax, float(v))
    if excl_rows is not None and len(excl_rows) and not CLIP_EXCLUDED:
        v = (excl_rows['live_cm2'].fillna(0) + excl_rows['dead_cm2'].fillna(0)).max()
        if np.isfinite(v):
            ymax = max(ymax, float(v))
    v = (cd['live_cm2'].fillna(0) + cd['dead_cm2'].fillna(0)).max()
    if np.isfinite(v):
        ymax = max(ymax, float(v))
    no_data = []
    for (t, a), x in xs.items():
        if (t, a) in excluded:
            r = (excl_rows[(excl_rows.time == t) & (excl_rows.area == a)]
                 if excl_rows is not None else None)
            if r is not None and len(r) and np.isfinite(float(r['live_cm2'].iloc[0])):
                lv, dd = float(r['live_cm2'].iloc[0]), float(r['dead_cm2'].iloc[0])
                ax.bar(x, lv, 0.9, color='#BFBFBF', edgecolor='#5F5F5F', linewidth=0.5,
                       hatch='///', zorder=3)
                ax.bar(x, dd, 0.9, bottom=lv, color='#E6E6E6', edgecolor='#5F5F5F',
                       linewidth=0.5, hatch='///', zorder=3)
                # excluded slot: hatch + a distinct colour say "not used"; the number is
                # never put behind the bar or behind a word (white bbox, own colour)
                off = (lv + dd) > ymax * 0.94
                if np.isfinite(float(r['viability'].iloc[0])):
                    if off:
                        ax.text(x, ymax * 0.985, '%d%% \u25bc' % round(
                            float(r['viability'].iloc[0])), ha='center', va='top',
                            fontsize=6.4, color='#6B4F8A', fontweight='bold', zorder=9,
                            bbox=dict(boxstyle='round,pad=0.14', fc='white', ec='#BFBFBF',
                                      linewidth=0.4, alpha=0.95))
                    else:
                        ax.text(x, lv + dd + ymax * 0.014,
                                '%.0f%%' % float(r['viability'].iloc[0]),
                                ha='center', va='bottom', fontsize=6.8, color='#6B4F8A',
                                fontweight='bold', zorder=9,
                                bbox=dict(boxstyle='round,pad=0.14', fc='white', ec='#BFBFBF',
                                          linewidth=0.4, alpha=0.95))
            else:
                no_data.append((t, a))
            continue
        g = cd[(cd.time == t) & (cd.area == a)]
        if g.empty or not np.isfinite(float(g['live_cm2'].iloc[0])):
            continue
        lv, dd = float(g['live_cm2'].iloc[0]), float(g['dead_cm2'].iloc[0])
        ax.bar(x, lv, 0.9, color=C_LIVE, edgecolor='black', linewidth=0.45)
        ax.bar(x, dd, 0.9, bottom=lv, color=C_DEAD, edgecolor='black', linewidth=0.45)
        for j, lb in enumerate(labels):
            col = 'r_%d_live' % j
            if not marks or col not in g.columns:
                continue
            rv = float(g[col].iloc[0])
            if not np.isfinite(rv):
                continue
            ax.plot(x + mark_dx(len(labels), j), rv, marker=MARKERS[j % len(MARKERS)],
                    markersize=4.4, markerfacecolor='white', markeredgecolor='black',
                    markeredgewidth=0.9, zorder=5)
        if np.isfinite(float(g['viability'].iloc[0])):
            ax.text(x, lv + dd + ymax * 0.012, '%.0f%%' % float(g['viability'].iloc[0]),
                    ha='center', va='bottom', fontsize=6.8, color='#444444')
    ax.set_ylim(0, ymax * 1.14 if ymax else 1)
    if no_data:
        _mark_excluded(ax, xs, no_data, 0.0, ax.get_ylim()[1] * 0.92)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: '{:,.0f}'.format(v)))
    _time_labels(ax, times, xs, groups, AREAS)
    ax.set_ylabel('Cell density (cells/cm$^2$)', fontsize=9)
    ax.set_title(title, fontsize=10.2)
    ax.grid(axis='y', alpha=0.25)


def panel_total_n(ax, cd, times, title, labels, marks=True, notes=()):
    xs, groups = _xmap(times, AREAS)
    ymax = 0.0
    for (t, a), x in xs.items():
        g = cd[(cd.time == t) & (cd.area == a)]
        if g.empty:
            continue
        v = float(g['total_cm2'].iloc[0])
        e = float(g['total_cm2_sd'].iloc[0])
        if not np.isfinite(e):
            e = 0.0
        ax.bar(x, v, 0.9, color=SURF_COLOR[a], edgecolor='black', linewidth=0.45)
        if np.isfinite(e) and e > 0:
            ax.errorbar(x, v, yerr=e, fmt='none', ecolor='#333333', elinewidth=0.9, capsize=3)
        for j, lb in enumerate(labels):
            col = 'r_%d_total' % j
            if not marks or col not in g.columns:
                continue
            rv = float(g[col].iloc[0])
            if not np.isfinite(rv):
                continue
            ax.plot(x + mark_dx(len(labels), j), rv, marker=MARKERS[j % len(MARKERS)],
                    markersize=4.4, markerfacecolor='white', markeredgecolor='black',
                    markeredgewidth=0.9, zorder=5)
        if a != 'c':
            c = cd[(cd.time == t) & (cd.area == 'c')]
            aa_v = np.nan
            if 'aa' in cd.columns and np.isfinite(float(g['aa'].iloc[0])):
                aa_v = float(g['aa'].iloc[0])          # mean of the per-repeat AA values
            elif not c.empty:
                cc = float(c['total_cm2'].iloc[0])
                if cc and np.isfinite(cc):
                    aa_v = (cc - v) / cc * 100.0
            if np.isfinite(aa_v):
                lab = '0%' if abs(aa_v) < 0.5 else '%.0f%%' % aa_v
                ax.text(x, v + e + ymax * 0.02, lab, ha='center', va='bottom',
                        fontsize=7.0, color='#222222')
        ymax = max(ymax, v + e)
    for j, lb in enumerate(labels):
        col = 'r_%d_total' % j
        if col in cd.columns:
            v = cd[col].max(skipna=True)
            if np.isfinite(v):
                ymax = max(ymax, float(v))
    ax.set_ylim(0, ymax * 1.16 if ymax else 1)
    for t, a, msg in notes:                     # flags on individual columns
        if (t, a) in xs:
            ax.text(xs[(t, a)], ax.get_ylim()[1] * 0.99, msg, ha='center',
                    va='top', fontsize=9.5, fontweight='bold', color='#6A1B9A', zorder=8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: '{:,.0f}'.format(v)))
    _time_labels(ax, times, xs, groups, AREAS)
    ax.set_ylabel('Total cells (live + dead), cells/cm$^2$', fontsize=9)
    ax.set_title(title, fontsize=10.2)
    ax.grid(axis='y', alpha=0.25)


def _mark_excluded(ax, xs, excluded, y0, y1, label='EXCLUDED'):
    """Grey dashed box + tag in a slot removed by the exclusion registry (no data drawn)."""
    from matplotlib.patches import Rectangle
    for (t, a) in sorted(excluded):
        if (t, a) not in xs:
            continue
        x = xs[(t, a)]
        ax.add_patch(Rectangle((x - 0.44, y0), 0.88, y1 - y0, facecolor='#F2F2F2',
                               edgecolor='#9E9E9E', linestyle=(0, (2, 2)), linewidth=0.9,
                               zorder=2))
        ax.text(x, y0 + (y1 - y0) * 0.5, label, rotation=90, fontsize=6.2, color='#7A7A7A',
                fontweight='bold', ha='center', va='center', zorder=6,
                bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.9))


CLIP_EXCLUDED = False      # set from --clip-excluded in main()
MINPX = 3                  # set from --minpx in main(); printed in the footnote


def mark_dx(n, j):
    """Horizontal offset for the n per-repeat markers inside one bar."""
    if n <= 1:
        return 0.0
    step = 0.42 / (n - 1)
    return (j - (n - 1) / 2.0) * step


def legend_n(fig, labels, y=0.062):
    h = [Patch(facecolor=C_LIVE, edgecolor='black', label='Live (green channel)'),
         Patch(facecolor=C_DEAD, edgecolor='black', label='Dead (red channel)'),
         Patch(facecolor=SURF_COLOR['c'], edgecolor='black', label='Control area'),
         Patch(facecolor=SURF_COLOR['1'], edgecolor='black', label='LIPSS area'),
         Patch(facecolor=SURF_COLOR['2'], edgecolor='black', label='Nanopillar area')]
    for j, lb in enumerate(labels):
        h.append(plt.Line2D([], [], marker=MARKERS[j % len(MARKERS)], linestyle='none',
                            markerfacecolor='white', markeredgecolor='black',
                            label='%s mean' % lb))
    fig.legend(handles=h, loc='lower center', bbox_to_anchor=(0.5, y), ncol=len(h),
               frameon=False, fontsize=8.6, handlelength=1.6, columnspacing=1.4)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rep', action='append', default=[], help='"label=count dir" (repeatable)')
    ap.add_argument('--focus', default='', help='repeat label drawn on its own (default: last)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--drop', action='append', default=[], help='"species|time|area|label"')
    ap.add_argument('--borrow', action='append', default=[], help='"species|time|label=donor"')
    ap.add_argument('--viabfrom', action='append', default=[], help='"species|time|label=donor"')
    ap.add_argument('--infer', action='append', default=[], help='"species|label" (control estimate)')
    ap.add_argument('--exclusions', default='',
                    help='CSV registry of excluded points (from build_650_exclusion_registry.py); '
                         'every listed row/group is removed before any statistic')
    ap.add_argument('--exclude-3', action='store_true')
    ap.add_argument('--no-marks', action='store_true')
    ap.add_argument('--plain', action='store_true')
    ap.add_argument('--minpx', type=int, default=3,
                    help='minimum particle size used in the counting run (printed in the '
                         'footnote)')
    ap.add_argument('--clip-excluded', action='store_true',
                    help='scale both axes to the RETAINED values and draw the excluded '
                         'measurements off-scale (value printed with an arrow at the axis '
                         'edge) so the real numbers stay readable')
    a = ap.parse_args()
    global CLIP_EXCLUDED, MINPX
    CLIP_EXCLUDED = bool(a.clip_excluded)
    MINPX = int(a.minpx)
    os.makedirs(a.out, exist_ok=True)

    reps = [parse_rep(s) for s in a.rep]
    if not reps:
        raise SystemExit('need at least one --rep "label=dir"')
    labels = [lb for lb, _ in reps]
    focus = a.focus or labels[-1]
    if focus not in labels:
        raise SystemExit('--focus %r is not one of %s' % (focus, labels))
    # input order is kept for the combined figure (repeat 1, 2, 3 ...); --focus only picks
    # which repeat gets its own figure
    dirs = dict(reps)
    EXCL = []
    if a.exclusions and os.path.isfile(a.exclusions):
        ex = pd.read_csv(a.exclusions, encoding='utf-8-sig')
        ex['area'] = ex['area'].fillna('').astype(str)
        ex['field'] = pd.to_numeric(ex['field'], errors='coerce')

        def _area_str(v):
            """'2' / 'c' — the CSV round-trip turns the numeric areas into 2.0."""
            s = str(v).strip()
            if s in ('', 'nan', 'None'):
                return ''
            try:
                f = float(s)
                return str(int(f)) if f.is_integer() else s
            except ValueError:
                return s

        for _, r in ex.iterrows():
            if r['repeat'] not in labels:
                continue
            EXCL.append(dict(repeat=r['repeat'], species=str(r['species']),
                             time=str(r['time']), area=_area_str(r['area']),
                             field=(None if pd.isna(r['field']) else int(r['field'])),
                             level=str(r['level']), issue=str(r['issue'])))
        print('exclusions loaded: %d entries -> %d (repeat, species, time, area) slots'
              % (len(EXCL), len({(e['repeat'], e['species'], e['time'], e['area']) for e in EXCL})))

    drops = [parse_trip(s, 4) for s in a.drop]
    borrows = [parse_trip(s, 3) for s in a.borrow]
    viabs = [parse_trip(s, 3) for s in a.viabfrom]
    infers = [parse_trip(s, 2) for s in a.infer]

    print('repeats:', ', '.join('%s <- %s' % (lb, dirs[lb]) for lb in labels))
    store = {lb: load_repeat(dirs[lb], a.exclude_3) for lb in labels}
    store_full = {lb: {sp: d.copy() for sp, d in store[lb].items()} for lb in labels}
    if EXCL:
        for lb in labels:
            for sp, raw in list(store[lb].items()):
                m = pd.Series(False, index=raw.index)
                for e in EXCL:
                    if e['repeat'] != lb or norm(e['species']) != norm(sp):
                        continue
                    mm = (raw.time == e['time'])
                    if e['area']:
                        mm &= (raw.area == e['area'])
                    if e['field'] is not None:
                        mm &= (raw.num == e['field'])
                    m |= mm
                n = int(m.sum())
                if n:
                    store[lb][sp] = raw[~m].copy()
                    print('  [%s] %s: removed %d excluded row(s)' % (lb, sp, n))
    for lb in labels:
        print('  [%s] %s' % (lb, ', '.join('%s: %d rows' % (sp, len(d)) for sp, d in store[lb].items())))
        apply_drop(store, lb, drops)

    # views: total (red-as-total kept) + viability (both channels counted)
    tot_view, viab_view = {}, {}
    for lb in labels:
        tot_view[lb], viab_view[lb] = {}, {}
        for sp, raw in store[lb].items():
            tot_view[lb][sp] = raw
            viab_view[lb][sp] = raw[raw.live.notna()].copy()

    # ---------------- infer a control that was never measured / was contaminated -------
    # Same method as the repeat-2 delivery (references/livedead-multi-repeat-figures.md
    # §10.2): ratios treated:control taken only from timepoints whose control is a real,
    # non-red-only measurement; pooled ratio -> control estimate at the broken timepoint.
    EST = {}
    for sp_b, lb in infers:
        if lb not in labels:
            print('  ! --infer: unknown label %r' % lb)
            continue
        for sp_label in list(store[lb].keys()):
            if norm(sp_b) != norm(sp_label):
                continue
            pristine = store[lb][sp_label]                 # before borrow/viabfrom
            ratios = []
            for t in TIMES:
                c = pristine[(pristine.time == t) & (pristine.area == 'c')]
                if len(c) == 0:
                    continue
                if 'red_only' in c.columns and bool(c['red_only'].any()):
                    continue                                # contaminated: not a real control
                cm = float(c['total'].mean())
                if not cm:
                    continue
                for ar in ('1', '2'):
                    g = pristine[(pristine.time == t) & (pristine.area == ar)]
                    if len(g):
                        ratios.append((t, ar, float(g['total'].mean()) / cm))
            if not ratios:
                continue
            R = float(np.mean([r[2] for r in ratios]))
            lo = float(np.min([r[2] for r in ratios]))
            hi = float(np.max([r[2] for r in ratios]))
            for t in TIMES:
                tv = tot_view[lb][sp_label]
                cc = tv[(tv.time == t) & (tv.area == 'c')]
                real = len(cc) and not ('red_only' in cc.columns and bool(cc['red_only'].any()))
                if real:
                    continue
                vals = [float(pristine[(pristine.time == t) & (pristine.area == ar)]['total'].mean())
                        for ar in ('1', '2') if len(pristine[(pristine.time == t) & (pristine.area == ar)])]
                if not vals:
                    continue
                mt = float(np.mean(vals))
                est = mt / R
                tv = tv[~((tv.time == t) & (tv.area == 'c'))]
                row = dict(repeat='%s (control inferred)' % lb, time=t, area='c', num=0,
                           g_image='', r_image='', live=np.nan, dead=est, total=est,
                           dead_rate=np.nan, red_only=True)
                tot_view[lb][sp_label] = pd.concat([tv, pd.DataFrame([row])], ignore_index=True)
                EST[(lb, sp_label, t)] = dict(
                    treated=mt, ratio=R, lo=lo, hi=hi, n_pairs=len(ratios), est=est,
                    lo_c=mt / hi, hi_c=mt / lo,
                    basis='; '.join('%s@%s %.3f' % ('LIPSS' if r[1] == '1' else 'Nano', r[0], r[2])
                                    for r in ratios))
                print('  [%s] %s %s control inferred -> %.0f cells/field (range %.0f-%.0f); '
                      'pooled treated:control ratio %.3f from %d pairs'
                      % (lb, sp_label, t, est, mt / hi, mt / lo, R, len(ratios)))
    if EST:
        pd.DataFrame([dict(species=k[1], time=k[2], repeat=k[0], treated_mean=v['treated'],
                           ratio_mean=v['ratio'], ratio_min=v['lo'], ratio_max=v['hi'],
                           n_pairs=v['n_pairs'], control_est=v['est'],
                           control_lo=v['lo_c'], control_hi=v['hi_c'], basis=v['basis'])
                      for k, v in sorted(EST.items())]).to_csv(
            os.path.join(a.out, '650nm_control_inference.csv'), index=False, encoding='utf-8-sig')

    # borrow the whole control / only the viability of a contaminated control
    for kind, specs, target in (('borrow', borrows, (tot_view, viab_view)),
                                ('viabfrom', viabs, (viab_view,))):
        for sp_b, t_b, rest in specs:
            if '=' not in rest:
                raise SystemExit('%s wants "label=donor", got %r' % (kind, rest))
            lb, donor = [x.strip() for x in rest.split('=', 1)]
            if lb not in labels or donor not in labels:
                print('  ! %s: unknown label in %r' % (kind, rest))
                continue
            for sp_label in list(store[lb].keys()):
                if norm(sp_b) != norm(sp_label):
                    continue
                for views in target:
                    have = views[lb][sp_label]
                    if len(have[(have.time == t_b) & (have.area == 'c')]):
                        continue
                    d0 = store[donor].get(sp_label)
                    if d0 is None:
                        continue
                    src = d0 if views is tot_view[lb] else d0[d0.live.notna()]
                    donor_rows = src[(src.time == t_b) & (src.area == 'c')].copy()
                    if not len(donor_rows):
                        continue
                    donor_rows['repeat'] = '%s (borrowed from %s)' % (lb, donor)
                    views[lb][sp_label] = pd.concat([views[lb][sp_label], donor_rows],
                                                    ignore_index=True)
                    if views is target[-1]:
                        print('  [%s] %s %s control <- %s (%d fields, %s)'
                              % (lb, sp_label, t_b, donor, len(donor_rows), kind))

    # same views/tables built from the FULL data: used only to DRAW the excluded points
    full_tot, full_viab, tables_full = {}, {}, {}
    for lb in labels:
        full_tot[lb], full_viab[lb], tables_full[lb] = {}, {}, {}
        for sp, raw in store_full[lb].items():
            full_tot[lb][sp] = raw
            full_viab[lb][sp] = raw[raw.live.notna()].copy()
            times_f = [t for t in TIMES if t in set(raw.time)]
            tables_full[lb][sp] = display_table(full_tot[lb][sp], full_viab[lb][sp], times_f)

    # per-repeat display tables (what figure A uses, focus repeat only)
    tables = {lb: {} for lb in labels}
    for lb in labels:
        for sp in store[lb]:
            times = [t for t in TIMES if t in set(tot_view[lb][sp].time)]
            tables[lb][sp] = display_table(tot_view[lb][sp], viab_view[lb][sp], times)
        # one summary CSV per repeat, so downstream figure/report code never re-prepares data
        rows_lb = [tables[lb][sp].assign(species=sp) for _, sp in SPECIES if sp in tables[lb]]
        if rows_lb:
            pd.concat(rows_lb).to_csv(
                os.path.join(a.out, '650nm_livedead_%s_summary.csv' % lb.replace(' ', '')),
                index=False, encoding='utf-8-sig')

    # ---------------- per-repeat anti-adhesion, total + live, with delta-method SD ----
    def _aa(ctrl_vals, trt_vals):
        """Anti-adhesion + delta-method SD.

        An inferred control is a SINGLE synthetic row (the estimated level), so the usual
        two-sample delta method cannot run on it: fall back to propagating only the SD of
        the treated mean in that case (and say so in the figure footnote)."""
        trt_vals = trt_vals[np.isfinite(trt_vals)] if len(trt_vals) else trt_vals
        ctrl_vals = ctrl_vals[np.isfinite(ctrl_vals)] if len(ctrl_vals) else ctrl_vals
        if len(trt_vals) < 2 or len(ctrl_vals) < 1:
            return np.nan, np.nan
        if len(ctrl_vals) >= 2:
            v, sd = base.aa_with_sd(ctrl_vals, trt_vals)
            return float(v), float(sd)
        c = float(np.mean(ctrl_vals))
        if not c:
            return np.nan, np.nan
        m = float(np.mean(trt_vals))
        se = float(np.std(trt_vals, ddof=1)) / np.sqrt(len(trt_vals))
        return (c - m) / c * 100.0, 100.0 * se / c

    aa_rows = []
    for sp_dir, sp_label in SPECIES:
        have = [lb for lb in labels if sp_label in tables[lb]]
        if not have:
            continue
        times = [t for t in TIMES if any(t in set(tables[lb][sp_label].time) for lb in have)]
        for t in times:
            for ar in ('1', '2'):
                row = dict(species=sp_label, time=t, area=ar)
                tot_v, live_v, tot_sd, live_sd = [], [], [], []
                for lb in have:
                    cT = tot_view[lb][sp_label]
                    cV = viab_view[lb][sp_label]
                    at, ats = _aa(cT[(cT.time == t) & (cT.area == 'c')]['total'].astype(float),
                                  cT[(cT.time == t) & (cT.area == ar)]['total'].astype(float))
                    al, als = _aa(cV[(cV.time == t) & (cV.area == 'c')]['live'].astype(float),
                                  cV[(cV.time == t) & (cV.area == ar)]['live'].astype(float))
                    row['%s_AA%%' % lb] = at
                    row['%s_AA%%_sd' % lb] = ats
                    row['%s_AAlive%%' % lb] = al
                    row['%s_AAlive%%_sd' % lb] = als
                    tot_v.append(at)
                    live_v.append(al)
                    tot_sd.append(ats)
                    live_sd.append(als)
                row['combined_AA%'] = float(np.nanmean(tot_v)) if np.isfinite(tot_v).any() else np.nan
                row['combined_AAlive%'] = float(np.nanmean(live_v)) if np.isfinite(live_v).any() else np.nan
                row['aa'] = row['combined_AA%']
                row['aa_sd'] = (float(np.nanstd(tot_v, ddof=1))
                                if np.isfinite(tot_v).sum() > 1 else np.nan)
                row['aa_live'] = row['combined_AAlive%']
                row['aa_live_sd'] = (float(np.nanstd(live_v, ddof=1))
                                     if np.isfinite(live_v).sum() > 1 else np.nan)
                row['n_aa'] = int(np.isfinite(tot_v).sum())
                row['repeats'] = ','.join(have)
                aa_rows.append(row)
    AA = pd.DataFrame(aa_rows)
    AA.to_csv(os.path.join(a.out, '650nm_livedead_perrepeat_aa.csv'), index=False,
              encoding='utf-8-sig')

    # AA recomputed on the FULL data, only so the excluded slots can still be drawn.
    # No anti-adhesion is shown when the CONTROL itself is unusable (never imaged, contaminated
    # red-only coupon, or excluded): a ratio against a broken control is not a number worth
    # showing even in grey.
    AAX = {}
    excl_ctrl = {(e['repeat'], norm(e['species']), e['time']) for e in EXCL
                 if e['area'] in ('', 'c')}
    for lb in labels:
        for sp_label in tables_full[lb]:
            cT = full_tot[lb][sp_label]
            cV = full_viab[lb][sp_label]
            for t in TIMES:
                cinfo = cT[(cT.time == t) & (cT.area == 'c')]
                ctrl_bad = ((lb, norm(sp_label), t) in excl_ctrl
                            or len(cinfo) == 0
                            or bool(cinfo['red_only'].any()))
                for ar in ('1', '2'):
                    if ctrl_bad:
                        continue
                    at, _ = _aa(cT[(cT.time == t) & (cT.area == 'c')]['total'].astype(float),
                                cT[(cT.time == t) & (cT.area == ar)]['total'].astype(float))
                    al, _ = _aa(cV[(cV.time == t) & (cV.area == 'c')]['live'].astype(float),
                                cV[(cV.time == t) & (cV.area == ar)]['live'].astype(float))
                    if np.isfinite(at) or np.isfinite(al):
                        AAX[(lb, sp_label, t, ar)] = dict(total=at, live=al)

    # ================= figures: left = live/dead density, right = anti-adhesion ========
    # One figure per repeat plus one combined figure. The right-hand panel is the
    # anti-adhesion rate ITSELF (% fewer cells than the control of the same timepoint),
    # not the density with a percentage label: positive up = fewer cells than control,
    # negative down = more cells than control.
    if EST:
        pd.DataFrame([dict(species=k[1], time=k[2], repeat=k[0], treated_mean=v['treated'],
                           ratio_mean=v['ratio'], ratio_min=v['lo'], ratio_max=v['hi'],
                           n_pairs=v['n_pairs'], control_est=v['est'],
                           control_lo=v['lo_c'], control_hi=v['hi_c'], basis=v['basis'])
                      for k, v in sorted(EST.items())]).to_csv(
            os.path.join(a.out, '650nm_control_inference.csv'), index=False,
            encoding='utf-8-sig')

    def aa_panel(ax, aa, sp_label, times, title, labels, marks=True, est_times=(),
                 excluded=(), excl_aa=None):
        """Grouped anti-adhesion bars: per area a solid (total cells) + lighter (live cells)."""
        excluded_set = set(excluded)
        xbase = {t: i * 3.0 for i, t in enumerate(times)}
        ymin, ymax, vals = 0.0, 0.0, []
        vals_ok = []
        for t in times:
            g = aa[(aa.species == sp_label) & (aa.time == t)]
            for ar, dx in (('1', -0.62), ('2', 0.62)):
                if (t, ar) in excluded_set:
                    ex = (excl_aa or {}).get((t, ar))
                    if ex:
                        for key in ('total', 'live'):
                            v = ex.get(key, np.nan)
                            if np.isfinite(v):
                                vals.append((v, v))
                    continue
                r = g[g.area == ar]
                if r.empty:
                    continue
                for col, sdcol in (('combined_AA%', 'aa_sd'), ('combined_AAlive%', 'aa_live_sd')):
                    v = r[col].iloc[0]
                    if not np.isfinite(v):
                        continue
                    sd = r[sdcol].iloc[0]
                    sd = float(sd) if np.isfinite(sd) else 0.0
                    vals.append((v - sd, v + sd))
                    vals_ok.append((v - sd, v + sd))
        for lo, hi in (vals_ok if (CLIP_EXCLUDED and vals_ok) else vals):
            ymin, ymax = min(ymin, lo), max(ymax, hi)
        span = max(ymax - ymin, 10.0)
        ymin, ymax = ymin - span * 0.14, ymax + span * 0.16

        no_aa = set()
        for t in times:
            g = aa[(aa.species == sp_label) & (aa.time == t)]
            for ar, dx in (('1', -0.62), ('2', 0.62)):
                if (t, ar) in excluded_set:
                    # still show the measurement: grey, hatched, never used in a statistic
                    ex = (excl_aa or {}).get((t, ar))
                    if ex and (np.isfinite(ex['total']) or np.isfinite(ex['live'])):
                        for key, w, off, alpha in (('total', 0.42, -0.22, 1.0),
                                                   ('live', 0.30, 0.25, 0.45)):
                            v = ex[key]
                            if not np.isfinite(v):
                                continue
                            x = xbase[t] + dx + off
                            ax.bar(x, v, w, color='#BFBFBF' if key == 'total' else '#E6E6E6',
                                   edgecolor='#5F5F5F', linewidth=0.45, hatch='///',
                                   alpha=alpha, zorder=3)
                            if key == 'total' and abs(v) >= 3:
                                if v < ymin or v > ymax:
                                    clipped_log.append((sp_label, t, ar, v))
                                    ylab = ymin + span * 0.075 if v < ymin else ymax - span * 0.075
                                    txt = ('%.0f' % v) + (' \u25bc' if v < ymin else ' \u25b2')
                                    va = 'bottom' if v < ymin else 'top'
                                else:
                                    ylab = v + (span * 0.015 if v >= 0 else -span * 0.015)
                                    txt = '%.0f' % v
                                    va = 'bottom' if v >= 0 else 'top'
                                ax.text(x, ylab, txt, ha='center', va=va, fontsize=6.2,
                                        color='#6B4F8A', fontweight='bold', zorder=9,
                                        bbox=dict(boxstyle='round,pad=0.14', fc='white',
                                                  ec='#BFBFBF', linewidth=0.4, alpha=0.95))
                        # no per-bar 'excluded' word any more: it used to sit over the bar
                        # and its number. Hatch + the violet value + the legend key carry it.
                    else:
                        no_aa.add((t, ar))
                    continue
                r = g[g.area == ar]
                if r.empty:
                    continue
                for col, sdcol, w, off, alpha, label_it in (
                        ('combined_AA%', 'aa_sd', 0.42, -0.22, 1.0, True),
                        ('combined_AAlive%', 'aa_live_sd', 0.30, 0.25, 0.32, False)):
                    v = r[col].iloc[0]
                    if not np.isfinite(v):
                        continue
                    sd = r[sdcol].iloc[0]
                    sd = float(sd) if np.isfinite(sd) else 0.0
                    x = xbase[t] + dx + off
                    ax.bar(x, v, w, color=SURF_COLOR[ar], edgecolor='#444444' if label_it
                           else '#888888', linewidth=0.45, alpha=alpha, zorder=3)
                    if sd > 0:
                        ax.errorbar(x, v, yerr=sd, fmt='none', ecolor='#333333',
                                    elinewidth=0.8, capsize=2.2, zorder=4)
                    if marks and len(labels) > 1 and label_it:
                        for j, lb in enumerate(labels):
                            col_r = '%s_AA%%' % lb
                            rv = r[col_r].iloc[0] if col_r in r.columns else np.nan
                            if not np.isfinite(rv):
                                continue
                            ax.plot(x, rv, marker=MARKERS[j % len(MARKERS)], markersize=3.2,
                                    markerfacecolor='white', markeredgecolor='black',
                                    markeredgewidth=0.75, zorder=6)
                    if label_it and abs(v) >= 3:
                        # above/below the error-bar end so the label never sits on a stem
                        ylab = (v + sd) if v >= 0 else (v - sd)
                        ax.text(x, ylab + (span * 0.015 if v >= 0 else -span * 0.015),
                                '%.0f' % v, ha='center',
                                va='bottom' if v >= 0 else 'top', fontsize=6.2, color='#222222',
                                zorder=7,
                                bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none',
                                          alpha=0.9))
        ax.axhline(0, color='black', linewidth=0.9)
        ax.set_ylim(ymin, ymax)
        xs_ex = {(t, ar): xbase[t] + (-0.62 if ar == '1' else 0.62)
                 for (t, ar) in no_aa if t in xbase and ar in ('1', '2')}
        if xs_ex:
            _mark_excluded(ax, xs_ex, set(xs_ex), ymin, ymax, label='EXCLUDED')
        ax.set_xticks([xbase[t] + dx for t in times for dx in (-0.62, 0.62)])
        ax.set_xticklabels(['LIPSS' if dx < 0 else 'Nano' for t in times for dx in (-0.62, 0.62)],
                           fontsize=7.2)
        for t in times:
            mark = ' $\\S$' if t in est_times else ''
            ax.text(xbase[t], -0.155, t + mark, transform=ax.get_xaxis_transform(),
                    ha='center', fontsize=10.5, fontweight='bold')
        ax.set_xlim(-1.6, (len(times) - 1) * 3.0 + 1.6)
        ax.set_ylabel('Anti-adhesion (%)   + = fewer cells than control', fontsize=9)
        ax.set_title(title, fontsize=10.2)
        ax.grid(axis='y', alpha=0.25)

    def aa_legend(fig, labels, y=0.062):
        h = [Patch(facecolor='#777777', edgecolor='#444444', label='Total cells (live + dead)'),
             Patch(facecolor='#777777', edgecolor='#888888', alpha=0.32,
                   label='Live cells only'),
             Patch(facecolor='#BFBFBF', edgecolor='#5F5F5F', hatch='///',
                   label='Excluded (shown, not used)'),
             Patch(facecolor=SURF_COLOR['1'], edgecolor='black', label='LIPSS area'),
             Patch(facecolor=SURF_COLOR['2'], edgecolor='black', label='Nanopillar area'),
             Patch(facecolor=C_LIVE, edgecolor='black', label='Live'),
             Patch(facecolor=C_DEAD, edgecolor='black', label='Dead')]
        for j, lb in enumerate(labels):
            h.append(plt.Line2D([], [], marker=MARKERS[j % len(MARKERS)], linestyle='none',
                                markerfacecolor='white', markeredgecolor='black',
                                label='%s mean' % lb))
        fig.legend(handles=h, loc='lower center', bbox_to_anchor=(0.5, y), ncol=len(h),
                   frameon=False, fontsize=8.2, handlelength=1.5, columnspacing=1.3)

    # per-repeat AA table -> one frame per repeat and one combined frame
    def frame_stats(lb):
        """Stats table for the left panel: one repeat, or the combined means."""
        out = {}
        if lb == 'combined':
            for _, sp in SPECIES:
                rows = []
                for t in TIMES:
                    for ar in AREAS:
                        vals = [tables[x][sp][(tables[x][sp].time == t) &
                                              (tables[x][sp].area == ar)] for x in labels
                                if sp in tables[x]]
                        vals = [v for v in vals if len(v)]
                        if not vals:
                            continue
                        def m(col):
                            v = [float(x[col].iloc[0]) for x in vals
                                 if np.isfinite(float(x[col].iloc[0]))]
                            return (float(np.mean(v)) if v else np.nan,
                                    float(np.std(v, ddof=1)) if len(v) > 1 else np.nan)
                        live, live_sd = m('live_cm2')
                        dead, dead_sd = m('dead_cm2')
                        total, total_sd = m('total_cm2')
                        viab, _ = m('viability')
                        rows.append(dict(species=sp, time=t, area=ar, n=len(vals),
                                         live_cm2=live, live_sd=live_sd, dead_cm2=dead,
                                         dead_sd=dead_sd, total_cm2=total,
                                         total_cm2_sd=total_sd, viability=viab,
                                         total_sd=total_sd))
                out[sp] = pd.DataFrame(rows)
        else:
            for _, sp in SPECIES:
                if sp in tables.get(lb, {}):
                    st = tables[lb][sp].copy()
                    st['total_sd'] = st['total_cm2_sd']
                    out[sp] = st
        return out

    clipped_log = []
    for lb in list(labels) + (['combined'] if len(labels) > 1 else []):
        clipped_log.clear()
        fs = frame_stats(lb)
        if not fs:
            continue
        is_comb = lb == 'combined'
        if is_comb:
            rows_c = [fs[sp].assign(species=sp) for _, sp in SPECIES if sp in fs]
            pd.concat(rows_c).to_csv(
                os.path.join(a.out, '650nm_livedead_combined_summary.csv'),
                index=False, encoding='utf-8-sig')
        fig, axes = plt.subplots(2, 2, figsize=(14.2, 9.6), dpi=200)
        for i, (_, sp_label) in enumerate(SPECIES):
            if sp_label not in fs:
                continue
            st = fs[sp_label]
            ex_times = ({e['time'] for e in EXCL
                         if e['repeat'] == lb and norm(e['species']) == norm(sp_label)}
                        if not is_comb else set())
            # keep the excluded incubation points on the axis so they can be shown as excluded
            times = [t for t in TIMES if t in set(st.time) or t in ex_times]
            ex_slots = set()
            if not is_comb:
                for e in EXCL:
                    if e['repeat'] != lb or norm(e['species']) != norm(sp_label):
                        continue
                    if e['area']:
                        ex_slots.add((e['time'], e['area']))
                    else:
                        ex_slots.update((e['time'], ar) for ar in AREAS)
            excl_rows = (None if is_comb
                         else tables_full.get(lb, {}).get(sp_label))
            excl_aa = (None if is_comb else
                       {(k[2], k[3]): v for k, v in AAX.items()
                        if k[0] == lb and k[1] == sp_label})
            panel_stacked_n(axes[i, 0], st, times,
                            '(%s) %s - live + dead density (cells/cm$^2$)'
                            % ('ac'[i], sp_label),
                            labels if is_comb else [], marks=not a.no_marks,
                            excluded=ex_slots, excl_rows=excl_rows)
            est_times = {k[2] for k in EST if k[0] == lb and norm(k[1]) == norm(sp_label)}
            marks = (not a.no_marks) and is_comb
            aa_panel(axes[i, 1], AA, sp_label, times,
                     '(%s) %s - anti-adhesion vs the control of the same timepoint'
                     % ('bd'[i], sp_label), labels if is_comb else [], marks=marks,
                     est_times=est_times, excluded=ex_slots, excl_aa=excl_aa)
        if is_comb:
            # show, in grey, the per-repeat values that the registry removed: visible but not
            # part of any bar, mean or error bar
            for j, lbx in enumerate(labels):
                tf = tables_full.get(lbx, {})
                for _, sp_label in SPECIES:
                    if sp_label not in tf:
                        continue
                    axx = (axes[0, 0] if sp_label == 'E. coli' else axes[1, 0])
                    aax = (axes[0, 1] if sp_label == 'E. coli' else axes[1, 1])
                    tr = tf[sp_label]
                    dx_t = {t: i * 3.0 for i, t in enumerate(
                        [x for x in TIMES if x in set(tr.time)])}
                    dx_a = {t: i * 3.0 for i, t in enumerate(
                        [x for x in TIMES if x in set(tr.time)])}
                    for e in EXCL:
                        if e['repeat'] != lbx or norm(e['species']) != norm(sp_label):
                            continue
                        areas = [e['area']] if e['area'] else AREAS
                        for ar in areas:
                            if ar not in ('1', '2') and ar != 'c':
                                continue
                            g = tr[(tr.time == e['time']) & (tr.area == ar)]
                            if len(g) and np.isfinite(float(g['total_cm2'].iloc[0])) \
                                    and e['time'] in dx_t:
                                x = dx_t[e['time']] + AREAS.index(ar) * 1.05 - 1.05
                                axx.plot(x + mark_dx(len(labels), j),
                                         float(g['total_cm2'].iloc[0]), marker='x',
                                         markersize=5.0, markeredgewidth=1.2,
                                         color='#9E9E9E', zorder=7)
                            k = (lbx, sp_label, e['time'], ar)
                            if ar in ('1', '2') and k in AAX and e['time'] in dx_a:
                                v = AAX[k]['total']
                                if np.isfinite(v):
                                    x = dx_a[e['time']] + (-0.62 if ar == '1' else 0.62) - 0.22
                                    aax.plot(x + mark_dx(len(labels), j), v, marker='x',
                                             markersize=5.0, markeredgewidth=1.2,
                                             color='#9E9E9E', zorder=7)
        ttl = ('650 nm textured stainless steel - LIVE/DEAD, %s' % lb if not is_comb else
               '650 nm textured stainless steel - LIVE/DEAD, %s combined'
               % ' + '.join(labels))
        fig.suptitle(ttl + ('  (control estimated - see footnote)' if any(
            k[0] == lb for k in EST) else ''), fontsize=12.5, y=0.975)
        aa_legend(fig, labels if marks else [], y=0.079)
        note = ('Left: bars = mean of 5 fields, error bars = SD of the 5 fields, % over the '
                'stacked bar = pooled viability. Right: anti-adhesion = (N_control - N_surface) '
                '/ N_control x 100 for total cells (solid) and live cells (hatched); positive = '
                'fewer cells than the untreated control area of the same coupon, negative = more '
                'cells than the control. Error bars = delta-method SD')
        note += (' across the %d repeats; empty markers = the individual repeat AA values and '
                 'the bar = their mean.' % len(labels) if is_comb else ' of the field means')
        note += ('. ImageJ 1.54, adaptive threshold (background mode + 40), size %d-500 px, '
                 % MINPX + 
                 '40x field area 46 946 um2, n = 5 fields per condition.')
        if any(k[0] == lb for k in EST):
            bits = ['%s %s: control not measurable -> estimated %.0f-%.0f cells/field'
                    % (k[1], k[2], v['lo_c'], v['hi_c']) for k, v in sorted(EST.items())
                    if k[0] == lb]
            note += ('  section sign = control inferred from the treated:control ratio at the '
                     'timepoints with a real control - estimate, not a measurement ('
                     + '; '.join(bits) + '); those bars are qualitative only.')
        drop_hits = [d for d in drops if d[3] == lb]
        if EXCL:
            ex_lbl = [e for e in EXCL if e['repeat'] == lb]
            if is_comb:
                by_t = {}
                for e in EXCL:
                    by_t.setdefault((e['time'], e['species']), []).append(e)
                bits = ['%s %s: %s excluded (%s)'
                        % (k[0], k[1], ', '.join(sorted({x['repeat'] for x in v})),
                           '; '.join(sorted({x['issue'] for x in v})))
                        for k, v in sorted(by_t.items())]
                note += ('  EXCLUDED DATA (grey x markers = the per-repeat values that the registry '
                         'removed; they are shown for completeness but are not part of any bar, '
                         'mean or error bar): '
                         + '; '.join(bits) + '.')
            elif ex_lbl:
                bits = ['%s %s %s - %s'
                        % (e['time'], e['species'],
                           ('whole timepoint' if not e['area']
                            else AREA_SHORT.get(e['area'], e['area']).replace(chr(10), ' ')),
                           e['issue'])
                        for e in ex_lbl]
                note += ('  EXCLUDED DATA in this repeat (not used in any statistic, shown as a '
                         'grey cross): ' + '; '.join(bits) + '.')
        if clipped_log:
            note += ('  Axis scaled to the retained measurements: the excluded bar(s) marked '
                     'with an arrow at the axis edge are far larger than the rest and would '
                     'otherwise flatten the plot - %s.'
                     % '; '.join('%s %s %s at %+.0f %%'
                                 % (s, tt, AREA_SHORT.get(ar, ar).replace(chr(10), ' '), vv)
                                 for s, tt, ar, vv in clipped_log))
        if drop_hits:
            note += ('  Omitted from this repeat (staining artefact, superseded by the re-shot '
                     'coupon): ' + '; '.join('%s %s %s'
                                             % (d[0], d[1], AREA_SHORT.get(d[2], d[2]).replace(chr(10), ' '))
                                             for d in drop_hits) + '.')
        if a.exclude_3:
            note += '  Extra re-shot coupon (sample 3) excluded from every statistic.'
        footer(fig, note, False, y=0.004, fontsize=6.6, width=190)
        fig.tight_layout(rect=(0, 0.118, 1, 0.95))
        name = ('650nm_livedead_combined_%s_AA.png'
                % ''.join(x.replace('repeat', 'r').replace(' ', '') for x in labels)
                if is_comb else '650nm_livedead_%s_AA.png' % lb.replace(' ', ''))
        p = os.path.join(a.out, name)
        fig.savefig(p)
        plt.close(fig)
        print('figure:', p)

    AA.to_csv(os.path.join(a.out, '650nm_livedead_perrepeat_aa.csv'), index=False,
              encoding='utf-8-sig')
    print('AA table:', os.path.join(a.out, '650nm_livedead_perrepeat_aa.csv'))


if __name__ == '__main__':
    main()
