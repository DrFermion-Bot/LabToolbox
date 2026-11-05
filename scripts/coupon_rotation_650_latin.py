# -*- coding: utf-8 -*-
"""coupon_rotation_650_latin.py — with FOUR repeats the 650 nm LIVE/DEAD design is a
complete 4x4 Latin square (rows = repeats, columns = timepoints, letters = coupons):

    repeat 1 : 3h<-1  5h<-2  7h<-3  24h<-4
    repeat 2 : 3h<-2  5h<-3  7h<-4  24h<-1
    repeat 3 : 3h<-3  5h<-4  7h<-1  24h<-2
    repeat 4 : 3h<-4  5h<-1  7h<-2  24h<-3

so coupon, timepoint and repeat are mutually orthogonal and a coupon effect on
anti-adhesion IS separately estimable (the two-repeat version of this analysis
could not do that; see coupon_rotation_650.py).

What it does
  * builds one anti-adhesion value per (repeat, species, time, area), each against
    its OWN repeat control, then removes every point listed in the exclusion
    registry (so no excluded coupon is used);
  * fits AA ~ C(repeat) + C(time) + C(coupon) (the Latin-square model) per
    species x area, plus the reduced AA ~ C(coupon) model, and reports the
    partial F-test for the coupon term with its effect size (eta^2);
  * prints the per-coupon means with SD and n, and the per-coupon AA profile
    across the four timepoints.

Usage
  python coupon_rotation_650_latin.py --out <dir> --rep "repeat 1=<dir>" --rep ... \
      --exclusions <registry.csv>
"""
from __future__ import annotations

import argparse
import itertools
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols

DS = ('F:/OneDrive - University of Dundee/Svetlana Zolotovskaya (Staff) 的文件 - '
      'Ruinong Pan_Antibacterial Surfaces/Live_Dead Bacteria Test/650nm-20261014')
TIMES = ['3h', '5h', '7h', '24h']
SP_DIR = {'E. coli': 'E.coli', 'S. aureus': 'S.aureus'}
AREAS = [('1', 'LIPSS'), ('2', 'Nanopillar')]
ROTATION = {
    'repeat 1': {'3h': 1, '5h': 2, '7h': 3, '24h': 4},
    'repeat 2': {'3h': 2, '5h': 3, '7h': 4, '24h': 1},
    'repeat 3': {'3h': 3, '5h': 4, '7h': 1, '24h': 2},
    'repeat 4': {'3h': 4, '5h': 1, '7h': 2, '24h': 3},
}


def load(dirpath, sp):
    p = os.path.join(dirpath, SP_DIR[sp], 'livedead_raw_counts.csv')
    df = pd.read_csv(p, encoding='utf-8-sig')
    df = df[df.area.astype(str) != '3'].copy()
    df['area'] = df['area'].astype(str)
    df['time'] = df['time'].astype(str)
    df['live'] = pd.to_numeric(df['live'], errors='coerce')
    df['dead'] = pd.to_numeric(df['dead'], errors='coerce')
    df['total'] = df['live'].fillna(0) + df['dead'].fillna(0)
    return df


def load_exclusions(path):
    if not path or not os.path.isfile(path):
        return pd.DataFrame(columns=['repeat', 'species', 'time', 'area'])
    ex = pd.read_csv(path, encoding='utf-8-sig')
    ex['area'] = ex['area'].fillna('').astype(str)
    out = []
    for _, r in ex.iterrows():
        a = r['area'].strip()
        try:
            a = str(int(float(a))) if a not in ('', 'c') else a
        except ValueError:
            pass
        out.append(dict(repeat=str(r['repeat']).strip(), species=str(r['species']).strip(),
                        time=str(r['time']).strip(), area=a))
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--rep', action='append', default=[])
    ap.add_argument('--exclusions', default='')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    labels = [x.split('=', 1)[0].strip() for x in a.rep]
    dirs = {x.split('=', 1)[0].strip(): x.split('=', 1)[1].strip() for x in a.rep}
    labels = [lb for lb in ROTATION if lb in labels]
    EX = load_exclusions(a.exclusions)

    def excluded(lb, sp, t, ar):
        if not len(EX):
            return False
        m = ((EX['repeat'] == lb) & (EX['species'] == sp) & (EX['time'] == t) &
             ((EX['area'] == ar) | (EX['area'] == '')))
        return bool(m.any()) or bool(((EX['repeat'] == lb) & (EX['species'] == sp) &
                                     (EX['time'] == t) & (EX['area'] == '')).any())

    rows = []
    for lb in labels:
        for sp in ('E. coli', 'S. aureus'):
            df = load(dirs[lb], sp)
            for t in TIMES:
                c = df[(df.time == t) & (df.area == 'c')]['total'].astype(float)
                if len(c) < 2:
                    continue
                for ar, nm in AREAS:
                    if excluded(lb, sp, t, ar):
                        continue
                    s = df[(df.time == t) & (df.area == ar)]['total'].astype(float)
                    if len(s) < 2:
                        continue
                    aa = (c.mean() - s.mean()) / c.mean() * 100.0
                    rows.append(dict(repeat=lb, species=sp, time=t, area=ar, area_name=nm,
                                     coupon=ROTATION[lb][t], aa=aa,
                                     ctrl=c.mean(), treated=s.mean()))
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(a.out, 'coupon_latin_observations.csv'), index=False,
             encoding='utf-8-sig')

    lines, summ = [], []
    for sp in ('E. coli', 'S. aureus'):
        for ar, nm in AREAS:
            s = d[(d.species == sp) & (d.area == ar)].copy()
            n = len(s)
            head = '=== %s / %s: %d observations ===' % (sp, nm, n)
            print(head); lines.append(head)
            if n < 8:
                msg = '   too few observations for the Latin-square model - skipped'
                print(msg); lines.append(msg); continue
            s['repeat'] = pd.Categorical(s['repeat'], categories=labels)
            s['time'] = pd.Categorical(s['time'], categories=TIMES)
            s['coupon'] = pd.Categorical(s['coupon'], categories=[1, 2, 3, 4])
            full = ols('aa ~ C(repeat) + C(time) + C(coupon)', data=s).fit()
            red = ols('aa ~ C(repeat) + C(time)', data=s).fit()
            ft = full.compare_f_test(red)
            ss_full = (full.resid ** 2).sum()
            ss_red = (red.resid ** 2).sum()
            eta2 = (ss_red - ss_full) / ((s.aa - s.aa.mean()) ** 2).sum() * 100.0
            txt = ('   coupon term: F = %.2f, p = %.3f, partial eta2 = %.0f %% of the total '
                   'variance (df diff %d over %d residual df)'
                   % (ft[0], ft[1], eta2, int(ft[2]), int(full.df_resid)))
            print(txt); lines.append(txt)
            an = sm.stats.anova_lm(full, typ=2)
            print(an.to_string()); lines.append(an.to_string())
            for cp, g in s.groupby('coupon'):
                m = '   coupon %s: mean AA %+.0f %%, SD %.0f, n = %d  (%s)' % (
                    cp, g.aa.mean(), g.aa.std(ddof=1) if len(g) > 1 else float('nan'), len(g),
                    ', '.join('%s %+.0f' % (r.time, r.aa) for _, r in g.iterrows()))
                print(m); lines.append(m)
            summ.append(dict(species=sp, area=nm, n=n, F=ft[0], p=ft[1], eta2_pct=eta2))

    sm_df = pd.DataFrame(summ)
    p_out = os.path.join(a.out, 'coupon_latin_tests.csv')
    sm_df.to_csv(p_out, index=False, encoding='utf-8-sig')
    print('\ntests ->', p_out)
    # per-coupon summary table
    piv = (d.groupby(['species', 'area_name', 'coupon'])['aa']
           .agg(['mean', 'std', 'count']).reset_index())
    piv.to_csv(os.path.join(a.out, 'coupon_latin_percoupon.csv'), index=False,
               encoding='utf-8-sig')
    print(piv.to_string(index=False))
    with open(os.path.join(a.out, 'coupon_latin_report.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))


if __name__ == '__main__':
    main()
