# -*- coding: utf-8 -*-
"""Run build_sem_group_report.build() for every sample folder under SEM-EDX graphics."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sem_group_report import build

ROOT = (r"F:\OneDrive - University of Dundee\Svetlana Zolotovskaya (Staff) 的文件 - "
        r"Ruinong Pan_Antibacterial Surfaces\SEM-EDX graphics\02_SEM_raw_images")

JOBS = [
    (os.path.join(ROOT, "515nm", "LIPSS_regions"), "515 nm LIPSS coupons (position 1)", dict(mixed=False)),
    (os.path.join(ROOT, "515nm", "nanopillar_regions"), "515 nm nanopillar coupons (position 2)", dict(mixed=False)),
    (os.path.join(ROOT, "515-8_and_polished_surface"),
     "515-8 reference set: LIPSS / nanopillar / polished at 3k and 12k", dict(mixed=True)),
]
for s in ["2N", "4N", "9N", "10N", "13N", "14N", "15N", "17N", "18N"]:
    JOBS.append((os.path.join(ROOT, "650nm", "Nanopillars", s),
                 f"650 nm nanopillar coupon {s}", dict(mixed=False, coupon=s)))

only = sys.argv[1:]          # optional: run only these group names
if only:
    JOBS = [j for j in JOBS if os.path.basename(j[0]) in only]

t0 = time.time()
ok, fail = [], []
for path, title, kw in JOBS:
    name = os.path.basename(path)
    if not os.path.isdir(path):
        print(f"!! missing: {path}"); fail.append(name); continue
    print(f"\n=== {name} — {title}")
    try:
        r = build(path, title=title, tile_um=2.0, **(kw or {}))
        ok.append((name, r["n_fields"], r["n_pairs"], bool(r["pdf"])))
        print(f"    {r['n_fields']} fields, {r['n_pairs']} pairs, pdf={'yes' if r['pdf'] else 'NO'}")
    except Exception as exc:
        import traceback; traceback.print_exc()
        fail.append(name)

print("\n================ SUMMARY ================")
for n, f, p, pdf in ok:
    print(f"  OK   {n:28s} fields={f:3d} pairs={p:3d} pdf={pdf}")
for n in fail:
    print(f"  FAIL {n}")
print(f"elapsed {time.time()-t0:.0f} s")
