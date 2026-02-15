
"""
Test: render two parallel JJ chains connected at one end by a
Josephson junction (island bar + half-bridge overlap).

Run inside Blender (via the Blender Development extension or
  blender --python test_jj_chain_3d.py
).
"""

import sys
import os
import bpy
import math

# ── path setup ──────────────────────────────────────────────────────────
project_root = "/Users/jiakaiwang/Documents/Github/CoupledQuantumSystems"
if project_root not in sys.path:
    sys.path.append(project_root)

# Force-reload so edits are picked up without restarting Blender
import importlib
import visualization_3d.primitives as _p
import visualization_3d.components as _c
importlib.reload(_p)
importlib.reload(_c)

from visualization_3d.primitives import (
    clear_scene, get_material, create_cuboid, create_half_bridge,
)
from visualization_3d.components import JJChain3D, LAYER_H, BRIDGE_W_FRAC, SIGMOID_STEEP
from visualization.styles import JJChainDims


def test_dual_chain():
    clear_scene()

    # ── dimensions ──────────────────────────────────────────────────────
    dims = JJChainDims(gap=3)
    h = LAYER_H
    sep = 15.0          # Y distance between two chain centre-lines
    y1 = -sep / 2       # chain 1 centre-line
    y2 =  sep / 2       # chain 2 centre-line
    delta = dims.overlap # how far the island bar extends past midpoint
    conn_width = dims.width  # connector bar width (same as chain)

    # ── two parallel chains along +X ───────────────────────────────
    chain = JJChain3D(dims)
    total_len = chain.place(location=(0, y1, 0), angle_deg=0,
                            name_prefix="ChainA")
    chain.place(location=(0, y2, 0), angle_deg=0,
                name_prefix="ChainB")

    # ── connector at x = x_end ─────────────────────────────────────
    # The connector joins the two chains at x_end + width/2.
    #
    # Piece 1 (Layer 1 island): runs along Y from y1 - w/2
    #   past the midpoint by delta.
    # Piece 2 (Layer 2 half-bridge): runs along Y from y2 + w/2
    #   down to the midpoint.  Its wing climbs onto the island bar.

    x_end = total_len  # right-hand edge of both chains
    cx = x_end + conn_width / 2   # x position of both connector pieces
    y_bot = y1 - conn_width / 2   # bottom edge of connector
    y_top = y2 + conn_width / 2   # top edge of connector
    y_mid = (y1 + y2) / 2

    # --- Piece 1: island bar (Layer 1) ---------------------------------
    # From y_bot to y_mid + delta
    bar_len = (y_mid + delta) - y_bot
    bar_cy = y_bot + bar_len / 2
    create_cuboid(
        (cx, bar_cy, h / 2),
        (conn_width / 2, bar_len / 2, h / 2),
        name="Conn_Island",
        material=get_material("aluminum"),
    )

    # --- Piece 2: half-bridge (Layer 2) --------------------------------
    # From y_top down to y_mid
    hb_len = y_top - y_mid
    hb_cy = y_mid + hb_len / 2
    bridge_w = conn_width * BRIDGE_W_FRAC
    # Rotate -90° about Z so local +X → -Y (wing points toward y_mid).
    create_half_bridge(
        (cx, hb_cy, 0),
        total_length=hb_len,
        width=bridge_w,
        h_step=h,
        thickness=h,
        overlap_len=delta,
        name="Conn_HalfBridge",
        material=get_material("aluminum2"),
        steepness=SIGMOID_STEEP,
        rotation_euler=(0, 0, -math.pi / 2),
    )

    # ── substrate ───────────────────────────────────────────────────
    margin = 10
    create_cuboid(
        (total_len / 2 + conn_width / 2, 0, -1.0),
        ((total_len + conn_width + 2 * margin) / 2,
         (sep + dims.width + 2 * margin) / 2,
         1.0),
        name="Substrate",
        material=get_material("substrate"),
    )

    # ── camera + light ──────────────────────────────────────────────
    bpy.ops.object.select_all(action="DESELECT")
    cam_x = total_len / 2
    cam_y = -total_len * 0.55
    cam_z = total_len * 0.40
    bpy.ops.object.camera_add(
        location=(cam_x, cam_y, cam_z),
        rotation=(1.1, 0, 0),
    )
    bpy.context.scene.camera = bpy.context.object

    bpy.ops.object.light_add(type="SUN",
                             location=(cam_x, 0, total_len * 0.6))
    bpy.context.object.data.energy = 4

    print(f"Dual JJ Chain test complete — {total_len:.0f} units long, "
          f"sep={sep}, delta={delta}.")


test_dual_chain()
