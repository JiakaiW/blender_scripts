"""Default color palettes and dimension presets for chip visualization."""

from dataclasses import dataclass, field
from typing import Dict


# ── Color palettes ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Palette:
    """A named colour scheme for the chip drawing."""
    xmon_body: str = "#9EAAB2"
    jj_chain_island: str = "#6B8E9B"
    jj_chain_bridge: str = "#4A6C6F"
    junction: str = "#D95F5F"
    resonator: str = "#7BA3B8"
    dc_squid_body: str = "#D95F5F"        # JJ rectangles in SQUID
    squid_leg: str = "#D4B84A"              # yellow thin bars / U-bar
    connector: str = "#6B8E9B"
    background: str = "#F5F5F7"
    coupler_body: str = "#B8A07A"
    flux_line: str = "#8B6C42"
    label_color: str = "#333333"


DEFAULT_PALETTE = Palette()


# ── Dimension presets ───────────────────────────────────────────────────────
@dataclass
class XmonDims:
    """Standard Xmon cross dimensions (µm-like units)."""
    arm_len: float = 140
    arm_width: float = 30
    pad_head_size: float = 60


@dataclass
class JJChainDims:
    """Standard JJ chain dimensions."""
    length: float = 200
    width: float = 15
    island_len: float = 20
    gap: float = 15
    overlap: float = 6


@dataclass
class FluxoniumDims:
    """Composite dimensions for a full fluxonium qubit."""
    xmon: XmonDims = field(default_factory=XmonDims)
    chain: JJChainDims = field(default_factory=JJChainDims)
    chain_separation: float = 40
    chain_start_dist: float = 15   # distance from Xmon centre to chain start
    chain_angle: float = -45  # degrees, relative to Xmon center
    connector_bar_extra: float = 6
    connector_bar_height: float = 6


@dataclass
class CouplerXmonDims:
    """Xmon dimensions for a tunable-transmon coupler (two short + two long)."""
    long_arm_len: float = 100
    short_arm_len: float = 50
    arm_width: float = 24
    pad_head_size: float = 45


@dataclass
class DCSqUIDDims:
    """DC-SQUID drawn as two parallel legs + U-bar + two JJs."""
    leg_length: float = 40       # how far the two thin bars extend from the arm
    leg_separation: float = 20   # distance between the two parallel bars
    leg_width: float = 3         # thickness of each thin bar (data units)
    u_bar_width: float = 3       # thickness of the connecting U-bar (data units)
    junction_width: float = 10   # JJ rectangle width (along leg)
    junction_height: float = 8   # JJ rectangle height (across leg)


@dataclass
class ResonatorDims:
    """Readout resonator (smooth meander with semicircular turns)."""
    lead_length: float = 15       # initial straight segment before first turn
    turn_radius: float = 8        # radius of semicircular U-turns
    meander_amplitude: float = 30 # vertical distance between top and bottom straights
    num_turns: int = 5            # number of semicircular U-turns
    width: float = 3              # half-width of the resonator trace (data units)


@dataclass
class FluxLineDims:
    """Flux bias feed line dimensions."""
    length: float = 60        # total length of the feed line
    width: float = 3          # half-width of the feed line trace (data units)
    standoff: float = 8       # gap between SQUID and start of line
    hook_radius: float = 6    # radius of mutual-inductance hook (data units)
    hook_width: float = 2.5   # half-width of hook stroke (data units)


@dataclass
class TunableTransmonDims:
    """Composite dimensions for a full tunable-transmon coupler."""
    xmon: CouplerXmonDims = field(default_factory=CouplerXmonDims)
    dc_squid: DCSqUIDDims = field(default_factory=DCSqUIDDims)
    resonator: ResonatorDims = field(default_factory=ResonatorDims)
    flux_line: FluxLineDims = field(default_factory=FluxLineDims)
    squid_arm_index: int = 0        # which short arm gets the SQUID (0 or 1)
    resonator_arm_index: int = 1    # which short arm gets the resonator


# ── Lattice presets ─────────────────────────────────────────────────────────
@dataclass
class LatticeConfig:
    """Configuration for a square lattice of qubits + couplers."""
    rows: int = 3
    cols: int = 3
    pitch: float = 0    # 0 = auto-compute from component dims; >0 = explicit
    pad_gap: float = 20 # desired clearance between facing pads (used by auto-pitch)
