"""
Square-lattice layout engine.

Places **data qubits** (fluxonium) on lattice sites and **couplers**
(tunable transmons) on lattice edges, computing positions and orientations
automatically from a ``LatticeConfig``.
"""

from __future__ import annotations

import numpy as np
import matplotlib.patches as patches
from matplotlib.axes import Axes
from typing import Tuple, Dict, List, Optional

from .styles import LatticeConfig, FluxoniumDims, TunableTransmonDims, DEFAULT_PALETTE
from .qubits import FluxoniumQubit, TunableTransmonCoupler


# ── small helpers ───────────────────────────────────────────────────────────

def _edge_angle(direction: str) -> float:
    """Return the global rotation of a coupler for a given lattice edge direction."""
    # Long arms of the coupler point at the two data qubits it connects.
    # For a horizontal edge: long arms point 0° and 180° → coupler angle = 0
    # For a vertical edge:   long arms point 90° and 270° → coupler angle = 90
    return {"horizontal": 0, "vertical": 90}[direction]


# ═══════════════════════════════════════════════════════════════════════════
#  SQUARE LATTICE
# ═══════════════════════════════════════════════════════════════════════════
class SquareLattice:
    """
    A rows × cols square lattice of fluxonium data qubits with tunable-
    transmon couplers on every interior edge.

    The lattice coordinate system has (0, 0) at the bottom-left qubit,
    +x pointing right, +y pointing up.

    Parameters
    ----------
    config : LatticeConfig
        rows, cols, pitch.
    fluxonium_dims : FluxoniumDims | None
        Dimension override for data qubits.
    coupler_dims : TunableTransmonDims | None
        Dimension override for couplers.
    """

    def __init__(
        self,
        config: LatticeConfig | None = None,
        fluxonium_dims: FluxoniumDims | None = None,
        coupler_dims: TunableTransmonDims | None = None,
    ):
        self.cfg = config or LatticeConfig()
        self.fluxonium_dims = fluxonium_dims or FluxoniumDims()
        self.coupler_dims = coupler_dims or TunableTransmonDims()

        # Auto-compute pitch if not explicitly set
        if self.cfg.pitch <= 0:
            self.cfg.pitch = self._compute_min_pitch()

        # Build prototype components (shared geometry; placement is per-call)
        self._data_qubit = FluxoniumQubit(dims=self.fluxonium_dims)
        self._coupler = TunableTransmonCoupler(dims=self.coupler_dims)

        # Pre-compute site & edge positions
        self._site_positions: Dict[Tuple[int, int], np.ndarray] = {}
        self._edge_positions: Dict[Tuple[Tuple[int,int], Tuple[int,int]], dict] = {}
        self._build_positions()

    # ── auto-pitch ─────────────────────────────────────────────────────
    def _compute_min_pitch(self) -> float:
        """Derive minimum pitch so facing pads have at least ``pad_gap`` clearance."""
        fx = self.fluxonium_dims.xmon
        fx_tip = fx.arm_width / 2 + fx.arm_len + fx.pad_head_size / 1.5

        tx = self.coupler_dims.xmon
        tx_tip = tx.arm_width / 2 + tx.long_arm_len + tx.pad_head_size / 1.5

        return 2 * (fx_tip + tx_tip + self.cfg.pad_gap)

    # ── position computation ───────────────────────────────────────────
    def _build_positions(self):
        p = self.cfg.pitch
        for r in range(self.cfg.rows):
            for c in range(self.cfg.cols):
                self._site_positions[(r, c)] = np.array([c * p, r * p], dtype=float)

        # Horizontal edges (connect (r,c) ↔ (r,c+1))
        for r in range(self.cfg.rows):
            for c in range(self.cfg.cols - 1):
                pos = (self._site_positions[(r, c)] + self._site_positions[(r, c + 1)]) / 2
                self._edge_positions[((r, c), (r, c + 1))] = {
                    "xy": pos, "direction": "horizontal",
                }
        # Vertical edges (connect (r,c) ↔ (r+1,c))
        for r in range(self.cfg.rows - 1):
            for c in range(self.cfg.cols):
                pos = (self._site_positions[(r, c)] + self._site_positions[(r + 1, c)]) / 2
                self._edge_positions[((r, c), (r + 1, c))] = {
                    "xy": pos, "direction": "vertical",
                }

    # ── public accessors ───────────────────────────────────────────────
    @property
    def site_positions(self) -> Dict[Tuple[int, int], np.ndarray]:
        """``{(row, col): np.array([x, y])}`` for every data-qubit site."""
        return dict(self._site_positions)

    @property
    def edge_positions(self):
        """``{((r1,c1),(r2,c2)): {"xy": ..., "direction": ...}}`` for every coupler edge."""
        return dict(self._edge_positions)

    @property
    def num_data_qubits(self) -> int:
        return self.cfg.rows * self.cfg.cols

    @property
    def num_couplers(self) -> int:
        return len(self._edge_positions)

    # ── checkerboard cell logic ────────────────────────────────────────
    def _cell_type(self, r: int, c: int, first_cell: str = "resonator") -> str:
        """Return ``'resonator'`` or ``'flux_line'`` for lattice cell *(r, c)*.

        Cell *(r, c)* is the square whose lower-left corner sits on
        data-qubit site *(r, c)*.  In a checkerboard layout the type
        alternates so that adjacent cells always differ.
        """
        if (r + c) % 2 == 0:
            return first_cell
        return "flux_line" if first_cell == "resonator" else "resonator"

    def _mirror_for_edge(
        self,
        edge_key: Tuple[Tuple[int, int], Tuple[int, int]],
        direction: str,
        first_cell: str = "resonator",
    ) -> bool:
        """Compute the *mirror* flag for a coupler so that its readout
        resonator faces the nearest ``'resonator'`` cell and the DC-SQUID /
        flux-line faces the nearest ``'flux_line'`` cell.
        """
        (r1, c1), (r2, c2) = edge_key

        if direction == "horizontal":
            r, c = r1, c1
            cell_above = (r, c) if r < self.cfg.rows - 1 else None
            cell_below = (r - 1, c) if r > 0 else None
            # mirror=True  → resonator faces UP
            # mirror=False → resonator faces DOWN
            if cell_above is not None:
                return self._cell_type(*cell_above, first_cell) == "resonator"
            return self._cell_type(*cell_below, first_cell) != "resonator"

        # vertical
        r, c = r1, c1
        cell_right = (r, c) if c < self.cfg.cols - 1 else None
        cell_left = (r, c - 1) if c > 0 else None
        # mirror=False → resonator faces RIGHT
        # mirror=True  → resonator faces LEFT
        if cell_right is not None:
            return self._cell_type(*cell_right, first_cell) != "resonator"
        return self._cell_type(*cell_left, first_cell) == "resonator"

    def _draw_cell_shading(
        self, ax: Axes, origin: Tuple[float, float],
        first_cell: str, alpha: float,
    ):
        """Draw subtle background rectangles to distinguish cell types."""
        ox, oy = origin
        p = self.cfg.pitch
        half = p * 0.46

        res_color  = "#d0e0ff"   # light blue  → resonator cells
        flux_color = "#ffe0d0"   # light peach → flux-line cells

        for r in range(self.cfg.rows - 1):
            for c in range(self.cfg.cols - 1):
                cx = c * p + p / 2 + ox
                cy = r * p + p / 2 + oy
                ct = self._cell_type(r, c, first_cell)
                color = res_color if ct == "resonator" else flux_color
                rect = patches.Rectangle(
                    (cx - half, cy - half), 2 * half, 2 * half,
                    facecolor=color, edgecolor="none", alpha=alpha,
                    zorder=-1,
                )
                ax.add_patch(rect)

    # ── drawing ─────────────────────────────────────────────────────────
    def place(
        self,
        ax: Axes,
        origin: Tuple[float, float] = (0, 0),
        labels: bool = False,
        label_fontsize: float = 8,
        cell_pattern: str = "checkerboard",
        first_cell: str = "resonator",
        shade_cells: bool = True,
        shade_alpha: float = 0.15,
    ):
        """
        Draw the full lattice on *ax*.

        Parameters
        ----------
        origin : tuple
            Global (x, y) offset applied to the entire lattice.
        labels : bool
            If True, annotate each qubit and coupler with an index.
        cell_pattern : str or None
            ``'checkerboard'`` — alternate *resonator* and *flux-line*
            unit cells so that each square contains either four readout
            resonators or four flux feed-lines pointing inward.
            ``None`` — no automatic coupler mirroring.
        first_cell : str
            Type of cell (0, 0): ``'resonator'`` or ``'flux_line'``.
        shade_cells : bool
            Draw a subtle colour wash behind each unit cell.
        shade_alpha : float
            Opacity of the cell shading rectangles.
        """
        ox, oy = origin

        # ── cell shading (behind everything) ───────────────────────────
        if shade_cells and cell_pattern == "checkerboard":
            self._draw_cell_shading(ax, origin, first_cell, shade_alpha)

        # ── data qubits ────────────────────────────────────────────────
        for idx, ((r, c), pos) in enumerate(sorted(self._site_positions.items())):
            gx, gy = pos[0] + ox, pos[1] + oy
            self._data_qubit.place(ax, (gx, gy))
            if labels:
                ax.text(gx, gy - 40, f"D{idx}", ha="center", va="top",
                        fontsize=label_fontsize, color=DEFAULT_PALETTE.label_color,
                        fontweight="bold")

        # ── couplers ───────────────────────────────────────────────────
        for idx, (edge_key, edge_info) in enumerate(sorted(self._edge_positions.items())):
            pos = edge_info["xy"]
            gx, gy = pos[0] + ox, pos[1] + oy
            coupler_angle = _edge_angle(edge_info["direction"])

            mirror = False
            if cell_pattern == "checkerboard":
                mirror = self._mirror_for_edge(
                    edge_key, edge_info["direction"], first_cell,
                )

            self._coupler.place(ax, (gx, gy), angle=coupler_angle, mirror=mirror)
            if labels:
                ax.text(gx, gy - 30, f"C{idx}", ha="center", va="top",
                        fontsize=label_fontsize - 1, color=DEFAULT_PALETTE.label_color,
                        fontstyle="italic")

    # ── auto view limits ───────────────────────────────────────────────
    def auto_lims(self, margin: float = 350) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Return ``((xmin, xmax), (ymin, ymax))`` enclosing all sites with *margin*."""
        all_pos = np.array(list(self._site_positions.values()))
        xmin, ymin = all_pos.min(axis=0) - margin
        xmax, ymax = all_pos.max(axis=0) + margin
        return (xmin, xmax), (ymin, ymax)
