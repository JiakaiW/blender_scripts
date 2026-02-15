"""
Top-level convenience functions for rendering full chip layouts.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from typing import Optional, Tuple

from .styles import LatticeConfig, FluxoniumDims, TunableTransmonDims, DEFAULT_PALETTE
from .lattice import SquareLattice
from .qubits import FluxoniumQubit, TunableTransmonCoupler


def draw_chip(
    rows: int = 3,
    cols: int = 3,
    pitch: float = 0,
    figsize: Optional[Tuple[float, float]] = None,
    labels: bool = True,
    fluxonium_dims: FluxoniumDims | None = None,
    coupler_dims: TunableTransmonDims | None = None,
    title: str | None = None,
    ax: Axes | None = None,
    show: bool = True,
) -> Axes:
    """
    Draw a complete chip with fluxonium data qubits on a square lattice
    and tunable-transmon couplers on every edge.

    Parameters
    ----------
    rows, cols : int
        Lattice dimensions.
    pitch : float
        Center-to-center distance between adjacent data qubits.
    figsize : tuple or None
        Matplotlib figure size; auto-computed if None.
    labels : bool
        Annotate qubits (D0, D1, …) and couplers (C0, C1, …).
    fluxonium_dims, coupler_dims
        Optional dimension overrides.
    title : str or None
        Figure title.
    ax : Axes or None
        If provided, draw on this Axes instead of creating a new figure.
    show : bool
        Call ``plt.show()`` at the end (ignored when *ax* is provided).

    Returns
    -------
    ax : matplotlib.axes.Axes
    """
    config = LatticeConfig(rows=rows, cols=cols, pitch=pitch)
    lattice = SquareLattice(config, fluxonium_dims=fluxonium_dims,
                            coupler_dims=coupler_dims)

    # Auto figure size
    if ax is None:
        if figsize is None:
            figsize = (4 + cols * 3.5, 4 + rows * 3.5)
        fig, ax = plt.subplots(figsize=figsize)
    ax.set_aspect("equal")
    ax.set_facecolor(DEFAULT_PALETTE.background)
    ax.axis("off")

    lattice.place(ax, labels=labels)

    # Auto limits
    (xmin, xmax), (ymin, ymax) = lattice.auto_lims()
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")

    plt.tight_layout()
    if show and ax is not None:
        plt.show()

    return ax


# ── quick-draw single components (useful during development) ───────────
def draw_fluxonium(dims: FluxoniumDims | None = None, show: bool = True) -> Axes:
    """Draw a single fluxonium qubit centred at the origin."""
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_aspect("equal")
    ax.set_facecolor(DEFAULT_PALETTE.background)
    ax.axis("off")
    FluxoniumQubit(dims).place(ax, (0, 0))
    ax.set_xlim(-350, 350)
    ax.set_ylim(-350, 350)
    ax.set_title("Fluxonium Data Qubit", fontsize=12, fontweight="bold")
    plt.tight_layout()
    if show:
        plt.show()
    return ax


def draw_coupler(dims: TunableTransmonDims | None = None, show: bool = True) -> Axes:
    """Draw a single tunable-transmon coupler centred at the origin."""
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_aspect("equal")
    ax.set_facecolor(DEFAULT_PALETTE.background)
    ax.axis("off")
    TunableTransmonCoupler(dims).place(ax, (0, 0))
    ax.set_xlim(-300, 300)
    ax.set_ylim(-300, 300)
    ax.set_title("Tunable Transmon Coupler", fontsize=12, fontweight="bold")
    plt.tight_layout()
    if show:
        plt.show()
    return ax
