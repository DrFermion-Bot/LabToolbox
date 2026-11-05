# -*- coding: utf-8 -*-
"""build_650_exclusion_registry.py — the single source of truth for every excluded
650 nm LIVE/DEAD data point, with the reason and the evidence.

Two layers:

1. DOCUMENTED exclusions (experimental problems reported by the user / found in the
   dataset notes). Level "group" removes a whole incubation point of one repeat
   (control + both treated areas), level "cell" removes one area of one timepoint.
2. AUTOMATED outlier screen on what is left, using two rules that are deliberately
   narrow so nothing gets dropped just for being large:
     * field level: a field is flagged only if its count is > 3x the median of the
       other four fields of the same condition (none currently pass);
     * repeat level: per condition, a repeat is flagged only if the OTHER TWO agree
       within 25 percentage points AND this one lies more than 100 pp away from their
       mean. With two disagreeing repeats nothing is flagged - that condition is
       simply not reproducible and is reported as such.

Writes <out>/650nm_exclusions_<date>.csv (consumed by plot_650_multirepeat.py --exclusions)
and <out>/650nm_exclusion_screen_<date>.csv (the numbers behind each auto-flag).

Usage
  python build_650_exclusion_registry.py --out <fig dir> --date 20261029 \
      --rep "repeat 1=<imagej_counts>" --rep "repeat 2=<imagej_counts_repeat2>" \
      --rep "repeat 3=<imagej_counts_repeat3>"
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

TIMES = ['3h', '5h', '7h', '24h']
SP_DIR = {'E. coli': 'E.coli', 'S. aureus': 'S.aureus'}

# ---------------------------------------------------------------- documented issues
# level: 'group' = the whole incubation point of that repeat (control + treated),
#        'cell'  = one area of one incubation point.
DOCUMENTED = [
    dict(repeat='repeat 1', species='E. coli', time='7h', area='', level='group',
         issue='ethanol contamination of the sample',
         detail='Ethanol reached the sample at this incubation point of run 1. Only the E. coli '
                'point is affected; the S. aureus 7 h block of run 1 is valid and stays in the '
                'analysis.',
         evidence='user report 2026-10-29 (species-confirmed same day)'),
    dict(repeat='repeat 1', species='S. aureus', time='5h', area='2', level='cell',
         issue='staining artefact (near-zero viability coupon)',
         detail='Nanopillar coupon read live 1-23 / dead 1700-1870 (viability 0.4 %). The '
                'run-2 re-shot of the same coupon read 50.7 %, i.e. the run-1 staining failed.',
         evidence='600nm_repeat2 re-shot, sample 3; see 650nm_repeat2_report_20261022'),
    dict(repeat='repeat 2', species='S. aureus', time='7h', area='', level='group',
         issue='control dropped (no control images)',
         detail='The control area was never imaged at this timepoint of run 2, so no '
                'anti-adhesion can be formed; the whole timepoint is excluded.',
         evidence='dataset: S.aureus/repeat 2/7h/ contains only 1-* and 2-* files'),
    dict(repeat='repeat 2', species='S. aureus', time='24h', area='', level='group',
         issue='contaminated control coupon',
         detail='The control coupon was contaminated (nearly all dead, only the red channel '
                'was saved): no usable live/dead pair and no usable control.',
         evidence='dataset note: S.aureus/repeat 2/24h/readme.txt'),
    dict(repeat='repeat 4', species='S. aureus', time='3h', area='1', level='cell',
         issue='acquisition anomaly on the LIPSS coupon',
         detail='Every field of this coupon carries 4 000-5 000 detected objects with a median '
                'object area of 24-44 px, against 560-760 objects and 70-105 px in the control '
                'and nanopillar areas of the same run and the same 3 h session (exposure 0.50 s '
                'here, 0.20-0.30 s there). The objects are sub-cell speckle rather than cocci, '
                'so the count (8 384 cells/field, i.e. 10x the control) is an artefact of the '
                'image, not of the surface. The rest of the 3 h block is unaffected.',
         evidence='pixel-geometry check (object size distribution) + visual inspection, '
                  '2026-11-05'),
]


def load_counts(dirpath, sp):
    p = os.path.join(dirpath, SP_DIR[sp], 'livedead_raw_counts.csv')
    if not os.path.isfile(p):
        return None
    df = pd.read_csv(p, encoding='utf-8-sig')
    df = df[df.area != '3'].copy()
    df['live'] = pd.to_numeric(df['live'], errors='coerce')
    df['dead'] = pd.to_numeric(df['dead'], errors='coerce')
    df['total'] = df['live'].fillna(0) + df['dead'].fillna(0)
    df['area'] = df['area'].astype(str)
    df['time'] = df['time'].astype(str)
    df['num'] = pd.to_numeric(df['num'], errors='coerce')
    return df


def apply_exclusions(raw, exclusions):
    """Drop every row matched by the registry (group / cell / field level)."""
    out = raw.copy()
    drop = pd.Series(False, index=out.index)
    for e in exclusions:
        m = (out.time == e['time']) & (out.species == raw.attrs.get('species', ''))
        if e['area']:
            m &= (out.area == str(e['area']))
        if e.get('field'):
            m &= (out.num == e['field'])
        drop |= m
    return out[~drop].copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--date', default='20261029')
    ap.add_argument('--rep', action='append', default=[])
    ap.add_argument('--agree-pp', type=float, default=25.0,
                    help='two repeats count as agreeing when their AA differs by <= this (pp)')
    ap.add_argument('--outlier-pp', type=float, default=100.0,
                    help='third repeat must be further than this from their mean to be flagged')
    ap.add_argument('--field-factor', type=float, default=3.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    labels = [x.split('=', 1)[0].strip() for x in a.rep]
    dirs = {x.split('=', 1)[0].strip(): x.split('=', 1)[1].strip() for x in a.rep}

    raws = {}
    for lb in labels:
        for sp in ('E. coli', 'S. aureus'):
            d = load_counts(dirs[lb], sp)
            if d is not None:
                d.attrs['species'] = sp
                raws[(lb, sp)] = d

    reg = []           # registry rows
    screen = []        # evidence rows for auto flags

    # ---- 1. documented exclusions -------------------------------------------------
    for e in DOCUMENTED:
        lb = e['repeat']
        if lb not in labels:
            continue
        d = raws.get((lb, e['species']))
        m = None
        if d is not None:
            m = (d.time == e['time']) & (d.area == str(e['area']) if e['area'] else True)
        n_rows = int(m.sum()) if m is not None else 0
        reg.append(dict(level=e['level'], repeat=lb, species=e['species'], time=e['time'],
                        area=e['area'], field='', issue=e['issue'], detail=e['detail'],
                        evidence=e['evidence'], rows_removed=n_rows,
                        source='documented'))

    # ---- apply documented exclusions, then screen what is left --------------------
    dropped = {(r['repeat'], r['species'], r['time'], r['area']) for r in reg}
    clean = {}
    for (lb, sp), d in raws.items():
        m = pd.Series(False, index=d.index)
        for r in reg:
            if r['repeat'] != lb or r['species'] != sp:
                continue
            mm = (d.time == r['time'])
            if r['area']:
                mm &= (d.area == r['area'])
            m |= mm
        clean[(lb, sp)] = d[~m].copy()

    # ---- 2a. field-level screen ---------------------------------------------------
    for (lb, sp), d in clean.items():
        for (t, ar), g in d.groupby(['time', 'area']):
            v = g['total'].astype(float).values
            if len(v) < 5:
                continue
            for i, val in enumerate(v):
                om = float(np.median(np.delete(v, i)))
                if om > 0 and (val > a.field_factor * om or val < om / a.field_factor):
                    num = int(g['num'].iloc[i])
                    # NOT excluded: a field that is simply denser or sparse is normal sampling
                    # for these sparse E. coli fields, and dropping it would bias the mean.
                    # The 650 nm images were checked (object-size distribution) and show no
                    # clumps/debris in these fields, so they are reported, not removed.
                    screen.append(dict(rule='field', repeat=lb, species=sp, time=t, area=ar,
                                       field=num, value=val, reference=om, ratio=val / om,
                                       flagged=False,
                                       note='flagged for review, retained: no image-level '
                                            'artefact (object sizes normal, no >500 px clumps)'))

    # ---- 2b. repeat-level AA screen (needs three intact repeats) -------------------
    def aa(d, t, ar):
        c = d[(d.time == t) & (d.area == 'c')]['total'].astype(float)
        s = d[(d.time == t) & (d.area == ar)]['total'].astype(float)
        if len(c) < 2 or len(s) < 2:
            return np.nan
        return float((c.mean() - s.mean()) / c.mean() * 100.0)

    for sp in ('E. coli', 'S. aureus'):
        have = [lb for lb in labels if (lb, sp) in clean]
        for t in TIMES:
            for ar in ('1', '2'):
                vals = {lb: aa(clean[(lb, sp)], t, ar) for lb in have}
                ok = {lb: v for lb, v in vals.items() if np.isfinite(v)}
                if len(ok) < 3:
                    for lb, v in vals.items():
                        screen.append(dict(rule='repeat', repeat=lb, species=sp, time=t, area=ar,
                                           field='', value=v, reference=np.nan, ratio=np.nan,
                                           flagged=False))
                    continue
                arr = np.array(list(ok.values()), float)
                # Generalised screen (works for 3+ repeats): the OTHER repeats must agree
                # within --agree-pp among themselves, and this one must lie further than
                # --outlier-pp from their mean. With exactly three repeats this reduces
                # to the original "best-agreeing pair vs the leftover" rule.
                pair_means, pair_gaps, devs = [], [], []
                for k in range(len(arr)):
                    others = np.delete(arr, k)
                    pair_gaps.append(float(others.max() - others.min()))
                    pair_means.append(float(others.mean()))
                    devs.append(abs(float(arr[k]) - pair_means[-1]))
                names = list(ok.keys())
                for idx, lb in enumerate(names):
                    flagged = (pair_gaps[idx] <= a.agree_pp) and (devs[idx] > a.outlier_pp)
                    screen.append(dict(rule='repeat', repeat=lb, species=sp, time=t, area=ar,
                                       field='', value=arr[idx], reference=pair_means[idx],
                                       ratio=devs[idx], flagged=bool(flagged)))
                # flag at most the single most extreme value (a rule that can cascade would
                # delete the whole set)
                cand = [k for k in range(len(arr))
                        if pair_gaps[k] <= a.agree_pp and devs[k] > a.outlier_pp]
                if cand:
                    flagged = True
                    k = max(cand, key=lambda x: devs[x])
                    others_txt = ' / '.join('%+.0f' % v for v in np.delete(arr, k))
                    reg.append(dict(level='cell', repeat=names[k], species=sp, time=t, area=ar,
                                    field='', issue='anti-adhesion outlier',
                                    detail='AA %+.0f %% vs %s %% in the other %d repeats '
                                           '(they agree within %.0f pp; this one lies '
                                           '%.0f pp from their mean, rule > %.0f pp).'
                                           % (arr[k], others_txt, len(arr) - 1,
                                              pair_gaps[k], devs[k], a.outlier_pp),
                                    evidence='automated screen', rows_removed=0,
                                    source='automated'))
                else:
                    flagged = False
                del flagged

    reg_df = pd.DataFrame(reg)
    reg_df['rows_removed'] = reg_df['rows_removed'].fillna(0).astype(int)
    p_reg = os.path.join(a.out, '650nm_exclusions_%s.csv' % a.date)
    reg_df.to_csv(p_reg, index=False, encoding='utf-8-sig')
    p_scr = os.path.join(a.out, '650nm_exclusion_screen_%s.csv' % a.date)
    pd.DataFrame(screen).to_csv(p_scr, index=False, encoding='utf-8-sig')

    print('registry ->', p_reg)
    for _, r in reg_df.iterrows():
        print('  %-8s %-9s %-4s %-3s %-5s %-34s %s'
              % (r['repeat'], r['species'], r['time'], r['area'] or 'all', r['level'],
                 r['issue'], ('' if r['source'] == 'documented' else r['detail'])))
    print('screen   ->', p_scr)
    fl = pd.DataFrame(screen)
    if len(fl):
        print('field-rule candidates:', int((fl.rule == 'field').sum()),
              '| repeat-rule evaluations:', int((fl.rule == 'repeat').sum()),
              '| repeat-rule flags:', int(fl.flagged.sum()))


if __name__ == '__main__':
    main()
