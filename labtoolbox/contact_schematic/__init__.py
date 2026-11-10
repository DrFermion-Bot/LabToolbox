# -*- coding: utf-8 -*-
"""接触几何示意图 (AFM 处理流程末端).

实测几何 (周期/纹深/尖峰间距/凸起高度) → 细菌黏附 3D 示意图 + 接触几何图.
公开接口:
  run(...)        一步跑完: 测量 → CSV → 渲染 fig1/2/3 → README (CLI 与 GUI 共用)
  measure_geometry / summarise / write_csv   底层测量 (geometry.py)
  render_all / render_contact_geometry       底层渲染 (render.py)
"""
import os

from .geometry import (CLASS_LIPSS, CLASS_PILLAR, classify, measure_file,  # noqa: F401
                       measure_geometry, summarise, write_csv)
from .render import (ECOLI_D, ECOLI_L, SAUREUS_D, render_all,  # noqa: F401
                     render_contact_geometry, _figure as render_surface_figure)

__all__ = ["CLASS_LIPSS", "CLASS_PILLAR", "classify", "measure_file", "measure_geometry",
           "summarise", "write_csv", "render_all", "render_contact_geometry",
           "render_surface_figure", "ECOLI_L", "ECOLI_D", "SAUREUS_D",
           "run", "write_readme"]

README_TMPL = """# 细菌-织构接触示意图 ({label}) — 自动生成

由 `labtoolbox.contact_schematic` 在 AFM 处理流程末端生成 (ZSR 通道, 平面扣除 + 5σ 去尖峰).

## 实测几何 (nm)

| 参数 | 数值 (mean ± sd, n) |
|---|---|
| LIPSS 周期 | {p_mean:.1f} ± {p_sd:.1f} (n={p_n}) |
| LIPSS 纹深 (P98-P2) | {d_mean:.1f} ± {d_sd:.1f} (n={d_n}) |
| 纳米柱尖峰间距 (NN 中位) | {s_mean:.1f} ± {s_sd:.1f} (n={s_n}) |
| 纳米柱凸起高度 (P90-中位) | {h_mean:.1f} ± {h_sd:.1f} (n={h_n}) |

逐文件数值见 `geometry_measurements.csv`.

## 文件

- `fig1_LIPSS_adhesion.png/.pdf` — (a) 形貌+剖面尺寸; (b) 大肠杆菌平行 0°; (c) 45°; (d) 垂直 90°; (e) 金黄色葡萄球菌
- `fig2_nanopillar_adhesion.png/.pdf` — 同构
- `fig3_contact_geometry.png/.pdf` — 球形菌 SEI 几何 (R, r, θ, h, D(r)=h+R−√(R²−r²)); 杆平行 (与沟两侧斜坡相切); 杆跨越 (只碰脊顶)

## 假设 (必须与论文图注一致)

1. 细菌按**刚性**杆/球建模, 接触 = 几何搁置于凸起处, **不是**力学或 XDLVO 计算;
2. LIPSS 沟槽按正弦近似, 纳米柱按准周期阵列近似 (真实排布准随机);
3. D(r) 采用等效球-平面关系 (SEI 惯例), 对正弦脊顶为近似;
4. 细胞尺寸取**文献标称值** (E. coli {ec_l:.1f}×{ec_d:.1f} µm, S. aureus {sa:.1f} µm), 非本组实测;
5. 全部**严格同比例** (未夸大 z 轴).

重绘: `python -m labtoolbox.contact_schematic --input <数据目录> --out <输出目录>`
"""


def write_readme(g, out_dir, label="515 nm", cell=(ECOLI_L, ECOLI_D), coccus=SAUREUS_D):
    """写自动生成的说明 README.md (含实测值与假设). 返回路径."""
    rd = README_TMPL.format(
        label=label,
        p_mean=g["lipss"]["period_nm"]["mean"], p_sd=g["lipss"]["period_nm"]["sd"],
        p_n=g["lipss"]["period_nm"]["n"],
        d_mean=g["lipss"]["depth_nm"]["mean"], d_sd=g["lipss"]["depth_nm"]["sd"],
        d_n=g["lipss"]["depth_nm"]["n"],
        s_mean=g["nanopillar"]["spacing_nm"]["mean"],
        s_sd=g["nanopillar"]["spacing_nm"]["sd"],
        s_n=g["nanopillar"]["spacing_nm"]["n"],
        h_mean=g["nanopillar"]["height_nm"]["mean"],
        h_sd=g["nanopillar"]["height_nm"]["sd"],
        h_n=g["nanopillar"]["height_nm"]["n"],
        ec_l=cell[0], ec_d=cell[1], sa=coccus)
    path = os.path.join(out_dir, "README.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(rd)
    return path


def run(folder, output_dir="output", label="515 nm", channel="zsr", lam_nm=515.0,
        dpi=190, cell=(ECOLI_L, ECOLI_D), coccus=SAUREUS_D, render=True, verbose=False):
    """AFM 末端一步: 测量几何 → CSV → (可选) 渲染 fig1/2/3 + README.

    参数 (与 python -m labtoolbox.contact_schematic 一致):
      folder     AFM 原始数据 (.ibw 文件或目录, 递归)
      output_dir 输出目录
      label      样品标签 (进标题), 如 "515 nm"
      channel    .ibw 通道 (默认 zsr)
      lam_nm     激光波长 nm (FFT 物理窗口用, 默认 515)
      dpi        出图 dpi (默认 190)
      cell       E. coli (长, 直径) µm — 文献标称值, 可覆盖
      coccus     S. aureus 直径 µm — 文献标称值, 可覆盖
      render     False = 只测量出表, 不画图 (同 CLI --no-render)
      verbose    打印 CLI 同款进度 (CLI 用; GUI 静默)

    返回 dict: {"csv", "summary", "figures", "readme", "n_files"}.
    方法学未改动: 仍是 geometry.py 的 ZSR 口径测量 + render.py 的严格同比例示意图.
    """
    os.makedirs(output_dir, exist_ok=True)
    if verbose:
        print(f"[1/3] 测量: {folder}")
    recs = measure_geometry(folder, channel=channel, lam_nm=lam_nm)
    csv_path = write_csv(recs, os.path.join(output_dir, "geometry_measurements.csv"))
    g = summarise(recs, lam_nm=lam_nm)
    if verbose:
        print(f"      文件 {g['n_files']} 个 (LIPSS {g['n_lipss']} / 纳米柱 {g['n_pillar']}) → {csv_path}")
    made = []
    readme = None
    if render:
        if verbose:
            print("[2/3] 渲染示意图")
        made = render_all(g, output_dir, label=label, dpi=dpi, cell=cell, coccus=coccus)
        if verbose:
            for path in made:
                print("      ", os.path.basename(path))
            print("[3/3] 写 README")
        readme = write_readme(g, output_dir, label=label, cell=cell, coccus=coccus)
    if verbose and render:
        print("完成 →", output_dir)
    return {"csv": csv_path, "summary": g, "figures": made, "readme": readme,
            "n_files": g["n_files"]}
