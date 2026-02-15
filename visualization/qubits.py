"""
Composite qubit drawings built from primitives.

Each composite knows how to place itself and exposes **anchor points**
(in local coordinates) so the lattice layout engine can wire them together.
"""

from __future__ import annotations

import numpy as np
import matplotlib.patches as patches
import matplotlib.transforms as transforms
from matplotlib.axes import Axes
from typing import Dict, Tuple

from .styles import (
    FluxoniumDims, TunableTransmonDims,
    CouplerXmonDims, DCSqUIDDims, ResonatorDims, FluxLineDims,
    DEFAULT_PALETTE,
)
from .primitives import Xmon, JJChain, JosephsonJunction, DCSqUID, Resonator, FluxLine, _stamp_rect


# ═══════════════════════════════════════════════════════════════════════════
#  FLUXONIUM DATA QUBIT
#  Xmon body  +  two parallel JJ chains (45° tilted)  +  phase-slip JJ
# ═══════════════════════════════════════════════════════════════════════════
class FluxoniumQubit:
    """
    A fluxonium qubit drawn as an Xmon cross with a superinductance loop.

    The superinductance consists of two parallel JJ chains exiting at
    ``chain_angle`` (default −45°) from the Xmon centre, closed at the far
    end by a connector bar and a phase-slip junction.

    Anchor points (local coords, before global rotation):
        "center"  – Xmon centre (0, 0)
        "arm_N"   – tip of each Xmon arm (N ∈ {0, 90, 180, 270})
    """

    def __init__(self, dims: FluxoniumDims | None = None):
        if dims is None:
            dims = FluxoniumDims()
        self.dims = dims
        self._xmon = Xmon(dims=dims.xmon)
        self._chain = JJChain(dims=dims.chain)
        self._jj = JosephsonJunction(width=6, height=10)  # scaled to match smaller chain

    # ── anchors (local) ────────────────────────────────────────────────
    def anchors(self) -> Dict[str, np.ndarray]:
        pts: Dict[str, np.ndarray] = {"center": np.array([0.0, 0.0])}
        for a in (0, 90, 180, 270):
            pts[f"arm_{a}"] = self._xmon.arm_tip(a)
        return pts

    def anchor_global(self, name: str, xy: Tuple[float, float], angle: float) -> np.ndarray:
        """Return anchor *name* transformed to global coords."""
        local = self.anchors()[name]
        rad = np.radians(angle)
        rot = np.array([[np.cos(rad), -np.sin(rad)],
                        [np.sin(rad),  np.cos(rad)]])
        return rot @ local + np.array(xy)

    # ── drawing ─────────────────────────────────────────────────────────
    def place(self, ax: Axes, xy=(0, 0), angle: float = 0,
              color_xmon=None, color_chain_island=None, color_chain_bridge=None,
              color_junction=None, color_connector=None):
        d = self.dims
        pal = DEFAULT_PALETTE
        color_xmon = color_xmon or pal.xmon_body
        color_chain_island = color_chain_island or pal.jj_chain_island
        color_chain_bridge = color_chain_bridge or pal.jj_chain_bridge
        color_junction = color_junction or pal.junction
        color_connector = color_connector or pal.connector

        # 1) Xmon body
        self._xmon.place(ax, xy, angle, color=color_xmon)

        # 2) JJ chains --------------------------------------------------
        # Chain direction in *global* frame
        chain_global_angle = angle + d.chain_angle
        rad = np.radians(chain_global_angle)
        vec_fwd = np.array([np.cos(rad), np.sin(rad)])
        vec_perp = np.array([-np.sin(rad), np.cos(rad)])

        origin = np.asarray(xy, dtype=float)
        center_start = origin + vec_fwd * d.chain_start_dist

        start_A = center_start + vec_perp * (d.chain_separation / 2)
        start_B = center_start - vec_perp * (d.chain_separation / 2)

        self._chain.place(ax, start_A, chain_global_angle,
                          color_island=color_chain_island,
                          color_bridge=color_chain_bridge)
        self._chain.place(ax, start_B, chain_global_angle,
                          color_island=color_chain_island,
                          color_bridge=color_chain_bridge)

        # 3) Connector bar + phase-slip JJ at far end -------------------
        actual_len = self._chain.total_length
        end_A = start_A + vec_fwd * actual_len
        end_B = start_B + vec_fwd * actual_len
        bar_center = (end_A + end_B) / 2
        bar_len = d.chain_separation + d.connector_bar_extra

        base_bar = (
            transforms.Affine2D()
            .rotate_deg(chain_global_angle + 90)
            .translate(bar_center[0], bar_center[1])
            + ax.transData
        )
        _stamp_rect(
            ax, (-bar_len / 2, -d.connector_bar_height / 2),
            bar_len, d.connector_bar_height,
            0, base_bar, facecolor=color_connector, edgecolor=None,
        )

        # Phase-slip junction
        self._jj.place(ax, tuple(bar_center), chain_global_angle,
                       color=color_junction)


# ═══════════════════════════════════════════════════════════════════════════
#  TUNABLE TRANSMON COUPLER
#  Asymmetric Xmon  +  DC SQUID on one short arm  +  readout resonator on
#  the other short arm
# ═══════════════════════════════════════════════════════════════════════════
class TunableTransmonCoupler:
    """
    A tunable-transmon coupler (frequency-tunable via flux through a SQUID).

    Drawn as an asymmetric Xmon:
      - Two **long** arms (0° and 180°) face the neighbouring data qubits.
      - Two **short** arms (90° and 270°):
          * One carries a DC SQUID (two large Josephson junctions).
          * The other connects to a readout resonator.

    Parameters
    ----------
    dims : TunableTransmonDims | None
        Full dimension set. ``dims.squid_arm_index`` selects which short arm
        (0 → 90°, 1 → 270°) gets the SQUID; the other gets the resonator.
    """

    # Map logical short-arm index → angle
    _SHORT_ARM_ANGLES = {0: 90, 1: 270}

    def __init__(self, dims: TunableTransmonDims | None = None):
        if dims is None:
            dims = TunableTransmonDims()
        self.dims = dims

        self._xmon = Xmon(dims=dims.xmon)
        self._squid = DCSqUID(dims=dims.dc_squid)
        self._resonator = Resonator(dims=dims.resonator)
        self._flux_line = FluxLine(dims=dims.flux_line)

        # Determine which angles get SQUID / resonator
        self._squid_angle = self._SHORT_ARM_ANGLES[dims.squid_arm_index]
        self._res_angle = self._SHORT_ARM_ANGLES[dims.resonator_arm_index]

    # ── anchors (local) ────────────────────────────────────────────────
    def anchors(self) -> Dict[str, np.ndarray]:
        pts: Dict[str, np.ndarray] = {"center": np.array([0.0, 0.0])}
        for a in (0, 90, 180, 270):
            pts[f"arm_{a}"] = self._xmon.arm_tip(a)
        return pts

    def anchor_global(self, name: str, xy: Tuple[float, float], angle: float) -> np.ndarray:
        local = self.anchors()[name]
        rad = np.radians(angle)
        rot = np.array([[np.cos(rad), -np.sin(rad)],
                        [np.sin(rad),  np.cos(rad)]])
        return rot @ local + np.array(xy)

    # ── internal helper: position along an arm ─────────────────────────
    def _arm_endpoint(self, arm_angle_deg: int) -> np.ndarray:
        """Local (x,y) at the outer edge of the pad on a given arm."""
        return self._xmon.arm_tip(arm_angle_deg)

    # ── drawing ─────────────────────────────────────────────────────────
    def place(self, ax: Axes, xy=(0, 0), angle: float = 0,
              mirror: bool = False,
              color_body=None, color_squid=None, color_resonator=None):
        """
        Draw the coupler.

        Parameters
        ----------
        mirror : bool
            If True, swap which short arm carries the SQUID vs. the resonator.
            Use this to flip the resonator to the opposite side without
            changing the global angle.
        """
        pal = DEFAULT_PALETTE
        color_body = color_body or pal.coupler_body
        color_squid = color_squid or pal.dc_squid_body
        color_resonator = color_resonator or pal.resonator

        # Resolve which arm gets which (possibly mirrored)
        if mirror:
            squid_angle = self._res_angle
            res_angle = self._squid_angle
        else:
            squid_angle = self._squid_angle
            res_angle = self._res_angle

        # 1) Xmon body (asymmetric arms)
        self._xmon.place(ax, xy, angle, color=color_body)

        # 2) DC SQUID: legs extend outward from the arm tip
        squid_local = self._arm_endpoint(squid_angle)
        squid_global_angle = angle + squid_angle
        rad_g = np.radians(angle)
        rot = np.array([[np.cos(rad_g), -np.sin(rad_g)],
                        [np.sin(rad_g),  np.cos(rad_g)]])
        squid_pos = rot @ squid_local + np.array(xy)
        self._squid.place(ax, tuple(squid_pos), squid_global_angle, color=color_squid)

        # 3) Resonator near the resonator arm tip, rotated 180° around its own centre
        #    so the meander body sits beyond the pad (not overlapping the arm).
        res_local = self._arm_endpoint(res_angle)
        res_dir = res_local / np.linalg.norm(res_local)
        res_gap = 10  # clearance between pad edge and resonator start
        res_origin_local = res_local + res_dir * res_gap

        # The resonator's local geometry starts at (0,0) along +x.
        # Rotating 180° around its bounding-box centre C maps origin → 2C.
        # So we place at: (arm_tip + gap) + R_arm * (2*C), angle + arm + 180
        res_C = self._resonator.center()
        res_arm_rad = np.radians(res_angle)
        rot_arm = np.array([[np.cos(res_arm_rad), -np.sin(res_arm_rad)],
                            [np.sin(res_arm_rad),  np.cos(res_arm_rad)]])
        shifted_origin = res_origin_local + rot_arm @ (2.0 * res_C)
        res_pos = rot @ shifted_origin + np.array(xy)
        res_global_angle = angle + res_angle + 180
        self._resonator.place(ax, tuple(res_pos), res_global_angle, color=color_resonator)

        # 4) Flux feed line beyond the SQUID legs
        #    The flux line starts at the arm tip and its standoff accounts
        #    for the leg length, so we pass the arm tip position.
        self._flux_line.place(ax, tuple(squid_pos), squid_global_angle,
                              squid_dims=self.dims.dc_squid)
