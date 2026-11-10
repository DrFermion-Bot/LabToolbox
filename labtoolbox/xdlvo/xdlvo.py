# -*- coding: utf-8 -*-
"""
XDLVO 细菌粘附预测模块
移植自 GitHub YHC-contrail/XDLVO-Theory-Calculator (经 xdlvo-bacterial-adhesion 技能验证)。

流程: 接触角 (二碘甲烷/水/甲酰胺) → 表面自由能 (LW/AB 分量)
     → ΔGadh (LW+AB+EL) → 相互作用能量曲线 → 势垒/势阱分析
"""
import numpy as np
from dataclasses import dataclass

PHYS = {'e': 1.602176634e-19, 'eps0': 8.8541878128e-12, 'k': 1.380649e-23, 'NA': 6.02214076e23}

PARAMS = {
    'gamma_diiodo': 50.8, 'gamma_form_LW': 39.0, 'gamma_form_plus': 2.28,
    'gamma_form_minus': 39.6, 'gamma_water_LW': 21.8, 'gamma_water_plus': 25.5,
    'gamma_water_minus': 25.5, 'h0': 0.158, 'lambda_ab': 0.6,
    'hmin': 0.15, 'hmax': 25.0, 'dh': 0.05,
}

PROBE_LIQUIDS = {
    'diiodomethane': (50.8, 0.0, 0.0),
    'water': (21.8, 25.5, 25.5),
    'formamide': (39.0, 2.28, 39.6),
    'glycerol': (34.0, 3.92, 57.4),
    'ethylene_glycol': (29.0, 1.92, 47.0),
}


@dataclass
class SurfaceEnergy:
    gamma_lw: float
    gamma_plus: float
    gamma_minus: float
    gamma_ab: float
    gamma_total: float

    def __repr__(self):
        return (f"γ^LW={self.gamma_lw:.2f}, γ⁺={self.gamma_plus:.2f}, "
                f"γ⁻={self.gamma_minus:.2f}, γ^AB={self.gamma_ab:.2f}, "
                f"γ^TOT={self.gamma_total:.2f} mJ/m²")


def water_dielectric(T_K):
    dT = T_K - 273.15
    return 87.740 - 0.40008*dT + 9.398e-4*dT**2 - 1.410e-6*dT**3


def debye_length(I_M, T_K):
    e = PHYS['e']; eps0 = PHYS['eps0']; k = PHYS['k']; NA = PHYS['NA']
    eps_r = water_dielectric(T_K)
    I_SI = I_M * 1000
    kappa_m = np.sqrt(2 * NA * e**2 * I_SI / (eps_r * eps0 * k * T_K))
    return kappa_m * 1e-9


def surface_energy_from_contact_angles(theta_diiodo, theta_water, theta_form,
                                       liquid_diiodo='diiodomethane',
                                       liquid_water='water',
                                       liquid_form='formamide'):
    l_di = PROBE_LIQUIDS[liquid_diiodo]
    l_w = PROBE_LIQUIDS[liquid_water]
    l_f = PROBE_LIQUIDS[liquid_form]
    t1, t2, t3 = map(np.radians, (theta_diiodo, theta_water, theta_form))
    gamma_lw = (l_di[0] * (1 + np.cos(t1)) / (2 * np.sqrt(l_di[0])))**2
    C1 = (l_w[0] + 2*np.sqrt(l_w[1]*l_w[2])) * (1 + np.cos(t2)) / 2 - np.sqrt(l_w[0]*gamma_lw)
    C2 = (l_f[0] + 2*np.sqrt(l_f[1]*l_f[2])) * (1 + np.cos(t3)) / 2 - np.sqrt(l_f[0]*gamma_lw)
    a11, a12 = np.sqrt(l_w[2]), np.sqrt(l_w[1])
    # vOCG: the formamide row multiplies sqrt(gamma_S^+) by sqrt(gamma_f^-)
    # and sqrt(gamma_S^-) by sqrt(gamma_f^+); the two liquid terms are not symmetric.
    a21, a22 = np.sqrt(l_f[2]), np.sqrt(l_f[1])
    det = a11*a22 - a12*a21
    if abs(det) < 1e-10:
        raise ValueError("病态矩阵: 探测液体酸碱特性太接近")
    sqrt_gp = (C1*a22 - C2*a12) / det
    sqrt_gm = (a11*C2 - a21*C1) / det
    gp = sqrt_gp**2; gm = sqrt_gm**2
    gab = 2 * np.sqrt(gp*gm)
    return SurfaceEnergy(gamma_lw, gp, gm, gab, gamma_lw + gab)


def delta_g(membrane, foulant, I_M, T_K=298.15, zeta_m=None, zeta_f=None):
    p = PARAMS
    sw = (p['gamma_water_LW'], p['gamma_water_plus'], p['gamma_water_minus'])
    s_lw = np.sqrt(sw[0]); s_p = np.sqrt(sw[1]); s_m = np.sqrt(sw[2])
    m_lw = np.sqrt(membrane.gamma_lw); m_p = np.sqrt(membrane.gamma_plus); m_m = np.sqrt(membrane.gamma_minus)
    f_lw = np.sqrt(foulant.gamma_lw); f_p = np.sqrt(foulant.gamma_plus); f_m = np.sqrt(foulant.gamma_minus)
    dg_lw = -2 * (m_lw - s_lw) * (f_lw - s_lw)
    dg_ab = (2*s_p*(f_m + m_m - s_m) + 2*s_m*(f_p + m_p - s_p)
             - 2*np.sqrt(foulant.gamma_minus*membrane.gamma_plus)
             - 2*np.sqrt(foulant.gamma_plus*membrane.gamma_minus))
    result = {'LW': dg_lw, 'AB': dg_ab, 'ADH': dg_lw + dg_ab}
    if zeta_m is not None and zeta_f is not None:
        kappa = debye_length(I_M, T_K)
        eps_r = water_dielectric(T_K)
        zm, zf = zeta_m, zeta_f
        z_sum2 = zm**2 + zf**2
        kh0 = kappa * p['h0']
        coth = 1/np.tanh(kh0) if abs(kh0) > 1e-10 else np.inf
        csch = 1/np.sinh(kh0) if abs(kh0) > 1e-10 else np.inf
        dg_el = (kappa*PHYS['eps0']*eps_r/2) * z_sum2 * (1 - coth + 2*zf*zm*csch/z_sum2) * 1e6
        result['EL'] = dg_el
        result['TOT'] = dg_lw + dg_ab + dg_el
    return result


def interaction_energy(membrane, foulant, dG, radius_nm, I_M, T_K=298.15,
                       zeta_m=None, zeta_f=None):
    """球–平面 XDLVO 相互作用能曲线 U(h)，返回单位 = kT。

    2026-09-29 量纲修正（修正前 LW 项比 AB 项小 1000×、EL 项又是独立量纲 → 曲线失真；
    用 scripts/xdlvo_unit_check.py 对照解析 Derjaguin 自检）：
        U_LW = 2π R ΔG^LW h0² / h
        U_AB = 2π R λ ΔG^AB exp((h0 − h)/λ)
        U_EL = π ε0 εr R [ 2ψ1ψ2·ln((1+e^−κh)/(1−e^−κh)) + (ψ1²+ψ2²)·ln(1−e^−2κh) ]   (HHF)
    长度内部取 SI(m)，ΔG 输入 mJ/m²（自动换算），ζ 输入 mV，输出除以 kT(T_K)。
    """
    p = PARAMS
    h_nm = np.arange(p['hmin'], p['hmax'] + p['dh'], p['dh'])
    h = h_nm * 1e-9                  # m
    a = radius_nm * 1e-9             # m
    h0 = p['h0'] * 1e-9              # m
    lam = p['lambda_ab'] * 1e-9      # m
    kT = PHYS['k'] * T_K
    u_lw = 2*np.pi*a*dG['LW']*1e-3*h0**2/h / kT
    u_ab = 2*np.pi*a*lam*dG['AB']*1e-3*np.exp((h0 - h)/lam) / kT
    u_el = np.zeros_like(h)
    if zeta_m is not None and zeta_f is not None:
        kappa_1nm = debye_length(I_M, T_K)       # κ, 单位 1/nm
        eps_r = water_dielectric(T_K)
        zm, zf = zeta_m*1e-3, zeta_f*1e-3        # V
        kh = kappa_1nm * h_nm
        e1 = np.exp(-np.clip(kh, 0, 700))
        e2 = np.exp(-np.clip(2*kh, 0, 700))
        term1 = np.log((1 + e1)/np.clip(1 - e1, 1e-12, None))
        term2 = np.log(np.clip(1 - e2, 1e-12, None))
        u_el = np.pi*PHYS['eps0']*eps_r*a*(2*zm*zf*term1 + (zm**2 + zf**2)*term2) / kT
    u_tot = u_lw + u_ab + u_el
    return {'h': h_nm, 'LW': u_lw, 'AB': u_ab, 'EL': u_el, 'TOT': u_tot}


def analyze_profile(energy):
    h, U = energy['h'], energy['TOT']
    barrier, bar_pos = None, None
    for i in range(1, len(U)-1):
        if U[i] > U[i-1] and U[i] > U[i+1]:
            if barrier is None or U[i] > barrier:
                barrier, bar_pos = U[i], h[i]
    minima = []
    if U[0] < U[1]:
        minima.append((h[0], U[0], 'primary'))
    for i in range(1, len(U)-1):
        if U[i] < U[i-1] and U[i] < U[i+1]:
            minima.append((h[i], U[i], 'secondary'))
    if minima:
        minima[0] = (minima[0][0], minima[0][1], 'primary')
    return {'barrier': barrier, 'barrier_position': bar_pos, 'minima': minima}


def run(contact_angles, bacteria=None, radius_nm=500, I_M=0.01,
        zeta_m=None, zeta_f=None, T_K=298.15, output_dir="output"):
    """一键 XDLVO 分析。
    contact_angles: (θ_diiodo, θ_water, θ_form) 或 dict.
    bacteria: SurfaceEnergy (默认 E. coli 文献值)
    """
    if isinstance(contact_angles, (list, tuple)):
        se = surface_energy_from_contact_angles(*contact_angles)
    else:
        se = surface_energy_from_contact_angles(
            contact_angles["theta_diiodo"], contact_angles["theta_water"],
            contact_angles["theta_form"])

    if bacteria is None:
        bacteria = SurfaceEnergy(gamma_lw=37.8, gamma_plus=0.6, gamma_minus=46.5,
                                 gamma_ab=2*np.sqrt(0.6*46.5),
                                 gamma_total=37.8+2*np.sqrt(0.6*46.5))
    dG = delta_g(se, bacteria, I_M=I_M, T_K=T_K, zeta_m=zeta_m, zeta_f=zeta_f)
    E = interaction_energy(se, bacteria, dG, radius_nm=radius_nm, I_M=I_M,
                           T_K=T_K, zeta_m=zeta_m, zeta_f=zeta_f)
    prof = analyze_profile(E)

    # 画图
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ..common.io_utils import save_figure, ensure_output_dir
    ensure_output_dir(output_dir)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(E['h'], E['LW'], ls='--', label='LW', color='#1f77b4')
    ax.plot(E['h'], E['AB'], ls='--', label='AB', color='#ff7f0e')
    if np.any(E['EL'] != 0):
        ax.plot(E['h'], E['EL'], ls='--', label='EL', color='#2ca02c')
    ax.plot(E['h'], E['TOT'], lw=2, label='Total', color='#d62728')
    ax.axhline(0, color='gray', lw=0.8)
    ax.set_xlabel("Separation distance h (nm)", fontsize=12)
    ax.set_ylabel("Interaction energy (kT)", fontsize=12)
    ax.set_title("XDLVO Interaction Energy", fontsize=13)
    ax.legend(frameon=False)
    ax.tick_params(direction='in')
    plt.tight_layout()
    fig_path = save_figure(fig, f"{output_dir}/xdlvo_energy.png")
    plt.close(fig)

    return {
        "surface_energy": se,
        "delta_g": {k: float(v) for k, v in dG.items()},
        "profile": prof,
        "figure": fig_path,
        "energy": E,
    }
