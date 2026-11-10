"""Regression tests for the vOCG surface-energy solver (xdlvo)."""
import unittest

import numpy as np

from labtoolbox.xdlvo.xdlvo import PROBE_LIQUIDS, surface_energy_from_contact_angles


def _angles_for(g_lw, g_plus, g_minus):
    """Forward vOCG: contact angles of the three probe liquids on a known SFE."""
    out = []
    for name in ("diiodomethane", "water", "formamide"):
        g_l, lp, lm = PROBE_LIQUIDS[name]
        cos = (2 * (np.sqrt(g_lw * g_l) + np.sqrt(g_plus * lm) + np.sqrt(g_minus * lp))
               / (g_l + 2 * np.sqrt(lp * lm))) - 1
        out.append(np.degrees(np.arccos(np.clip(cos, -1, 1))))
    return tuple(out)


class XdlvoSurfaceEnergyTest(unittest.TestCase):
    def test_round_trip_three_probe_liquids(self):
        # The formamide row is asymmetric, so a swap of gamma+ / gamma- is detectable.
        for sfe in ((40.0, 1.0, 20.0), (35.0, 0.1, 15.0), (30.0, 5.0, 40.0)):
            solved = surface_energy_from_contact_angles(*_angles_for(*sfe))
            self.assertAlmostEqual(solved.gamma_lw, sfe[0], places=6)
            self.assertAlmostEqual(solved.gamma_plus, sfe[1], places=6)
            self.assertAlmostEqual(solved.gamma_minus, sfe[2], places=6)

    def test_readme_angles_return_physical_acid_base_split(self):
        # Water/diiodomethane/formamide angles from the README example.
        solved = surface_energy_from_contact_angles(48.2, 72.3, 61.5)
        self.assertAlmostEqual(solved.gamma_lw, 35.272097, places=5)
        self.assertAlmostEqual(solved.gamma_plus, 0.00099, places=4)
        self.assertAlmostEqual(solved.gamma_minus, 15.523619, places=5)


if __name__ == "__main__":
    unittest.main()
