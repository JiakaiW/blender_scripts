"""
3D Blender components that mirror ``visualization/qubits.py``.

Each component reads dimension dataclasses from ``visualization.styles``
and produces Blender geometry with realistic Dolan-bridge junctions.
All single-layer elements use the same height ``LAYER_H``.
"""

import bpy
import math
import numpy as np

from .primitives import (
    create_cuboid,
    create_dolan_bridge,
    create_half_bridge,
    create_extruded_path,
    get_material,
)


# ── helpers ─────────────────────────────────────────────────────────────

def _rad(deg):
    return math.radians(deg)


def _rot2d(x, y, rad):
    """Rotate 2D point around origin."""
    c, s = math.cos(rad), math.sin(rad)
    return x * c - y * s, x * s + y * c


def _rot2d_vec(v, rad):
    """Rotate 2D vector/point."""
    return np.array(_rot2d(v[0], v[1], rad))


# ── height / thickness constants (data-unit Z scale) ───────────────────

LAYER_H        = 3    # Z thickness of each deposited Al layer (exaggerated for 3D visibility)
BRIDGE_W_FRAC  = 1.0   # bridge width = this × island width
SIGMOID_STEEP  = 2    # sigmoid steepness for bridge profile
SUBSTRATE_DROP = 2.0   # how far below z=0 the substrate top sits

# Back-compat aliases
ISLAND_HEIGHT  = LAYER_H
PAD_HEIGHT     = LAYER_H


# ═══════════════════════════════════════════════════════════════════════
#  XMON 3D  (four-armed cross + pads)
# ═══════════════════════════════════════════════════════════════════════

class Xmon3D:
    """
    3D Xmon cross: four arms + pads, single-layer cuboids at height h.

    Mirrors ``visualization.primitives.Xmon`` geometry exactly.
    """

    def __init__(self, dims, material=None):
        self.dims = dims
        self.mat = material or get_material("aluminum")

        # Resolve per-arm lengths (same logic as 2D Xmon)
        default_len = getattr(dims, "arm_len", None)
        long_len = getattr(dims, "long_arm_len", None)
        short_len = getattr(dims, "short_arm_len", None)

        if long_len is not None:
            self._arm_lengths = {0: long_len, 180: long_len,
                                 90: short_len, 270: short_len}
        else:
            self._arm_lengths = {a: default_len for a in (0, 90, 180, 270)}

    def arm_tip(self, angle_deg: int) -> np.ndarray:
        """Local (x,y) at the outer edge of the pad for arm *angle_deg*."""
        arm_l = self._arm_lengths[angle_deg]
        pad_w = self.dims.pad_head_size / 1.5
        dist = self.dims.arm_width / 2 + arm_l + pad_w
        rad = np.radians(angle_deg)
        return np.array([dist * np.cos(rad), dist * np.sin(rad)])

    def place(self, location=(0, 0, 0), angle_deg=0.0, name_prefix="Xmon"):
        lx, ly, lz = location
        rot = _rad(angle_deg)
        h = LAYER_H
        aw = self.dims.arm_width
        c = aw / 2
        pad_h = self.dims.pad_head_size

        # Centre square
        create_cuboid(
            (lx, ly, lz + h / 2), (c, c, h / 2),
            name=f"{name_prefix}_Center", material=self.mat,
            rotation_euler=(0, 0, rot),
        )

        for angle in (0, 90, 180, 270):
            arm_l = self._arm_lengths[angle]
            total_angle = rot + _rad(angle)

            # Arm: starts at distance c from centre, length arm_l
            arm_cx_local = c + arm_l / 2
            ax_, ay_ = _rot2d(arm_cx_local, 0, total_angle)
            create_cuboid(
                (lx + ax_, ly + ay_, lz + h / 2),
                (arm_l / 2, c, h / 2),
                name=f"{name_prefix}_Arm{angle}",
                material=self.mat,
                rotation_euler=(0, 0, total_angle),
            )

            # Pad at tip
            pad_w = pad_h / 1.5
            pad_cx_local = c + arm_l + pad_w / 2
            px, py = _rot2d(pad_cx_local, 0, total_angle)
            create_cuboid(
                (lx + px, ly + py, lz + h / 2),
                (pad_w / 2, pad_h / 2, h / 2),
                name=f"{name_prefix}_Pad{angle}",
                material=self.mat,
                rotation_euler=(0, 0, total_angle),
            )


# ═══════════════════════════════════════════════════════════════════════
#  DC SQUID 3D  (two legs + U-bar + two JJ rectangles)
# ═══════════════════════════════════════════════════════════════════════

class DCSqUID3D:
    """3D DC-SQUID: two parallel legs, U-bar, and two JJ rectangles."""

    def __init__(self, dims, mat_leg=None, mat_jj=None):
        self.dims = dims
        self.mat_leg = mat_leg or get_material("coupler")
        self.mat_jj = mat_jj or get_material("junction")

    def place(self, location=(0, 0, 0), angle_deg=0.0, name_prefix="SQUID"):
        d = self.dims
        lx, ly, lz = location
        rot = _rad(angle_deg)
        h = LAYER_H
        half_sep = d.leg_separation / 2

        # Single-JJ per leg: island bar (Layer 1) extends past midpoint,
        # half-bridge (Layer 2, single wing) overlaps from the other side.
        # Same pattern as the fluxonium connector piece.
        jj_overlap = 1.5
        mid_x = d.leg_length / 2

        for sign, tag in ((-1, "Bot"), (1, "Top")):
            cy_l = sign * half_sep

            # Island (Layer 1): from x=0 to x = mid_x + overlap
            island_len = mid_x + jj_overlap
            island_cx = island_len / 2
            i_gx, i_gy = _rot2d(island_cx, cy_l, rot)
            create_cuboid(
                (lx + i_gx, ly + i_gy, lz + h / 2),
                (island_len / 2, d.leg_width / 2, h / 2),
                name=f"{name_prefix}_Leg{tag}_Island",
                material=self.mat_leg,
                rotation_euler=(0, 0, rot),
            )

            # Half-bridge (Layer 2): from x = leg_length down to mid_x,
            # wing overlaps the island at the mid_x end
            hb_len = d.leg_length - mid_x
            hb_cx = mid_x + hb_len / 2
            hb_gx, hb_gy = _rot2d(hb_cx, cy_l, rot)
            # half_bridge local +X direction: we need the wing pointing
            # toward -X (toward the island). Rotate 180° so the sigmoid
            # wing faces the island overlap region.
            create_half_bridge(
                (lx + hb_gx, ly + hb_gy, lz),
                total_length=hb_len,
                width=d.leg_width * BRIDGE_W_FRAC,
                h_step=h - 0.05,  # penetrate into island to avoid z-fighting
                thickness=h,
                overlap_len=jj_overlap,
                name=f"{name_prefix}_JJ_{tag}",
                material=get_material("aluminum2"),
                steepness=SIGMOID_STEEP,
                rotation_euler=(0, 0, rot + math.pi),
            )

        # U-bar at x = leg_length
        ub_cx_l = d.leg_length
        ub_cx, ub_cy = _rot2d(ub_cx_l, 0, rot)
        create_cuboid(
            (lx + ub_cx, ly + ub_cy, lz + h / 2),
            (d.u_bar_width / 2, half_sep + d.leg_width / 2, h / 2),
            name=f"{name_prefix}_UBar",
            material=self.mat_leg,
            rotation_euler=(0, 0, rot),
        )


# ═══════════════════════════════════════════════════════════════════════
#  RESONATOR 3D  (meander made of cuboid segments)
# ═══════════════════════════════════════════════════════════════════════

class Resonator3D:
    """
    3D readout resonator that mirrors the 2D meander centreline.

    Instead of a ribbon polygon, we extrude the centreline into a
    series of short cuboid segments with the correct width and LAYER_H
    thickness.
    """

    _ARC_PTS = 30

    def __init__(self, dims, material=None):
        self.dims = dims
        self.mat = material or get_material("aluminum")

    def _build_centreline(self) -> np.ndarray:
        """Same meander path as ``visualization.primitives.Resonator``."""
        d = self.dims
        R = d.turn_radius
        A = d.meander_amplitude
        n = self._ARC_PTS
        points = []

        points.append((0.0, 0.0))
        x = d.lead_length
        points.append((x, 0.0))

        cx_q, cy_q = x, -R
        for i in range(1, n + 1):
            theta = (np.pi / 2) * (1 - i / n)
            points.append((cx_q + R * np.cos(theta), cy_q + R * np.sin(theta)))
        x += R
        y = -R

        first_drop = A / 2 - R
        if first_drop > 0:
            y = -A / 2
            points.append((x, y))

        at_bottom = True
        for _ in range(d.num_turns):
            if at_bottom:
                cx, cy = x + R, -A / 2
                for i in range(1, n + 1):
                    theta = np.pi + np.pi * i / n
                    points.append((cx + R * np.cos(theta), cy + R * np.sin(theta)))
                x += 2 * R
                points.append((x, A / 2))
                at_bottom = False
            else:
                cx, cy = x + R, A / 2
                for i in range(1, n + 1):
                    theta = np.pi - np.pi * i / n
                    points.append((cx + R * np.cos(theta), cy + R * np.sin(theta)))
                x += 2 * R
                points.append((x, -A / 2))
                at_bottom = True

        return np.array(points)

    def center(self) -> np.ndarray:
        pts = self._build_centreline()
        return np.array([(pts[:, 0].min() + pts[:, 0].max()) / 2,
                         (pts[:, 1].min() + pts[:, 1].max()) / 2])

    def place(self, location=(0, 0, 0), angle_deg=0.0, name_prefix="Res"):
        """Extrude the meander centreline as a single smooth curve object."""
        pts = self._build_centreline()
        lx, ly, lz = location
        rot = _rad(angle_deg)
        h = LAYER_H
        w = self.dims.width * 2  # full width (dims.width is half-width)

        # Rotate all centreline points into global frame
        rotated_pts = [_rot2d(p[0], p[1], rot) for p in pts]

        create_extruded_path(
            rotated_pts,
            width=w,
            height=h,
            location=(lx, ly, lz + h / 2),
            name=f"{name_prefix}_Meander",
            material=self.mat,
        )


# ═══════════════════════════════════════════════════════════════════════
#  FLUX LINE 3D  (simple feed line rectangle)
# ═══════════════════════════════════════════════════════════════════════

class FluxLine3D:
    """A flux bias feed line — one cuboid rectangle."""

    def __init__(self, dims, material=None):
        self.dims = dims
        self.mat = material or get_material("coupler")

    def place(self, location=(0, 0, 0), angle_deg=0.0,
              squid_dims=None, name_prefix="Flux"):
        d = self.dims
        lx, ly, lz = location
        rot = _rad(angle_deg)
        h = LAYER_H

        squid_half = squid_dims.leg_length if squid_dims else 40
        start_offset = squid_half + d.standoff

        cx_l = start_offset + d.length / 2
        cx, cy = _rot2d(cx_l, 0, rot)
        hw = d.width  # half-width

        create_cuboid(
            (lx + cx, ly + cy, lz + h / 2),
            (d.length / 2, hw, h / 2),
            name=f"{name_prefix}_Line",
            material=self.mat,
            rotation_euler=(0, 0, rot),
        )


# ═══════════════════════════════════════════════════════════════════════
#  JJ CHAIN 3D  (array of islands connected by Dolan bridges)
# ═══════════════════════════════════════════════════════════════════════

class JJChain3D:
    """
    A linear Josephson-junction chain rendered with realistic
    Dolan-bridge geometry.

    Each unit cell:
      1. **Bottom island** — thick aluminum cuboid (Layer 1).
      2. **Bridge** — narrow sigmoid-profiled strip (Layer 2) that
         climbs up from the substrate, overlaps the next island,
         dips into the gap, and overlaps the previous island.

    Parameters
    ----------
    dims : JJChainDims
        ``length``, ``width``, ``island_len``, ``gap``, ``overlap``.
    """

    def __init__(self, dims):
        self.dims = dims
        self.mat_island = get_material("aluminum")
        self.mat_bridge = get_material("aluminum2")

    def place(self, location=(0, 0, 0), angle_deg=0.0, name_prefix="JJ"):
        """
        Build the chain at *location* (x, y, z) rotated by *angle_deg*
        around Z.  The chain extends along the local +X direction.
        """
        d = self.dims
        unit = d.island_len + d.gap
        n_cells = int(d.length / unit)
        total_len = n_cells * unit + d.island_len

        lx, ly, lz = location
        rot_z = _rad(angle_deg)
        h = LAYER_H

        # ── islands (layer 1) ──
        x_cursor = 0.0
        for i in range(n_cells + 1):
            cx_local = x_cursor + d.island_len / 2
            cx, cy = _rot2d(cx_local, 0, rot_z)

            create_cuboid(
                (lx + cx, ly + cy, lz + h / 2),
                (d.island_len / 2, d.width / 2, h / 2),
                name=f"{name_prefix}_Island_{i}",
                material=self.mat_island,
                rotation_euler=(0, 0, rot_z),
            )
            x_cursor += unit

        # ── bridges (layer 2): same thickness h ────────────────────────
        bridge_w = d.width * BRIDGE_W_FRAC
        x_cursor = 0.0
        for i in range(n_cells):
            bridge_len = d.gap + 2 * d.overlap
            gap_centre_x = x_cursor + d.island_len + d.gap / 2
            bx, by = _rot2d(gap_centre_x, 0, rot_z)

            create_dolan_bridge(
                (lx + bx, ly + by, lz),
                total_length=bridge_len,
                width=bridge_w,
                h_step=h - 0.05,  # penetrate into island to avoid z-fighting
                thickness=h,
                overlap_len=d.overlap,
                name=f"{name_prefix}_Bridge_{i}",
                material=self.mat_bridge,
                steepness=SIGMOID_STEEP,
                rotation_euler=(0, 0, rot_z),
            )

            x_cursor += unit

        return total_len


# ═══════════════════════════════════════════════════════════════════════
#  FLUXONIUM 3D  (Xmon + two JJ chains + connector bar + phase-slip JJ)
# ═══════════════════════════════════════════════════════════════════════

class Fluxonium3D:
    """
    3D fluxonium data qubit — mirrors ``visualization.qubits.FluxoniumQubit``.

    Composed of:
      - Xmon cross (single layer)
      - Two parallel JJ chains at ``chain_angle`` (multi-layer)
      - Connector bar at far end (single layer)
      - Phase-slip JJ marker (single layer)
    """

    def __init__(self, dims=None):
        from visualization.styles import FluxoniumDims
        if dims is None:
            dims = FluxoniumDims()
        self.dims = dims
        self._xmon = Xmon3D(dims.xmon)
        self._chain = JJChain3D(dims.chain)

    def place(self, location=(0, 0, 0), angle_deg=0.0, name_prefix="Flux"):
        d = self.dims
        lx, ly, lz = location
        rot = _rad(angle_deg)
        h = LAYER_H

        # 1. Xmon body
        self._xmon.place(location, angle_deg, name_prefix=f"{name_prefix}_Xmon")

        # 2. JJ chains
        chain_global_angle = angle_deg + d.chain_angle
        chain_rad = _rad(chain_global_angle)
        vec_fwd = np.array([math.cos(chain_rad), math.sin(chain_rad)])
        vec_perp = np.array([-math.sin(chain_rad), math.cos(chain_rad)])

        origin = np.array([lx, ly])
        center_start = origin + vec_fwd * d.chain_start_dist

        start_A = center_start + vec_perp * (d.chain_separation / 2)
        start_B = center_start - vec_perp * (d.chain_separation / 2)

        total_len = self._chain.place(
            (*start_A, lz), chain_global_angle,
            name_prefix=f"{name_prefix}_ChainA",
        )
        self._chain.place(
            (*start_B, lz), chain_global_angle,
            name_prefix=f"{name_prefix}_ChainB",
        )

        # 3. Connector at far end: island bar (Layer 1) + half-bridge JJ (Layer 2)
        #    Same pattern as test_jj_chain_3d.py dual-chain connector.
        end_A = start_A + vec_fwd * total_len
        end_B = start_B + vec_fwd * total_len
        bar_center = (end_A + end_B) / 2
        bar_len = d.chain_separation + d.connector_bar_extra
        bar_h = d.connector_bar_height

        bar_angle = chain_global_angle + 90
        bar_rad = _rad(bar_angle)
        bar_unit = np.array([math.cos(bar_rad), math.sin(bar_rad)])
        overlap = d.chain.overlap

        # Island bar (Layer 1): from A-end past centre by overlap
        island_len = bar_len / 2 + overlap
        island_center = bar_center + bar_unit * (bar_len / 4 - overlap / 2)
        create_cuboid(
            (*island_center, lz + h / 2),
            (island_len / 2, bar_h / 2, h / 2),
            name=f"{name_prefix}_ConnIsland",
            material=get_material("aluminum"),
            rotation_euler=(0, 0, bar_rad),
        )

        # Half-bridge (Layer 2): from B-end toward centre, wing overlaps island
        hb_len = bar_len / 2
        hb_center = bar_center - bar_unit * bar_len / 4
        bridge_w = bar_h * BRIDGE_W_FRAC
        create_half_bridge(
            (*hb_center, lz),
            total_length=hb_len,
            width=bridge_w,
            h_step=h - 0.05,  # penetrate into island to avoid z-fighting
            thickness=h,
            overlap_len=overlap,
            name=f"{name_prefix}_ConnBridge",
            material=get_material("aluminum2"),
            steepness=SIGMOID_STEEP,
            rotation_euler=(0, 0, bar_rad),
        )


# ═══════════════════════════════════════════════════════════════════════
#  TUNABLE TRANSMON COUPLER 3D
# ═══════════════════════════════════════════════════════════════════════

class Coupler3D:
    """
    3D tunable-transmon coupler — mirrors
    ``visualization.qubits.TunableTransmonCoupler``.

    Composed of:
      - Asymmetric Xmon cross (single layer)
      - DC SQUID on one short arm
      - Readout resonator on the other short arm
      - Flux feed line beyond the SQUID
    """

    _SHORT_ARM_ANGLES = {0: 90, 1: 270}

    def __init__(self, dims=None):
        from visualization.styles import TunableTransmonDims
        if dims is None:
            dims = TunableTransmonDims()
        self.dims = dims
        self._xmon = Xmon3D(dims.xmon, material=get_material("coupler"))
        self._squid = DCSqUID3D(dims.dc_squid)
        self._resonator = Resonator3D(dims.resonator)
        self._flux_line = FluxLine3D(dims.flux_line)

        self._squid_angle = self._SHORT_ARM_ANGLES[dims.squid_arm_index]
        self._res_angle = self._SHORT_ARM_ANGLES[dims.resonator_arm_index]

    def place(self, location=(0, 0, 0), angle_deg=0.0,
              mirror=False, name_prefix="Coupler"):
        d = self.dims
        lx, ly, lz = location
        rot = _rad(angle_deg)

        if mirror:
            squid_angle = self._res_angle
            res_angle = self._squid_angle
        else:
            squid_angle = self._squid_angle
            res_angle = self._res_angle

        # 1. Xmon body
        self._xmon.place(location, angle_deg, name_prefix=f"{name_prefix}_Xmon")

        # 2. DC SQUID at squid-arm tip
        squid_local = self._xmon.arm_tip(squid_angle)
        squid_global_angle = angle_deg + squid_angle
        gx, gy = _rot2d(squid_local[0], squid_local[1], rot)
        self._squid.place(
            (lx + gx, ly + gy, lz), squid_global_angle,
            name_prefix=f"{name_prefix}_SQUID",
        )

        # 3. Resonator near the resonator arm tip
        res_local = self._xmon.arm_tip(res_angle)
        res_dir = res_local / np.linalg.norm(res_local)
        res_gap = 10
        res_origin_local = res_local + res_dir * res_gap

        res_C = self._resonator.center()
        res_arm_rad = _rad(res_angle)
        rot_arm = np.array([[math.cos(res_arm_rad), -math.sin(res_arm_rad)],
                            [math.sin(res_arm_rad),  math.cos(res_arm_rad)]])
        shifted_origin = res_origin_local + rot_arm @ (2.0 * res_C)
        rx, ry = _rot2d(shifted_origin[0], shifted_origin[1], rot)
        res_global_angle = angle_deg + res_angle + 180

        self._resonator.place(
            (lx + rx, ly + ry, lz), res_global_angle,
            name_prefix=f"{name_prefix}_Res",
        )

        # 4. Flux feed line beyond SQUID
        self._flux_line.place(
            (lx + gx, ly + gy, lz), squid_global_angle,
            squid_dims=d.dc_squid,
            name_prefix=f"{name_prefix}_Flux",
        )
