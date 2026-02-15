"""
Low-level geometric building blocks for superconducting chip visualization.

Every primitive stores its geometry in local coordinates (centered at origin)
and exposes a `.place(ax, xy, angle, **style)` method that stamps a copy onto
a matplotlib Axes with the requested global position & rotation.
"""

from __future__ import annotations

import numpy as np
import matplotlib.patches as patches
import matplotlib.path as mpath
import matplotlib.transforms as transforms
from matplotlib.axes import Axes
from typing import List, Tuple

from .styles import (
    XmonDims, CouplerXmonDims, JJChainDims, DCSqUIDDims, ResonatorDims,
    FluxLineDims,
    DEFAULT_PALETTE,
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _stamp_rect(
    ax: Axes,
    xy: Tuple[float, float],
    w: float,
    h: float,
    local_angle: float,
    base_transform,
    **kwargs,
) -> patches.Rectangle:
    """Create a Rectangle, compose its local rotation with *base_transform*, add to *ax*."""
    r = patches.Rectangle(xy, w, h, **kwargs)
    final = transforms.Affine2D().rotate_deg(local_angle) + base_transform
    r.set_transform(final)
    ax.add_patch(r)
    return r


# ═══════════════════════════════════════════════════════════════════════════
#  XMON  (cross + pads)
# ═══════════════════════════════════════════════════════════════════════════
class Xmon:
    """
    A four-armed cross capacitor with rectangular pads at each tip.

    Supports asymmetric arms: pass *arm_lengths* as a dict keyed by
    cardinal direction ``{0: L_right, 90: L_up, 180: L_left, 270: L_down}``
    to override the uniform *arm_len*.

    Parameters
    ----------
    dims : XmonDims | CouplerXmonDims
        Basic dimensions (arm_len / long/short, arm_width, pad_head_size).
    arm_lengths : dict[int, float] | None
        Per-arm overrides, keyed by angle (0, 90, 180, 270).
    """

    def __init__(
        self,
        dims: XmonDims | CouplerXmonDims | None = None,
        arm_lengths: dict[int, float] | None = None,
    ):
        if dims is None:
            dims = XmonDims()
        self.dims = dims
        self.arm_width = dims.arm_width
        self.pad_head_size = dims.pad_head_size

        # Resolve per-arm lengths
        default_len = getattr(dims, "arm_len", None)  # XmonDims
        long_len = getattr(dims, "long_arm_len", None)  # CouplerXmonDims
        short_len = getattr(dims, "short_arm_len", None)

        if arm_lengths is not None:
            self._arm_lengths = dict(arm_lengths)
        elif long_len is not None:
            # Coupler pattern: 0/180 = long, 90/270 = short (rotated by caller)
            self._arm_lengths = {0: long_len, 180: long_len, 90: short_len, 270: short_len}
        else:
            self._arm_lengths = {a: default_len for a in (0, 90, 180, 270)}

        self._patches: List[Tuple[Tuple, float]] = []  # ((x,y,w,h), local_angle)
        self._generate()

    # ── geometry ────────────────────────────────────────────────────────
    def _generate(self):
        c = self.arm_width / 2
        # center square
        self._patches.append(((-c, -c, self.arm_width, self.arm_width), 0))

        for angle in (0, 90, 180, 270):
            arm_l = self._arm_lengths[angle]
            # arm
            self._patches.append(((c, -c, arm_l, self.arm_width), angle))
            # pad at tip
            pad_x = c + arm_l
            pad_w = self.pad_head_size / 1.5
            pad_h = self.pad_head_size
            self._patches.append(((pad_x, -pad_h / 2, pad_w, pad_h), angle))

    # ── anchor points (local coords) ───────────────────────────────────
    def arm_tip(self, angle_deg: int) -> np.ndarray:
        """Return the (x, y) position of an arm tip in local coordinates."""
        arm_l = self._arm_lengths[angle_deg]
        pad_w = self.pad_head_size / 1.5
        dist = self.arm_width / 2 + arm_l + pad_w
        rad = np.radians(angle_deg)
        return np.array([dist * np.cos(rad), dist * np.sin(rad)])

    # ── drawing ─────────────────────────────────────────────────────────
    def place(self, ax: Axes, xy=(0, 0), angle: float = 0, color=None):
        if color is None:
            color = DEFAULT_PALETTE.xmon_body
        base = (
            transforms.Affine2D().rotate_deg(angle).translate(xy[0], xy[1])
            + ax.transData
        )
        for (rect_args, local_angle) in self._patches:
            _stamp_rect(
                ax, (rect_args[0], rect_args[1]), rect_args[2], rect_args[3],
                local_angle, base, facecolor=color, edgecolor=None,
            )


# ═══════════════════════════════════════════════════════════════════════════
#  JJ CHAIN  (array of superconducting islands linked by Josephson bridges)
# ═══════════════════════════════════════════════════════════════════════════
class JJChain:
    """
    A linear Josephson-junction chain (superinductance element).

    Geometry is built along the +x axis starting at x=0, centred on y=0.
    """

    def __init__(self, dims: JJChainDims | None = None):
        if dims is None:
            dims = JJChainDims()
        self.dims = dims
        self._islands: List[Tuple] = []
        self._bridges: List[Tuple] = []
        self.total_length: float = 0
        self._generate()

    def _generate(self):
        d = self.dims
        unit = d.island_len + d.gap
        n_cells = int(d.length / unit)
        bridge_len = d.gap + 2 * d.overlap
        x = 0.0
        for i in range(n_cells + 1):
            self._islands.append((x, -d.width / 2, d.island_len, d.width))
            if i < n_cells:
                bx = x + d.island_len - d.overlap
                bw = d.width * 0.85
                self._bridges.append((bx, -bw / 2, bridge_len, bw))
            x += unit
        self.total_length = x - unit + d.island_len

    def place(
        self, ax: Axes, xy=(0, 0), angle: float = 0,
        color_island=None, color_bridge=None,
    ):
        if color_island is None:
            color_island = DEFAULT_PALETTE.jj_chain_island
        if color_bridge is None:
            color_bridge = DEFAULT_PALETTE.jj_chain_bridge

        base = (
            transforms.Affine2D().rotate_deg(angle).translate(xy[0], xy[1])
            + ax.transData
        )
        for r in self._islands:
            _stamp_rect(ax, (r[0], r[1]), r[2], r[3], 0, base,
                        facecolor=color_island, edgecolor=None)
        for r in self._bridges:
            _stamp_rect(ax, (r[0], r[1]), r[2], r[3], 0, base,
                        facecolor=color_bridge, edgecolor=None, alpha=0.9)


# ═══════════════════════════════════════════════════════════════════════════
#  JOSEPHSON JUNCTION  (single JJ marker)
# ═══════════════════════════════════════════════════════════════════════════
class JosephsonJunction:
    """A single Josephson junction drawn as a small filled rectangle."""

    def __init__(self, width: float = 10, height: float = 16):
        self.width = width
        self.height = height

    def place(self, ax: Axes, xy=(0, 0), angle: float = 0, color=None, **kw):
        if color is None:
            color = DEFAULT_PALETTE.junction
        base = (
            transforms.Affine2D().rotate_deg(angle).translate(xy[0], xy[1])
            + ax.transData
        )
        _stamp_rect(
            ax, (-self.width / 2, -self.height / 2), self.width, self.height,
            0, base, facecolor=color, edgecolor=None, zorder=kw.get("zorder", 10),
        )


# ═══════════════════════════════════════════════════════════════════════════
#  DC SQUID  (two parallel legs + U-bar connector + two JJs)
# ═══════════════════════════════════════════════════════════════════════════
class DCSqUID:
    """
    DC-SQUID drawn as two parallel thin bars ("legs") extending outward
    from the Xmon arm pad, connected at their far end by a U-shaped bar.
    Two small rectangles at each leg-to-U-bar junction represent the
    Josephson junctions.

    Local geometry (before global rotation):
      - Legs run along +x starting at x=0, separated by ±leg_separation/2
        in the y direction.
      - The U-bar connects the two leg ends at x = leg_length.
      - JJ rectangles sit at (leg_length, ±leg_separation/2).
    """

    def __init__(self, dims: DCSqUIDDims | None = None):
        if dims is None:
            dims = DCSqUIDDims()
        self.dims = dims

    def place(self, ax: Axes, xy=(0, 0), angle: float = 0, color=None):
        """Draw the SQUID.  *color* controls the JJ rectangles."""
        if color is None:
            color = DEFAULT_PALETTE.dc_squid_body
        leg_color = DEFAULT_PALETTE.squid_leg

        base = (
            transforms.Affine2D().rotate_deg(angle).translate(xy[0], xy[1])
            + ax.transData
        )
        d = self.dims
        half_sep = d.leg_separation / 2
        hw = d.leg_width / 2  # half-width of each leg

        # ── two parallel legs (filled rectangles along +x) ─────────────
        for sign in (-1, 1):
            cy = sign * half_sep
            _stamp_rect(
                ax, (0, cy - hw), d.leg_length, d.leg_width,
                0, base, facecolor=leg_color, edgecolor=None,
            )

        # ── U-bar connecting the far ends of the two legs ──────────────
        u_hw = d.u_bar_width / 2
        _stamp_rect(
            ax, (d.leg_length - u_hw, -half_sep),
            d.u_bar_width, d.leg_separation,
            0, base, facecolor=leg_color, edgecolor=None,
        )

        # ── two JJ rectangles at the midpoint of each leg ─────────────
        for sign in (-1, 1):
            jj_x = d.leg_length / 2 - d.junction_width / 2
            jj_y = sign * half_sep - d.junction_height / 2
            _stamp_rect(
                ax, (jj_x, jj_y), d.junction_width, d.junction_height,
                0, base, facecolor=color, edgecolor=None, zorder=10,
            )


# ═══════════════════════════════════════════════════════════════════════════
#  RESONATOR  (meander with semicircular U-turns)
# ═══════════════════════════════════════════════════════════════════════════
class Resonator:
    """
    A readout resonator drawn as a meandering CPW stub with semicircular
    U-turns.

    Pattern (local coords, starting at origin along +x):
        1. Straight lead-in
        2. Quarter-circle right turn (+x → −y)
        3. Straight down for half the meander amplitude
        4. Semicircular U-turn (bottom) → now heading +y
        5. Straight up for full amplitude
        6. Semicircular U-turn (top) → now heading −y
        7. Repeat 5-6 for remaining turns
    """

    _ARC_PTS = 30  # points per semicircular arc

    def __init__(self, dims: ResonatorDims | None = None):
        if dims is None:
            dims = ResonatorDims()
        self.dims = dims

    def _build_meander_path(self) -> np.ndarray:
        d = self.dims
        R = d.turn_radius
        A = d.meander_amplitude
        n = self._ARC_PTS
        points: list = []

        # 1) Lead-in straight along +x
        points.append((0.0, 0.0))
        x = d.lead_length
        points.append((x, 0.0))

        # 2) Quarter-circle: +x → −y  (right turn)
        #    centre at (x, −R), sweep from π/2 → 0
        cx_q, cy_q = x, -R
        for i in range(1, n + 1):
            theta = (np.pi / 2) * (1 - i / n)
            points.append((cx_q + R * np.cos(theta),
                           cy_q + R * np.sin(theta)))
        x += R
        y = -R

        # 3) First straight down: remaining A/2 − R
        first_drop = A / 2 - R
        if first_drop > 0:
            y = -A / 2
            points.append((x, y))
        else:
            y = -R  # quarter-circle already reached or passed -A/2

        # 4-7) Alternating U-turns and straight segments
        at_bottom = True  # we are at y = −A/2
        for _ in range(d.num_turns):
            if at_bottom:
                # Bottom U-turn at y = −A/2, sweep π → 2π (dips downward)
                cx, cy = x + R, -A / 2
                for i in range(1, n + 1):
                    theta = np.pi + np.pi * i / n
                    points.append((cx + R * np.cos(theta),
                                   cy + R * np.sin(theta)))
                x += 2 * R
                # Straight up to +A/2
                points.append((x, A / 2))
                at_bottom = False
            else:
                # Top U-turn at y = +A/2, sweep π → 0 (bulges upward)
                cx, cy = x + R, A / 2
                for i in range(1, n + 1):
                    theta = np.pi - np.pi * i / n
                    points.append((cx + R * np.cos(theta),
                                   cy + R * np.sin(theta)))
                x += 2 * R
                # Straight down to −A/2
                points.append((x, -A / 2))
                at_bottom = True

        return np.array(points)

    def center(self) -> np.ndarray:
        """Bounding-box centre of the meander path in local coordinates."""
        pts = self._build_meander_path()
        return np.array([(pts[:, 0].min() + pts[:, 0].max()) / 2,
                         (pts[:, 1].min() + pts[:, 1].max()) / 2])

    def place(self, ax: Axes, xy=(0, 0), angle: float = 0, color=None):
        if color is None:
            color = DEFAULT_PALETTE.resonator
        base = (
            transforms.Affine2D().rotate_deg(angle).translate(xy[0], xy[1])
            + ax.transData
        )
        centreline = self._build_meander_path()
        hw = self.dims.width  # half-width in data units

        # Add a tiny extension at the last point so the ribbon ends flat
        end_tang = centreline[-1] - centreline[-2]
        end_tang = end_tang / np.linalg.norm(end_tang)
        centreline = np.vstack([centreline, centreline[-1] + end_tang * 0.01])

        n = len(centreline)
        # Compute tangent vectors at each point
        tangents = np.zeros_like(centreline)
        tangents[0] = centreline[1] - centreline[0]
        tangents[-1] = centreline[-1] - centreline[-2]
        tangents[1:-1] = centreline[2:] - centreline[:-2]
        lengths = np.linalg.norm(tangents, axis=1, keepdims=True)
        lengths[lengths == 0] = 1
        tangents /= lengths
        # Normals (rotate tangent 90° CCW)
        normals = np.column_stack([-tangents[:, 1], tangents[:, 0]])

        left = centreline + normals * hw
        right = centreline - normals * hw

        ribbon = np.concatenate([left, right[::-1]], axis=0)
        codes = [mpath.Path.MOVETO] + [mpath.Path.LINETO] * (len(ribbon) - 2) + [mpath.Path.CLOSEPOLY]
        path = mpath.Path(ribbon, codes)
        pp = patches.PathPatch(
            path, facecolor=color, edgecolor=None,
        )
        pp.set_transform(base)
        ax.add_patch(pp)


# ═══════════════════════════════════════════════════════════════════════════
#  FLUX FEED LINE  (simple T-shaped bias line near the SQUID)
# ═══════════════════════════════════════════════════════════════════════════
class FluxLine:
    """
    A flux bias feed line drawn near the SQUID loop.

    Placed relative to the SQUID centre: the line runs perpendicular to the
    SQUID arm starting from a small standoff.
    """

    def __init__(self, dims: FluxLineDims | None = None):
        if dims is None:
            dims = FluxLineDims()
        self.dims = dims

    def place(self, ax: Axes, xy=(0, 0), angle: float = 0,
              color=None, squid_dims: DCSqUIDDims | None = None):
        """
        Draw the flux line.  *xy* and *angle* should match the SQUID's
        placement so the line sits beside its loop.
        """
        if color is None:
            color = DEFAULT_PALETTE.flux_line
        d = self.dims

        # Position the line to the side of the SQUID loop
        squid_half = (squid_dims.leg_length
                      if squid_dims else 40)
        start_offset = squid_half + d.standoff

        base = (
            transforms.Affine2D().rotate_deg(angle).translate(xy[0], xy[1])
            + ax.transData
        )

        # Main feed line as a filled rectangle (data coordinates)
        hw = d.width  # half-width
        _stamp_rect(
            ax, (start_offset, -hw), d.length, 2 * hw,
            0, base, facecolor=color, edgecolor=None,
        )
