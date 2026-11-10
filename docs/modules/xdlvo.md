# xdlvo — XDLVO bacterial-adhesion prediction / XDLVO 细菌黏附预测

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

This module implements **extended DLVO (XDLVO) theory** for bacterial adhesion: measured contact angles are converted to solid/bacterium surface free energy (SFE), the free energy of adhesion at contact `ΔG_ADH` is computed from Lifshitz–van der Waals (LW), acid–base (AB) and (optionally) electrostatic (EL) contributions, and the sphere–plane interaction-energy curve `U(h)` is integrated to give the energy barrier and the primary/secondary minima. It is the theory side of the LabToolbox adhesion story: coatings (F-DLC, laser-textured stainless steel) are ranked by predicted adhesion against *E. coli* / *S. aureus*.

The sub-module `sei.py` extends the same physics to **rough topography** by Surface Element Integration (SEI): the sphere–surface interaction is integrated element-by-element over a measured AFM height field, so a flat-surface `ΔG(h)` law can be used to compare LIPSS ridges and nanopillar arrays.

### Inputs and data formats

`run(contact_angles, bacteria=None, radius_nm=500, I_M=0.01, zeta_m=None, zeta_f=None, T_K=298.15, output_dir="output")`:

| Input | Type | Default | Meaning |
|---|---|---|---|
| `contact_angles` | tuple `(θ_diiodo, θ_water, θ_form)` **or** dict with keys `theta_diiodo`, `theta_water`, `theta_form` | required | Sessile-drop contact angles, degrees, on the material |
| `bacteria` | `SurfaceEnergy` | embedded *E. coli* values | Bacterial SFE (γ^LW, γ^+, γ^-, γ^AB, γ^TOT) |
| `radius_nm` | float | `500` | Equivalent spherical cell radius for the sphere–plane model (nm) |
| `I_M` | float | `0.01` | Ionic strength, mol/L (for the Debye length and EL term) |
| `zeta_m`, `zeta_f` | float or None | `None` | Material / bacterium zeta potentials in **mV**. EL terms are only computed when both are given |
| `T_K` | float | `298.15` | Absolute temperature (K) |
| `output_dir` | str | `output` | Output directory for the figure |

The CLI passes contact angles as JSON: `labtoolbox xdlvo --angles '{"theta_diiodo":48.2,"theta_water":72.3,"theta_form":61.5}' --radius 500 --ionic 0.01 [--zeta-m ..] [--zeta-f ..]`. The GUI tab **🧫 XDLVO** exposes the three angles, radius and ionic strength (no zeta fields).

### Outputs

`run()` returns a dict and writes one figure `output/xdlvo_energy.png`:

```
{
  "surface_energy": SurfaceEnergy,          # material SFE, mJ/m²
  "delta_g": {"LW": float, "AB": float, "ADH": float,         # mJ/m²
              "EL": float, "TOT": float},                     # only if zeta given
  "profile": {"barrier": float|None, "barrier_position": float|None,
              "minima": [(h_nm, U_kT, "primary"|"secondary"), ...]},
  "energy": {"h": ndarray, "LW": ndarray, "AB": ndarray,
             "EL": ndarray, "TOT": ndarray},                  # U in kT, h in nm
  "figure": path
}
```

The figure plots `U_LW` (dashed blue), `U_AB` (dashed orange), `U_EL` (dashed green, only when non-zero) and `U_TOT` (solid red) against separation `h` in nm with a zero line; the y-axis is `Interaction energy (kT)`.

### End-to-end pipeline

1. Parse the three contact angles (tuple or dict).
2. **SFE from three liquids** — γ^LW from diiodomethane; γ^+, γ^- from the water/formamide pair solved as a 2×2 linear system; γ^AB = 2√(γ^+γ^-), γ^TOT = γ^LW + γ^AB.
3. If `bacteria is None`, use the embedded *E. coli* SFE `(γ^LW, γ^+, γ^-) = (37.8, 0.6, 46.5) mJ/m²`; otherwise use the supplied object.
4. **ΔG at contact** — LW and AB terms from the SFE components of material (`m`), bacterium (`f`) and water (`w`); if both zeta potentials are given, add the planar HHF electrostatic term `ΔG_EL(h0)`; `ΔG_ADH = ΔG_LW + ΔG_AB`, `ΔG_TOT = ΔG_ADH + ΔG_EL`.
5. **Interaction-energy curve** `U(h)` for a sphere of radius `R` above a flat plate (Derjaguin approximation for LW/AB, HHF for EL), on `h = 0.15 … 25 nm` in 0.05 nm steps; energies in units of `kT`.
6. **Profile analysis** — locate the highest local maximum (energy barrier) and the local minima (attached state(s)).
7. Plot the components and save the figure; return everything.

### Algorithms and formulas

#### Surface free energy from three contact angles

Diiodomethane is apolar (`γ^+ = γ^- = 0`):

```
γ_S^LW = ( γ_L^LW · (1 + cos θ_diiodo) / (2 √γ_L^LW) )² = γ_L^LW (1 + cos θ_diiodo)² / 4
```

For the polar liquids, with `γ_L = γ_L^LW + 2√(γ_L^+ γ_L^-)`:

```
C_i = γ_Li (1 + cos θ_i)/2 − √( γ_S^LW · γ_Li^LW )
C_i = √(γ_S^+)·√(γ_Li^-) + √(γ_S^-)·√(γ_Li^+)          (i = water, formamide)
```

which is solved as the 2×2 system below; the module assembles `a11, a12 = √γ_w^-, √γ_w^+` and `a21, a22 = √γ_f^-, √γ_f^+` and solves for `[√γ_S^+; √γ_S^-]`:

```
[ a11 a12 ] [ √γ_S^+ ]   [ C1 ]
[ a21 a22 ] [ √γ_S^- ] = [ C2 ]
```

then `γ_S^+ = u²`, `γ_S^- = v²`, `γ_S^AB = 2√(γ_S^+ γ_S^-)`, `γ_S^TOT = γ_S^LW + γ_S^AB`.
**Historical defect, fixed in the integration branch (commit `46bdd8f`):** at base commit `0e0508e` the formamide row was assembled as `a21 = √(γ_f^+)`, `a22 = √(γ_f^-)` instead of the vOCG-required `a21 = √(γ_f^-)`, `a22 = √(γ_f^+)`. Because the water row is symmetric (`γ_w^+ = γ_w^- = 25.5`), the solver then returned `γ_S^+` and `γ_S^-` **exchanged** — e.g. a surface with `(γ^LW, γ^+, γ^-) = (40, 1, 20)` mJ/m² came back as `(40, 20, 1)`.

The integration branch fixes the row order and adds `tests/test_xdlvo_surface_energy.py` (run with `python -m unittest discover -s tests`): it round-trips three known surfaces (`(40, 1, 20)`, `(35, 0.1, 15)`, `(30, 5, 40)` mJ/m²) through forward and inverse vOCG to 1e-6 and pins the README example. With the fix, the README angles `48.2/72.3/61.5°` give `γ^LW = 35.2721`, `γ^+ = 0.00099`, `γ^- = 15.5236`, `γ^AB = 0.2479`, `γ^TOT = 35.5200 mJ/m²` — a physically sensible result (`γ^+` ≈ 0, so the acid–base term is small). `γ^LW` was never affected. The solver still squares negative square roots silently, so an unphysical contact-angle set can appear as a small positive component instead of raising.

#### Free energy of adhesion at contact distance `h0`

```
ΔG_LW = −2 ( √γ_m^LW − √γ_w^LW ) ( √γ_f^LW − √γ_w^LW )
ΔG_AB = 2√γ_w^+ ( √γ_f^- + √γ_m^- − √γ_w^- )
      + 2√γ_w^- ( √γ_f^+ + √γ_m^+ − √γ_w^+ )
      − 2√(γ_f^- γ_m^+) − 2√(γ_f^+ γ_m^-)
ΔG_ADH = ΔG_LW + ΔG_AB                       [mJ/m²]
```

With zeta potentials (mV) the contact electrostatic term is the planar HHF expression

```
ΔG_EL(h0) = (κ ε0 εr / 2) · [ (ζ_m² + ζ_f²)(1 − coth(κ h0)) + 2 ζ_m ζ_f csch(κ h0) ]
```

where `κ` is in 1/nm and `ζ` in mV; the module's factor `1e6` converts the expression to mJ/m² (verified numerically against the SI evaluation).

#### Debye length and water dielectric constant

```
εr(T) = 87.740 − 0.40008 ΔT + 9.398e-4 ΔT² − 1.410e-6 ΔT³ ,   ΔT = T[K] − 273.15
κ = √( 2 NA e² (I·1000) / (εr ε0 k T) )        [m⁻¹] ;  returned as κ·1e-9 [nm⁻¹]
```

`I` is in mol/L (`·1000` → mol/m³). Constants: `e = 1.602176634e-19 C`, `ε0 = 8.8541878128e-12 F/m`, `k = 1.380649e-23 J/K`, `NA = 6.02214076e23 mol⁻¹`.

#### Sphere–plane interaction energy `U(h)` (output unit `kT`)

```
U_LW(h) = 2π R ΔG_LW h0² / h
U_AB(h) = 2π R λ_AB ΔG_AB · exp( (h0 − h)/λ_AB )
U_EL(h) = π ε0 εr R [ 2 ψ1 ψ2 ln( (1 + e^(−κh))/(1 − e^(−κh)) )
                      + (ψ1² + ψ2²) ln( 1 − e^(−2κh) ) ]
U_TOT = U_LW + U_AB + U_EL
```

with `ΔG` converted from mJ/m² to J/m² (`·1e-3`), lengths in m, `ψ` in V (`ζ·1e-3`), and the result divided by `kT` (`k·T_K`). The LW/AB forms are the Derjaguin approximation for a sphere of radius `R` (valid for `R ≫ h`); the EL form is the constant-potential HHF sphere–plane expression. This implementation was dimension-corrected on 2026-09-29 and is guarded by `scripts/xdlvo_unit_check.py`.

#### Barrier and minima (`analyze_profile`)

* Barrier = the **highest local maximum** of `U_TOT` (linear scan, strict `>` neighbours); `None` if there is no local maximum (monotonic curve).
* Minima = every local minimum of `U_TOT`; if the first grid point already rises (`U[0] < U[1]`), `(h_min, U[0])` is added as "primary". The first entry of the list is then always re-labelled `primary`, all others `secondary`. Note: with a monotonic attractive curve a single minimum at `h = 0.15 nm` is returned as the primary minimum; with an oscillating profile the label of the first minimum is forced to "primary" even if it is a secondary minimum.

### Parameters and defaults

Model constants (`xdlvo.PARAMS`):

| Symbol | Value | Meaning |
|---|---|---|
| `gamma_diiodo` | 50.8 mJ/m² | diiodomethane γ^LW |
| `gamma_form_LW`, `gamma_form_plus`, `gamma_form_minus` | 39.0, 2.28, 39.6 mJ/m² | formamide vOCG components |
| `gamma_water_LW`, `gamma_water_plus`, `gamma_water_minus` | 21.8, 25.5, 25.5 mJ/m² | water vOCG components |
| `h0` | 0.158 nm | minimum equilibrium separation at contact |
| `lambda_ab` | 0.6 nm | decay length of AB interactions |
| `hmin`, `hmax`, `dh` | 0.15, 25.0, 0.05 nm | separation grid for `U(h)` (498 points) |

Probe-liquid table (`PROBE_LIQUIDS`, `(γ^LW, γ^+, γ^-)` mJ/m²): diiodomethane (50.8, 0, 0), water (21.8, 25.5, 25.5), formamide (39.0, 2.28, 39.6), glycerol (34.0, 3.92, 57.4), ethylene glycol (29.0, 1.92, 47.0). `run()` only uses the three angles it is given — the liquid parameters are fixed to diiodomethane/water/formamide.

### Implementation notes

* Package `labtoolbox/xdlvo/`: `xdlvo.py` (210 lines), `sei.py` (135 lines). Dependencies: NumPy + matplotlib (Agg) only; no SciPy.
* `SurfaceEnergy` is a `@dataclass` with `gamma_lw`, `gamma_plus`, `gamma_minus`, `gamma_ab`, `gamma_total` and a formatted `__repr__`.
* Public functions: `water_dielectric`, `debye_length`, `surface_energy_from_contact_angles`, `delta_g`, `interaction_energy`, `analyze_profile`, `run`; re-exported by `labtoolbox.xdlvo.__init__`.
* The vOCG formamide-row fix of integration commit `46bdd8f` is regression-tested in `tests/test_xdlvo_surface_energy.py`; no other part of the numerical model changed.
* The embedded default bacterium is constructed inline in `run()`: `SurfaceEnergy(37.8, 0.6, 46.5, 2√(0.6·46.5), 37.8+2√(0.6·46.5))` — **the source does not cite where these *E. coli* values come from**; they are literature-like defaults, and users should substitute strain-specific measurements.
* Other probe liquids in `PROBE_LIQUIDS` (glycerol, ethylene glycol) are defined but not used by the three-liquid solver.
* CLI `labtoolbox xdlvo`; GUI tab **🧫 XDLVO**; the unified CLI registers `xdlvo` in `labtoolbox/cli.py`.

#### `sei.py` — Surface Element Integration on real/synthetic topography

```
U = ∫∫ ΔG( h(x,y) ) dA
ΔG_LW(h) = ΔG_LW(h0) · (h0/h)²
ΔG_AB(h) = ΔG_AB(h0) · exp( (h0 − h)/λ_AB )
ΔG_EL(h) = (κ ε0 εr/2) [ (ζ1² + ζ2²)(1 − coth κh) + 2 ζ1 ζ2 csch κh ]
```

Functions: `dg_per_area(h_nm, dG, I_M=0.15, T_K=298.15, zeta_m=None, zeta_f=None)`; `sphere_lower(R_nm, n=None)` (lower hemisphere grid, `n = clip(4R, 200, 900)` samples per side, spacing `dx = 2R/(n−1)`); `sei_sphere_on_surface(R_nm, surf_z, I_M=0.15, dG=..., ...)` (terrain resampled nearest-neighbour onto the sphere grid; the sphere is shifted vertically so the minimum gap equals `h0`); `sei_sphere_on_flat(R_nm, ...)` (used as a self-check against the Derjaguin integral); `lipss_field(period_nm, depth_nm, size_nm=2000, n=400, angle_deg=0)` — analytic LIPSS topography `z = (depth/2)·sin(2πu/Λ)`, `u = x·cosθ + y·sinθ`; `sei_rod_on_surface(R_rod_nm, length_nm, surf_z, ...)` — a rod modelled as a chain of `max(3, round(L/R)+1)` spheres along x with cyclically shifted terrain (`np.roll`). Units: lengths nm, energies J, contact `ΔG` mJ/m².
**Important unit quirk:** `dg_per_area` applies the HHF formula with ζ in **volts** (no `1e-3` conversion), unlike `delta_g`/`interaction_energy` which take mV. In the repository's scripts the SEI functions are called without zeta potentials (EL omitted), which avoids the ambiguity; do not mix the two zeta conventions.

### Assumptions, limitations and known quirks

* **Acid–base components from contact angles are solved correctly on the release branch.** The base commit `0e0508e` had the formamide row order wrong and returned `γ⁺`/`γ⁻` exchanged (historical note above); integration commit `46bdd8f` fixes the row and adds a regression test, so no manual swap is needed. The embedded bacterium SFE was always constructed directly and was never affected.
* **Sphere–plane geometry only.** `U(h)` uses the Derjaguin approximation (`R ≫ h`); it is a poor approximation for very small particles (`R` ≈ nm) or thick electrical double layers. The EL term is the constant-potential HHF form; constant-charge conditions are not modelled.
* **Flat, rigid, smooth surfaces** for `U(h)`; roughness requires the `sei.py` extension.
* **`ΔG` constants are temperature-independent**; only the dielectric constant/Debye length depend on `T`.
* **Default bacterium SFE is uncited** and geometry defaults (`R = 500 nm`) are generic — always supply measured strain zeta/SFE/radius for quantitative claims.
* **Profile labels are heuristic**: `barrier` can be negative (below `kT = 0`), and the first minimum is force-labelled "primary".
* `interaction_energy` arguments `radius_nm`, `I_M`, `T_K` are positional after `dG`; the `minima` entries contain NumPy floats (fine for plotting, not JSON-serialisable without conversion — `run()` converts `delta_g` values to `float` but not the profile).
* `sei.py` grid resampling ignores the terrain's physical pixel size (it assumes the `surf_z` grid matches the sphere grid); this is adequate for the relative energy comparisons it is used for but not for absolute SEI energies of sparse terrains.

### QC and validation

* `scripts/xdlvo_unit_check.py` compares the module's `U(h)` at contact with an independent analytic Derjaguin implementation for two chemistries (repulsive/attractive) and two radii (450 nm cell, 3.5 nm protein): PASS when the R ≥ 100 nm cases agree within 1%; the R = 3.5 nm O(λ/R) deviation is reported but not failed.
* `tests/test_xdlvo_surface_energy.py` (integration branch) guards the corrected SFE solver: three forward/inverse vOCG round-trips at six-decimal precision plus the README-angle acid–base split; it was added together with fix `46bdd8f`.
* Reproduced for this documentation at the base commit (Python 3.11 / NumPy 2.4; this interaction-energy code is unchanged by the fix) with `I = 0.15 M`, `T = 310.15 K`, ζ = (−25, −13) mV: `ΔG_LW = −4.897`, `ΔG_AB = 9.392`, `ΔG_EL = 0.00377`, `ΔG_ADH = 4.495 mJ/m²`; at the first grid point (`h = 0.15 nm`) `U_TOT = 3740.6 kT` equals the independent LW+AB analytic value plus the analytic EL value. `sei_sphere_on_flat` reproduces the numerical Derjaguin integral to 0.04%.
* No automated comparison against experimental adhesion data is built in; XDLVO predictions are thermodynamic tendencies, not measured adhesion forces.

### References

* van Oss CJ. *Interfacial Forces in Aqueous Media.* 2nd ed. CRC Press; 2006. (LW/AB theory, `h0` and `λ_AB` conventions)
* van Oss CJ, Chaudhury MK, Good RJ. Interfacial Lifshitz–van der Waals and polar interactions in macroscopic systems. *Chem Rev.* 1988;88(6):927–941.
* Bos R, van der Mei HC, Busscher HJ. Physico-chemical interactions in initial microbial adhesion and relevance for biofilm formation. *FEMS Microbiol Rev.* 1999;23(2):179–230.
* Israelachvili JN. *Intermolecular and Surface Forces.* 3rd ed. Academic Press; 2011. (DLVO/XDLVO, Derjaguin approximation, HHF electrostatics)
* Hogg R, Healy TW, Fuerstenau DW. Mutual coagulation of colloidal dispersions. *Trans Faraday Soc.* 1966;62:1638–1651. (HHF constant-potential expression)
* Derjaguin BV. Untersuchungen über die Reibung und Adhäsion, IV. *Kolloid-Z.* 1934;69:155–164. (Derjaguin approximation)
* Bhattacharjee S, Elimelech M. Surface element integration: a novel technique for evaluation of DLVO interaction between a particle and a flat plate. *J Colloid Interface Sci.* 1997;193(2):273–285. (SEI method used by `sei.py`)
* Malmberg CG, Maryott AA. Dielectric constant of water from 0 to 100 °C. *J Res Natl Bur Stand.* 1956;56:1–8. (empirical εr(T) polynomial)
* The `sei.py` docstring attributes the exact SEI formulation to Wang et al., *Materials & Design* 263 (2026) 115626, §2.7 — quoted here as code provenance only; it was not independently verified for this documentation.
* `scripts/xdlvo_unit_check.py` in this repository (dimension self-check).

## 中文

### 目的与科学背景

本模块实现用于细菌黏附的**扩展 DLVO（XDLVO）理论**：实测接触角 → 固体/细菌表面自由能（SFE）→ 接触距离处的黏附自由能 `ΔG_ADH`（Lifshitz–van der Waals（LW）、酸碱（AB）及可选的静电（EL）贡献）→ 球–平面相互作用能曲线 `U(h)` → 能量势垒与主/次势阱。它是 LabToolbox 黏附研究的理论侧：按预测黏附强弱对涂层（F-DLC、激光织构不锈钢）与 *E. coli* / *S. aureus* 的组合排序。

子模块 `sei.py` 用**表面单元积分（SEI）**把同一套物理推广到**粗糙形貌**：在实测 AFM 高度场上逐单元积分球–面相互作用，从而用平面 `ΔG(h)` 规律比较 LIPSS 条纹与纳米柱阵列。

### 输入与数据格式

`run(contact_angles, bacteria=None, radius_nm=500, I_M=0.01, zeta_m=None, zeta_f=None, T_K=298.15, output_dir="output")`：

| 输入 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `contact_angles` | 元组 `(θ_二碘甲烷, θ_水, θ_甲酰胺)` **或** 含 `theta_diiodo`、`theta_water`、`theta_form` 键的 dict | 必填 | 材料上的座滴接触角（度） |
| `bacteria` | `SurfaceEnergy` | 内嵌 *E. coli* 值 | 细菌 SFE（γ^LW、γ^+、γ^-、γ^AB、γ^TOT） |
| `radius_nm` | float | `500` | 球–平面模型的等效细胞半径（nm） |
| `I_M` | float | `0.01` | 离子强度（mol/L，用于 Debye 长度与 EL 项） |
| `zeta_m`、`zeta_f` | float 或 None | `None` | 材料 / 细菌 zeta 电位，单位 **mV**。两者都给出时才计算 EL 项 |
| `T_K` | float | `298.15` | 绝对温度（K） |
| `output_dir` | str | `output` | 图的输出目录 |

命令行以 JSON 传接触角：`labtoolbox xdlvo --angles '{"theta_diiodo":48.2,"theta_water":72.3,"theta_form":61.5}' --radius 500 --ionic 0.01 [--zeta-m ..] [--zeta-f ..]`。GUI 标签页 **🧫 XDLVO** 暴露三个角度、半径与离子强度（无 zeta 输入框）。

### 输出

`run()` 返回 dict，并写出图 `output/xdlvo_energy.png`：

```
{
  "surface_energy": SurfaceEnergy,          # 材料 SFE，mJ/m²
  "delta_g": {"LW": float, "AB": float, "ADH": float,         # mJ/m²
              "EL": float, "TOT": float},                     # 仅在给出 zeta 时
  "profile": {"barrier": float|None, "barrier_position": float|None,
              "minima": [(h_nm, U_kT, "primary"|"secondary"), ...]},
  "energy": {"h": ndarray, "LW": ndarray, "AB": ndarray,
             "EL": ndarray, "TOT": ndarray},                  # U 单位 kT，h 单位 nm
  "figure": path
}
```

图中纵轴为 `Interaction energy (kT)`，横轴为间距 `h`（nm），画 `U_LW`（蓝虚线）、`U_AB`（橙虚线）、`U_EL`（绿虚线，仅在非零时）与 `U_TOT`（红实线），并有 `y = 0` 参考线。

### 端到端流程

1. 解析三个接触角（元组或 dict）。
2. **三液求 SFE**——由二碘甲烷求 γ^LW；由水/甲酰胺两液解 2×2 线性方程组求 γ^+、γ^-；γ^AB = 2√(γ^+γ^-)，γ^TOT = γ^LW + γ^AB。
3. 若 `bacteria is None`，用内嵌 *E. coli* SFE `(γ^LW, γ^+, γ^-) = (37.8, 0.6, 46.5) mJ/m²`，否则用传入对象。
4. **接触处 ΔG**——由材料（`m`）、细菌（`f`）、水（`w`）的 SFE 分量算 LW 与 AB 项；若两个 zeta 都给，加入平面 HHF 静电项 `ΔG_EL(h0)`；`ΔG_ADH = ΔG_LW + ΔG_AB`，`ΔG_TOT = ΔG_ADH + ΔG_EL`。
5. **相互作用能曲线** `U(h)`：半径 `R` 的球在平板上方（LW/AB 用 Derjaguin 近似、EL 用 HHF），`h = 0.15 … 25 nm`、步长 0.05 nm，能量单位 `kT`。
6. **剖面分析**——找最高局部极大（能量势垒）与各局部极小（吸附态）。
7. 画各分量并保存图；返回全部结果。

### 算法与公式

#### 三液接触角求表面自由能

二碘甲烷为非极性液（`γ^+ = γ^- = 0`）：

```
γ_S^LW = ( γ_L^LW · (1 + cos θ_二碘甲烷) / (2 √γ_L^LW) )² = γ_L^LW (1 + cos θ_二碘甲烷)² / 4
```

对极性液体，令 `γ_L = γ_L^LW + 2√(γ_L^+ γ_L^-)`：

```
C_i = γ_Li (1 + cos θ_i)/2 − √( γ_S^LW · γ_Li^LW )
C_i = √(γ_S^+)·√(γ_Li^-) + √(γ_S^-)·√(γ_Li^+)          (i = 水, 甲酰胺)
```

模块组装的 2×2 方程组为 `a11, a12 = √γ_w^-, √γ_w^+`、`a21, a22 = √γ_f^-, √γ_f^+`，解 `[√γ_S^+; √γ_S^-]`：

```
[ a11 a12 ] [ √γ_S^+ ]   [ C1 ]
[ a21 a22 ] [ √γ_S^- ] = [ C2 ]
```

然后 `γ_S^+ = u²`、`γ_S^- = v²`、`γ_S^AB = 2√(γ_S^+ γ_S^-)`、`γ_S^TOT = γ_S^LW + γ_S^AB`。
**历史缺陷（已在集成分支 commit `46bdd8f` 修复）：** 基线 commit `0e0508e` 把甲酰胺行组装为 `a21 = √(γ_f^+)`、`a22 = √(γ_f^-)`，而 vOCG 方程要求 `a21 = √(γ_f^-)`、`a22 = √(γ_f^+)`。由于水行对称（`γ_w^+ = γ_w^- = 25.5`），求解器返回的 `γ_S^+` 与 `γ_S^-` 是**互换**的——例如 `(γ^LW, γ^+, γ^-) = (40, 1, 20)` mJ/m² 的表面会返回 `(40, 20, 1)`。

集成分支修正了行序，并新增 `tests/test_xdlvo_surface_energy.py`（运行 `python -m unittest discover -s tests`）：用三组已知表面（`(40, 1, 20)`、`(35, 0.1, 15)`、`(30, 5, 40)` mJ/m²）做正/反 vOCG 往返，精度 1e-6，并钉住 README 示例。修复后 README 角度 `48.2/72.3/61.5°` 得到 `γ^LW = 35.2721`、`γ^+ = 0.00099`、`γ^- = 15.5236`、`γ^AB = 0.2479`、`γ^TOT = 35.5200 mJ/m²`——物理上合理（`γ^+` ≈ 0，酸碱项很小）。`γ^LW` 从来不受影响。求解器仍会静默平方负的平方根，因此非物理的接触角组合可能表现为一个小的正分量而不是报错。

#### 接触距离 `h0` 处的黏附自由能

```
ΔG_LW = −2 ( √γ_m^LW − √γ_w^LW ) ( √γ_f^LW − √γ_w^LW )
ΔG_AB = 2√γ_w^+ ( √γ_f^- + √γ_m^- − √γ_w^- )
      + 2√γ_w^- ( √γ_f^+ + √γ_m^+ − √γ_w^+ )
      − 2√(γ_f^- γ_m^+) − 2√(γ_f^+ γ_m^-)
ΔG_ADH = ΔG_LW + ΔG_AB                       [mJ/m²]
```

给出 zeta 电位（mV）时，接触处的静电项用平面 HHF 式：

```
ΔG_EL(h0) = (κ ε0 εr / 2) · [ (ζ_m² + ζ_f²)(1 − coth(κ h0)) + 2 ζ_m ζ_f csch(κ h0) ]
```

其中 `κ` 单位 1/nm、`ζ` 单位 mV；模块的 `1e6` 因子把该式换算为 mJ/m²（已与 SI 直接计算核对）。

#### Debye 长度与水的介电常数

```
εr(T) = 87.740 − 0.40008 ΔT + 9.398e-4 ΔT² − 1.410e-6 ΔT³ ,   ΔT = T[K] − 273.15
κ = √( 2 NA e² (I·1000) / (εr ε0 k T) )        [m⁻¹]；函数返回 κ·1e-9 [nm⁻¹]
```

`I` 单位为 mol/L（`·1000` → mol/m³）。常数：`e = 1.602176634e-19 C`、`ε0 = 8.8541878128e-12 F/m`、`k = 1.380649e-23 J/K`、`NA = 6.02214076e23 mol⁻¹`。

#### 球–平面相互作用能 `U(h)`（输出单位 `kT`）

```
U_LW(h) = 2π R ΔG_LW h0² / h
U_AB(h) = 2π R λ_AB ΔG_AB · exp( (h0 − h)/λ_AB )
U_EL(h) = π ε0 εr R [ 2 ψ1 ψ2 ln( (1 + e^(−κh))/(1 − e^(−κh)) )
                      + (ψ1² + ψ2²) ln( 1 − e^(−2κh) ) ]
U_TOT = U_LW + U_AB + U_EL
```

`ΔG` 由 mJ/m² 换算为 J/m²（`·1e-3`），长度用 m，`ψ` 用 V（`ζ·1e-3`），最后除以 `kT`（`k·T_K`）。LW/AB 形式是半径 `R` 球的 Derjaguin 近似（要求 `R ≫ h`）；EL 形式是恒电位 HHF 球–平面式。该实现于 2026-09-29 做过量纲修正，并由 `scripts/xdlvo_unit_check.py` 守护。

#### 势垒与势阱（`analyze_profile`）

* 势垒 = `U_TOT` 的**最高局部极大**（线性扫描，严格 `>` 邻点）；不存在局部极大（单调曲线）时为 `None`。
* 势阱 = `U_TOT` 的所有局部极小；若首个网格点已上升（`U[0] < U[1]`），把 `(h_min, U[0])` 作为 "primary" 加入。随后列表第一项一律改标 `primary`，其余标 `secondary`。注意：单调吸引曲线会返回 `h = 0.15 nm` 处的单个 "primary" 极小；剖面有多个极小值时，第一项的 "primary" 标签是强制的，即使它实际上是次势阱。

### 参数与默认值

模型常数（`xdlvo.PARAMS`）：

| 符号 | 值 | 含义 |
|---|---|---|
| `gamma_diiodo` | 50.8 mJ/m² | 二碘甲烷 γ^LW |
| `gamma_form_LW`, `gamma_form_plus`, `gamma_form_minus` | 39.0, 2.28, 39.6 mJ/m² | 甲酰胺 vOCG 分量 |
| `gamma_water_LW`, `gamma_water_plus`, `gamma_water_minus` | 21.8, 25.5, 25.5 mJ/m² | 水 vOCG 分量 |
| `h0` | 0.158 nm | 接触处最小平衡间距 |
| `lambda_ab` | 0.6 nm | AB 作用的衰减长度 |
| `hmin`, `hmax`, `dh` | 0.15, 25.0, 0.05 nm | `U(h)` 的间距网格（498 点） |

探测液体表（`PROBE_LIQUIDS`，`(γ^LW, γ^+, γ^-)` mJ/m²）：二碘甲烷 (50.8, 0, 0)、水 (21.8, 25.5, 25.5)、甲酰胺 (39.0, 2.28, 39.6)、甘油 (34.0, 3.92, 57.4)、乙二醇 (29.0, 1.92, 47.0)。`run()` 只用传入的三个角度，液体参数固定为二碘甲烷/水/甲酰胺。

### 实现说明

* 包 `labtoolbox/xdlvo/`：`xdlvo.py`（210 行）、`sei.py`（135 行）。依赖仅 NumPy + matplotlib（Agg），不用 SciPy。
* `SurfaceEnergy` 为 `@dataclass`，字段 `gamma_lw`、`gamma_plus`、`gamma_minus`、`gamma_ab`、`gamma_total`，带格式化 `__repr__`。
* 公开函数：`water_dielectric`、`debye_length`、`surface_energy_from_contact_angles`、`delta_g`、`interaction_energy`、`analyze_profile`、`run`；由 `labtoolbox.xdlvo.__init__` 再导出。
* 集成分支 commit `46bdd8f` 的 vOCG 甲酰胺行修正由 `tests/test_xdlvo_surface_energy.py` 回归测试守护；数值模型的其余部分未改动。
* 内嵌默认细菌直接在 `run()` 里构造：`SurfaceEnergy(37.8, 0.6, 46.5, 2√(0.6·46.5), 37.8+2√(0.6·46.5))`——**源码没有注明这些 *E. coli* 值的出处**；它们是类文献默认值，定量使用时应替换为实测菌株参数。
* `PROBE_LIQUIDS` 中的甘油、乙二醇虽已定义，但三液求解器不使用。
* 命令行 `labtoolbox xdlvo`；GUI 标签页 **🧫 XDLVO**；统一 CLI 在 `labtoolbox/cli.py` 注册 `xdlvo` 子命令。

#### `sei.py`——真实/合成形貌上的表面单元积分

```
U = ∫∫ ΔG( h(x,y) ) dA
ΔG_LW(h) = ΔG_LW(h0) · (h0/h)²
ΔG_AB(h) = ΔG_AB(h0) · exp( (h0 − h)/λ_AB )
ΔG_EL(h) = (κ ε0 εr/2) [ (ζ1² + ζ2²)(1 − coth κh) + 2 ζ1 ζ2 csch κh ]
```

函数：`dg_per_area(h_nm, dG, I_M=0.15, T_K=298.15, zeta_m=None, zeta_f=None)`；`sphere_lower(R_nm, n=None)`（下半球网格，`n = clip(4R, 200, 900)` 每边采样点，间距 `dx = 2R/(n−1)`）；`sei_sphere_on_surface(R_nm, surf_z, I_M=0.15, dG=..., ...)`（地形最近邻重采样到球网格；竖直平移球使其最小间隙等于 `h0`）；`sei_sphere_on_flat(R_nm, ...)`（用作对 Derjaguin 积分的自检）；`lipss_field(period_nm, depth_nm, size_nm=2000, n=400, angle_deg=0)`——解析 LIPSS 形貌 `z = (depth/2)·sin(2πu/Λ)`，`u = x·cosθ + y·sinθ`；`sei_rod_on_surface(R_rod_nm, length_nm, surf_z, ...)`——杆状菌建模为沿 x 排列的 `max(3, round(L/R)+1)` 个球链，地形用 `np.roll` 循环平移。单位：长度 nm、能量 J、接触 `ΔG` mJ/m²。
**重要单位怪癖：** `dg_per_area` 直接按 HHF 公式使用**伏特**单位的 ζ（没有 `1e-3` 换算），而 `delta_g`/`interaction_energy` 用 mV。仓库脚本调用 SEI 函数时都不传 zeta（省略 EL），从而避开歧义；不要把两种 zeta 约定混用。

### 假设、局限与已知怪癖

* **发布分支上接触角导出的酸碱分量已正确求解。** 基线 commit `0e0508e` 的甲酰胺行序有误，会返回互换的 `γ⁺`/`γ⁻`（见上方历史说明）；集成分支 commit `46bdd8f` 已修正并加入回归测试，不再需要手工交换。内嵌细菌 SFE 一直是直接构造的，从未受影响。
* **仅球–平面几何。** `U(h)` 用 Derjaguin 近似（`R ≫ h`）；对极小颗粒（`R` 约 nm）或厚双电层偏差大。EL 项为恒电位 HHF 式，不建模恒电荷条件。
* 对 `U(h)` 假设**平面、刚性、光滑表面**；粗糙度需用 `sei.py` 扩展。
* **`ΔG` 常数与温度无关**；只有介电常数/Debye 长度随 `T` 变化。
* **默认细菌 SFE 无出处**，几何默认值（`R = 500 nm`）也是通用值——定量结论务必提供实测菌株的 zeta/SFE/半径。
* **剖面标签是启发式的**：`barrier` 可能为负（低于 `kT = 0`）；第一个极小被强制标为 "primary"。
* `interaction_energy` 的 `radius_nm`、`I_M`、`T_K` 在 `dG` 之后按位置传参；`minima` 元素含 NumPy 浮点（画图无碍，但未转换时不能直接 JSON 序列化——`run()` 只把 `delta_g` 的值转成了 `float`，未转 `profile`）。
* `sei.py` 的网格重采样忽略地形的物理像素尺寸（假定 `surf_z` 网格与球网格一致）；用于相对能量比较足够，但不适合稀疏地形上的绝对 SEI 能量。

### 质控与验证

* `scripts/xdlvo_unit_check.py` 把模块在接触处的 `U(h)` 与独立解析 Derjaguin 实现对比：两种化学（排斥/吸引）× 两个尺度（450 nm 细胞、3.5 nm 蛋白）；`R ≥ 100 nm` 的算例偏差 < 1% 判 PASS；`R = 3.5 nm` 的 O(λ/R) 偏差只报告不判失败。
* `tests/test_xdlvo_surface_energy.py`（集成分支）守护修正后的 SFE 求解器：三组正/反 vOCG 往返（六位小数）加 README 角度的酸碱拆分；该测试与修复 `46bdd8f` 一同加入。
* 本文档在基线上的核对（Python 3.11 / NumPy 2.4；相互作用能代码未受该修复影响，`I = 0.15 M`、`T = 310.15 K`、ζ = (−25, −13) mV）：`ΔG_LW = −4.897`、`ΔG_AB = 9.392`、`ΔG_EL = 0.00377`、`ΔG_ADH = 4.495 mJ/m²`；第一个网格点（`h = 0.15 nm`）`U_TOT = 3740.6 kT`，与独立 LW+AB 解析值加解析 EL 值一致。`sei_sphere_on_flat` 与数值 Derjaguin 积分吻合到 0.04%。
* 未内建与实验黏附数据的自动对比；XDLVO 预测的是热力学倾向，不是实测黏附力。

### 参考文献

* van Oss CJ. *Interfacial Forces in Aqueous Media.* 2nd ed. CRC Press; 2006.（LW/AB 理论、`h0` 与 `λ_AB` 约定）
* van Oss CJ, Chaudhury MK, Good RJ. Interfacial Lifshitz–van der Waals and polar interactions in macroscopic systems. *Chem Rev.* 1988;88(6):927–941.
* Bos R, van der Mei HC, Busscher HJ. Physico-chemical interactions in initial microbial adhesion and relevance for biofilm formation. *FEMS Microbiol Rev.* 1999;23(2):179–230.
* Israelachvili JN. *Intermolecular and Surface Forces.* 3rd ed. Academic Press; 2011.（DLVO/XDLVO、Derjaguin 近似、HHF 静电）
* Hogg R, Healy TW, Fuerstenau DW. Mutual coagulation of colloidal dispersions. *Trans Faraday Soc.* 1966;62:1638–1651.（HHF 恒电位表达式）
* Derjaguin BV. Untersuchungen über die Reibung und Adhäsion, IV. *Kolloid-Z.* 1934;69:155–164.（Derjaguin 近似）
* Bhattacharjee S, Elimelech M. Surface element integration: a novel technique for evaluation of DLVO interaction between a particle and a flat plate. *J Colloid Interface Sci.* 1997;193(2):273–285.（`sei.py` 使用的 SEI 方法）
* Malmberg CG, Maryott AA. Dielectric constant of water from 0 to 100 °C. *J Res Natl Bur Stand.* 1956;56:1–8.（经验 εr(T) 多项式）
* `sei.py` 的 docstring 把该 SEI 公式归因于 Wang et al., *Materials & Design* 263 (2026) 115626, §2.7——此处仅作为代码出处转述，本文档未独立核实。
* 本仓库 `scripts/xdlvo_unit_check.py`（量纲自检）。
