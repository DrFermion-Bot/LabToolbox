# contact_angle — Contact angle → surface free energy (OWRK) / 接触角 → 表面自由能（OWRK）

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

This module converts sessile-drop contact angles of **two probe liquids** into the surface free energy (SFE) of a solid, split into a dispersive (Lifshitz–van der Waals, LW) and a polar (P) component, using the **Owens–Wendt–Rabel–Kaelble (OWRK)** model. It is the quick, standalone OWRK route; the three-liquid van Oss–Chaudhury–Good (vOCG) route (γ^LW / γ^+ / γ^- and XDLVO adhesion energies) lives in [`xdlvo`](xdlvo.md). Contact angles measured on a coating are the first input of the bacterial-adhesion workflow, so this module is normally used to screen coatings before running XDLVO.

### Physics background and formulas

Fowkes' idea that surface energy splits into dispersive and polar terms gives, in the OWRK form,

```
γ_L (1 + cos θ) = 2 · ( √(γ_S^d · γ_L^d) + √(γ_S^p · γ_L^p) )
γ_L = γ_L^d + γ_L^p
```

where θ is the contact angle, `γ_L` the probe-liquid surface tension, and `γ_S` the solid surface free energy. Dividing by `2√γ_L^d` linearises the equation:

```
y_i = γ_Li (1 + cos θ_i) / (2 √γ_Li^d)
x_i = √( γ_Li^p / γ_Li^d )
y_i = a + b · x_i ,      a = √γ_S^d ,   b = √γ_S^p
```

Two liquids give an exactly determined 2-point system; the module solves it algebraically instead of least-squares:

```
b = (y2 − y1) / (x2 − x1)      a = y1 − b · x1
γ_S^LW = a²                    γ_S^P = max(b, 0)²      γ_S^TOT = γ_S^LW + γ_S^P
```

The probe-liquid table is stored in the vOCG convention `(γ^LW, γ^+, γ^-)` (mJ/m²). The OWRK quantities are reconstructed from it as `γ_L = γ_L^LW + 2√(γ_L^+ γ_L^-)` (used in `y`) and `γ_L^p = γ_L^+ + γ_L^-` (used in `x`); see the limitation on asymmetric liquids below.

### Inputs and data formats

| Input | Type | Meaning |
|---|---|---|
| `theta1` | float, required | Contact angle of liquid 1, degrees (through the liquid, sessile drop) |
| `theta2` | float, required | Contact angle of liquid 2, degrees |
| `liquid1` | str, default `water` | Probe liquid 1, must be a key of the probe table |
| `liquid2` | str, default `diiodomethane` | Probe liquid 2 |
| `output_dir` | str, default `output` | Accepted for API uniformity but **unused** (this module writes no files) |

The angle/liquid pairing is positional: `theta1` must belong to `liquid1`.

| Liquid key | γ^LW | γ^+ | γ^- | γ_L used in y (vOCG total) | γ_L^p used in x |
|---|---|---|---|---|---|
| `water` | 21.8 | 25.5 | 25.5 | 72.8 | 51.0 |
| `diiodomethane` | 50.8 | 0.0 | 0.0 | 50.8 | 0.0 |
| `formamide` | 39.0 | 2.28 | 39.6 | 58.0 | 41.88 |
| `glycerol` | 34.0 | 3.92 | 57.4 | 64.0 | 61.32 |
| `ethylene_glycol` | 29.0 | 1.92 | 47.0 | 48.0 | 48.92 |

Entry points: CLI `labtoolbox contact-angle --theta1 .. --theta2 .. [--liquid1 ..] [--liquid2 ..]`; GUI tab **接触角/表面能** (defaults 72.3° / 48.2°); Python `labtoolbox.contact_angle.run(...)`.

### Outputs

`run()` returns a dict (nothing is written to disk):

```
{
  "surface_energy": SurfaceEnergy(gamma_lw, gamma_p, gamma_total),   # mJ/m²
  "theta1_deg":  float,   "liquid1": str,
  "theta2_deg":  float,   "liquid2": str,
  "result":      str      # repr of SurfaceEnergy, e.g. "γ^LW=35.27, γ^P=7.64, γ^TOT=42.91 mJ/m²"
}
```

### End-to-end pipeline

1. Look up both liquids in `PROBE_LIQUIDS` (`_liquid_params`), raise on unknown names.
2. Convert the two angles to radians.
3. Build `y_i`, `x_i` with the formulas above (liquid total from the LW/acid-base components, polar part as `γ^+ + γ^-`).
4. Reject a degenerate pair when `|x2 − x1| < 1e-10` ("病态矩阵 : 两种液体极性差异太小").
5. Solve `a`, `b` from the two points; compute `γ_S^LW = a²`, `γ_S^P = max(b,0)²`.
6. If `a < 0` raise `ValueError` (unphysical negative dispersive component).
7. Return the `SurfaceEnergy` dataclass plus the echo of the inputs.

### Parameters and defaults

| Parameter | Default | Used by | Notes |
|---|---|---|---|
| `theta1` / `theta2` | required | CLI/API | degrees |
| `liquid1` | `water` | CLI/API/GUI | see probe table |
| `liquid2` | `diiodomethane` | CLI/API/GUI | nonpolar reference liquid |
| `output_dir` | `output` | API only | unused, no output files |

### Implementation notes

* Package `labtoolbox/contact_angle/`, single module `contact_angle.py` (99 lines at commit `0e0508e`); dependencies: NumPy only (no SciPy, no matplotlib, no I/O).
* `SurfaceEnergy` is a `@dataclass` with `gamma_lw`, `gamma_p`, `gamma_total` and a human-readable `__repr__`.
* Functions: `_liquid_params(name)`, `owrk_surface_energy(theta1, theta2, liquid1, liquid2)`, `lp_is_nonpolar(lp)`, `contact_angle_from_surface_energy(se, liquid)`, `run(...)`.
* `contact_angle_from_surface_energy` inverts OWRK: `cos θ = 2(√(γ_S^LW γ_L^LW) + √(γ_S^P γ_L^p)) / γ_L^LW − 1`; the denominator is the **LW part** of the liquid, not the liquid total (see limitations).
* Exported through `labtoolbox.contact_angle.__init__`; the unified CLI registers `contact-angle` in `labtoolbox/cli.py`.

### Assumptions, limitations and known quirks

* **Two-liquid, exact solve.** No over-determination, no least-squares, no confidence intervals or error propagation; an error in either angle shifts the result directly.
* **Probe-liquid constants are fixed** at room-temperature literature values; temperature, purity and batch are not modelled.
* **Polar-component bookkeeping is inconsistent for asymmetric liquids.** `y` uses γ_L = γ_L^LW + 2√(γ_L^+γ_L^-) while `x` uses γ_L^p = γ_L^+ + γ_L^-. The two agree only when γ^+ = γ^- (water) or both are zero (diiodomethane). The default water/diiodomethane pair is therefore textbook-consistent, while formamide/glycerol/ethylene-glycol combinations use a non-standard `x` (e.g. formamide: 41.88 instead of 19.0 mJ/m²).
* **Silent clamping.** `γ_S^P = max(b,0)²` turns a negative polar solution into 0 without warning.
* **Dead fallback branch.** When `a < 0` the code computes a placeholder nonpolar value using `cos 45°` and then raises anyway, so the fallback is never usable.
* **Inverse helper is only valid for a nonpolar probe liquid.** Its denominator uses `γ_L^LW` instead of the total `γ_L`; e.g. for `γ_S^LW = 30`, `γ_S^P = 20` mJ/m² the true water angle is 54.6° but the helper returns 0° (cosine clipped at 1). For diiodomethane the inversion is exact.
* **No roughness/hysteresis correction.** Static angles are used as-is; Wenzel/Cassie–Baxter wetting states, contact-angle hysteresis and drop-shape (axisymmetric drop) fitting are not implemented. Use advancing, equilibrium angles for clean flat coatings.
* **No acid/base decomposition.** Separating γ^+ and γ^- needs at least three liquids and the vOCG solver in `xdlvo.py`; OWRK collapses all polar interactions into one term.

### QC and validation

* Guard rails: unknown liquid name, degenerate liquid pair (`|x2−x1| < 1e-10`), negative `√γ_S^LW` → exception.
* No automatic report/figure is produced; the module is validated by consistency checks such as the single-liquid Fowkes relation `γ_S^LW = γ_L (1 + cos θ)² / 4` on the nonpolar liquid, or by comparing to the three-liquid vOCG solution (`xdlvo.surface_energy_from_contact_angles`).
* Verified example (commit `0e0508e`, Python 3.11/NumPy 2.4): `θ1 = 72.3°` on water, `θ2 = 48.2°` on diiodomethane → `γ^LW = 35.27`, `γ^P = 7.64`, `γ^TOT = 42.91 mJ/m²` (matches the README example values).

### References

* Owens DK, Wendt RC. Estimation of the surface free energy of polymers. *J Appl Polym Sci.* 1969;13(8):1741–1747. doi:10.1002/app.1969.070130815.
* Rabel W. Einige Aspekte der Benetzungstheorie und ihre Anwendung auf die Untersuchung und Veränderung der Oberflächeneigenschaften von Polymeren. *Farbe und Lack.* 1971;77:997–1005.
* Kaelble DH. Dispersion-polar surface tension properties of organic solids. *J Adhes.* 1970;2(2):66–81.
* Fowkes FM. Attractive forces at interfaces. *Ind Eng Chem.* 1964;56(12):40–52.
* van Oss CJ, Chaudhury MK, Good RJ. Interfacial Lifshitz–van der Waals and polar interactions in macroscopic systems. *Chem Rev.* 1988;88(6):927–941.
* van Oss CJ. *Interfacial Forces in Aqueous Media.* 2nd ed. CRC Press; 2006. (textbook — source of the vOCG probe-liquid constants)
* Probe-liquid numerical constants as tabulated in the module: water (21.8, 25.5, 25.5), diiodomethane (50.8, 0, 0), formamide (39.0, 2.28, 39.6), glycerol (34.0, 3.92, 57.4), ethylene glycol (29.0, 1.92, 47.0) mJ/m².

## 中文

### 目的与科学背景

本模块把**两种探测液体**的座滴接触角换算为固体表面自由能（surface free energy, SFE），并按 **OWRK（Owens–Wendt–Rabel–Kaelble）** 模型拆成色散分量（Lifshitz–van der Waals，LW）与极性分量（P）。它是快捷的独立 OWRK 途径；三液 van Oss–Chaudhury–Good（vOCG）途径（γ^LW / γ^+ / γ^- 以及 XDLVO 黏附能）在 [`xdlvo`](xdlvo.md) 模块中实现。涂层接触角是细菌黏附流程的第一步输入，因此本模块通常用于在跑 XDLVO 之前筛查涂层表面化学。

### 物理背景与公式

Fowkes 关于表面能可拆为色散项与极性项的假设，在 OWRK 形式下给出

```
γ_L (1 + cos θ) = 2 · ( √(γ_S^d · γ_L^d) + √(γ_S^p · γ_L^p) )
γ_L = γ_L^d + γ_L^p
```

其中 θ 为接触角，`γ_L` 为探测液体表面张力，`γ_S` 为固体表面自由能。两边除以 `2√γ_L^d` 即可线性化：

```
y_i = γ_Li (1 + cos θ_i) / (2 √γ_Li^d)
x_i = √( γ_Li^p / γ_Li^d )
y_i = a + b · x_i ,      a = √γ_S^d ,   b = √γ_S^p
```

两种液体给出恰定（2 点）方程组，模块直接代数求解而不用最小二乘：

```
b = (y2 − y1) / (x2 − x1)      a = y1 − b · x1
γ_S^LW = a²                    γ_S^P = max(b, 0)²      γ_S^TOT = γ_S^LW + γ_S^P
```

探测液体参数表以 vOCG 约定存储 `(γ^LW, γ^+, γ^-)`（mJ/m²），OWRK 用的量由它重建：`γ_L = γ_L^LW + 2√(γ_L^+ γ_L^-)`（用于 `y`），`γ_L^p = γ_L^+ + γ_L^-`（用于 `x`）。不对称液体的隐患见下文“局限”。

### 输入与数据格式

| 输入 | 类型 | 含义 |
|---|---|---|
| `theta1` | float，必填 | 液体 1 的接触角（度，座滴法、穿过液体测量） |
| `theta2` | float，必填 | 液体 2 的接触角（度） |
| `liquid1` | str，默认 `water` | 液体 1，须为参数表键名 |
| `liquid2` | str，默认 `diiodomethane` | 液体 2 |
| `output_dir` | str，默认 `output` | 仅为接口统一而保留，**实际未使用**（本模块不写文件） |

角度与液体按位置对应：`theta1` 必须对应 `liquid1`。

| 液体键名 | γ^LW | γ^+ | γ^- | y 中使用的 γ_L（vOCG 总值） | x 中使用的 γ_L^p |
|---|---|---|---|---|---|
| `water` | 21.8 | 25.5 | 25.5 | 72.8 | 51.0 |
| `diiodomethane` | 50.8 | 0.0 | 0.0 | 50.8 | 0.0 |
| `formamide` | 39.0 | 2.28 | 39.6 | 58.0 | 41.88 |
| `glycerol` | 34.0 | 3.92 | 57.4 | 64.0 | 61.32 |
| `ethylene_glycol` | 29.0 | 1.92 | 47.0 | 48.0 | 48.92 |

入口：命令行 `labtoolbox contact-angle --theta1 .. --theta2 .. [--liquid1 ..] [--liquid2 ..]`；GUI 标签页 **接触角/表面能**（默认 72.3° / 48.2°）；Python `labtoolbox.contact_angle.run(...)`。

### 输出

`run()` 返回 dict（不写盘）：

```
{
  "surface_energy": SurfaceEnergy(gamma_lw, gamma_p, gamma_total),   # mJ/m²
  "theta1_deg":  float,   "liquid1": str,
  "theta2_deg":  float,   "liquid2": str,
  "result":      str      # SurfaceEnergy 的 repr，例: "γ^LW=35.27, γ^P=7.64, γ^TOT=42.91 mJ/m²"
}
```

### 端到端流程

1. 用 `_liquid_params` 在 `PROBE_LIQUIDS` 中查两种液体，未知名称报错。
2. 两个角度换算为弧度。
3. 按上式构造 `y_i`、`x_i`（液体总值取 LW + 酸碱分量；极性项取 `γ^+ + γ^-`）。
4. 当 `|x2 − x1| < 1e-10` 时判定病态（"病态矩阵 : 两种液体极性差异太小"）并报错。
5. 由两点解 `a`、`b`，得 `γ_S^LW = a²`、`γ_S^P = max(b,0)²`。
6. 若 `a < 0` 抛出 `ValueError`（色散分量开方为负，无物理意义）。
7. 返回 `SurfaceEnergy` 数据类，并回显输入参数。

### 参数与默认值

| 参数 | 默认值 | 使用位置 | 说明 |
|---|---|---|---|
| `theta1` / `theta2` | 必填 | CLI/API | 单位：度 |
| `liquid1` | `water` | CLI/API/GUI | 见液体参数表 |
| `liquid2` | `diiodomethane` | CLI/API/GUI | 非极性参考液体 |
| `output_dir` | `output` | 仅 API | 未使用，无输出文件 |

### 实现说明

* 包 `labtoolbox/contact_angle/`，单文件 `contact_angle.py`（commit `0e0508e` 时 99 行）；依赖仅 NumPy（不用 SciPy、matplotlib，无文件 I/O）。
* `SurfaceEnergy` 为 `@dataclass`，字段 `gamma_lw`、`gamma_p`、`gamma_total`，带人类可读 `__repr__`。
* 函数：`_liquid_params(name)`、`owrk_surface_energy(theta1, theta2, liquid1, liquid2)`、`lp_is_nonpolar(lp)`、`contact_angle_from_surface_energy(se, liquid)`、`run(...)`。
* `contact_angle_from_surface_energy` 为 OWRK 反解：`cos θ = 2(√(γ_S^LW γ_L^LW) + √(γ_S^P γ_L^p)) / γ_L^LW − 1`；分母用的是液体的 **LW 分量**而非液体总值（见局限）。
* 通过 `labtoolbox.contact_angle.__init__` 导出；统一 CLI 在 `labtoolbox/cli.py` 注册 `contact-angle` 子命令。

### 假设、局限与已知怪癖

* **两液恰定求解。** 没有超定冗余、没有最小二乘、没有置信区间或误差传播；任一角度误差都直接传递。
* **液体常数固定**为室温文献值；温度、纯度、批次差异均未建模。
* **不对称液体的极性项记账不一致。** `y` 用 γ_L = γ_L^LW + 2√(γ_L^+γ_L^-)，`x` 用 γ_L^p = γ_L^+ + γ_L^-；两者只有在 γ^+ = γ^-（水）或均为 0（二碘甲烷）时相等。默认的水/二碘甲烷组合因此与教科书 OWRK 一致，而甲酰胺/甘油/乙二醇组合的 `x` 用了非标准值（如甲酰胺 41.88 而非 19.0 mJ/m²）。
* **静默截断。** `γ_S^P = max(b,0)²` 会把负的极性解变成 0 且不报警。
* **死代码回退分支。** `a < 0` 时先用 `cos 45°` 算了一个占位非极性值，随后仍然抛异常，因此该回退永远不可用。
* **反解函数只对非极性探测液体有效。** 其分母用 `γ_L^LW` 而非液体总值 `γ_L`；例如 `γ_S^LW = 30`、`γ_S^P = 20` mJ/m² 的表面真实水接触角为 54.6°，该函数返回 0°（余弦被 clip 到 1）。对二碘甲烷反解是精确的。
* **无粗糙度/滞后修正。** 直接使用静态接触角；未实现 Wenzel/Cassie–Baxter 浸润态、接触角滞后或液滴轮廓（轴对称滴形）拟合。洁净平面涂层请使用前进/平衡角。
* **无酸碱分解。** 拆分 γ^+ 与 γ^- 至少需要三种液体和 `xdlvo.py` 的 vOCG 求解器；OWRK 把所有极性作用并成一项。

### 质控与验证

* 防护：未知液体名、病态液体组合（`|x2−x1| < 1e-10`）、`√γ_S^LW` 为负 → 抛异常。
* 不自动生成报告/图；一致性校验可用单液 Fowkes 关系 `γ_S^LW = γ_L (1 + cos θ)² / 4`（非极性液），或与三液 vOCG 解（`xdlvo.surface_energy_from_contact_angles`）对比。
* 已核对示例（commit `0e0508e`，Python 3.11/NumPy 2.4）：水 θ1 = 72.3°、二碘甲烷 θ2 = 48.2° → `γ^LW = 35.27`、`γ^P = 7.64`、`γ^TOT = 42.91 mJ/m²`（与 README 示例值一致）。

### 参考文献

* Owens DK, Wendt RC. Estimation of the surface free energy of polymers. *J Appl Polym Sci.* 1969;13(8):1741–1747. doi:10.1002/app.1969.070130815.
* Rabel W. Einige Aspekte der Benetzungstheorie und ihre Anwendung auf die Untersuchung und Veränderung der Oberflächeneigenschaften von Polymeren. *Farbe und Lack.* 1971;77:997–1005.
* Kaelble DH. Dispersion-polar surface tension properties of organic solids. *J Adhes.* 1970;2(2):66–81.
* Fowkes FM. Attractive forces at interfaces. *Ind Eng Chem.* 1964;56(12):40–52.
* van Oss CJ, Chaudhury MK, Good RJ. Interfacial Lifshitz–van der Waals and polar interactions in macroscopic systems. *Chem Rev.* 1988;88(6):927–941.
* van Oss CJ. *Interfacial Forces in Aqueous Media.* 2nd ed. CRC Press; 2006.（教科书，vOCG 探测液体常数来源）
* 模块内使用的探测液体常数：水 (21.8, 25.5, 25.5)、二碘甲烷 (50.8, 0, 0)、甲酰胺 (39.0, 2.28, 39.6)、甘油 (34.0, 3.92, 57.4)、乙二醇 (29.0, 1.92, 47.0) mJ/m²。
