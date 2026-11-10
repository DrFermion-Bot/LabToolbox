# -*- coding: utf-8 -*-
"""命令行: python -m labtoolbox.contact_schematic --input <AFM 数据目录> --out <输出目录>

AFM 处理流程的末端步骤: 量取周期/纹深/尖峰间距/凸起高度 → 出
  fig1_LIPSS_adhesion.png/pdf      细菌在 LIPSS 上的 3D 黏附示意 (含取向/接触点)
  fig2_nanopillar_adhesion.png/pdf 同上, 纳米柱表面
  fig3_contact_geometry.png/pdf    接触几何 (球 SEI / 杆平行 / 杆跨越)
  geometry_measurements.csv        逐文件实测值 (可溯源)
  README.md                        自动生成的说明 (含实测值与假设)

真正的实现与 python -m labtoolbox.cli schematic 共用 contact_schematic.run()。
"""
import argparse
import sys

from . import run as schematic_run
from .render import ECOLI_D, ECOLI_L, SAUREUS_D


def main(argv=None):
    ap = argparse.ArgumentParser(prog="labtoolbox.contact_schematic",
                                 description="AFM 末端步骤: 细菌-织构接触示意图")
    ap.add_argument("--input", required=True, help="AFM 原始数据 (.ibw 文件或目录, 递归)")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--label", default="515 nm", help="样品标签 (进标题), 如 '515 nm'")
    ap.add_argument("--channel", default="zsr", help=".ibw 通道 (默认 zsr)")
    ap.add_argument("--lambda", dest="lam", type=float, default=515.0, help="激光波长 nm (FFT 窗口用)")
    ap.add_argument("--dpi", type=int, default=190)
    ap.add_argument("--cell", default=f"{ECOLI_L}x{ECOLI_D}", help="E. coli 长x直径 µm")
    ap.add_argument("--coccus", type=float, default=SAUREUS_D, help="S. aureus 直径 µm")
    ap.add_argument("--no-render", action="store_true", help="只测量出表, 不画图")
    a = ap.parse_args(argv)

    try:
        L, D = (float(v) for v in a.cell.lower().replace(" ", "").split("x"))
    except Exception:
        L, D = ECOLI_L, ECOLI_D

    schematic_run(a.input, output_dir=a.out, label=a.label, channel=a.channel,
                  lam_nm=a.lam, dpi=a.dpi, cell=(L, D), coccus=a.coccus,
                  render=not a.no_render, verbose=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
