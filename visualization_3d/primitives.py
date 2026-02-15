"""
Low-level 3D building blocks for Blender chip visualization.

Mirrors the role of ``visualization/primitives.py`` (matplotlib) but
generates Blender geometry instead.  Every helper works in *data units*
(the same coordinate system used by the 2D drawing) with explicit Z
heights to create the layered thin-film structure.
"""

import bpy
import bmesh
import math
import numpy as np


# ── global scale ────────────────────────────────────────────────────────

GLOBAL_SCALE = 0.01   # shrink data-unit coords → Blender units


# ── materials ───────────────────────────────────────────────────────────

def create_material(
    name, color, metal=0.9, rough=0.4, alpha=1.0,
    bump_strength=0.2, noise_scale=500.0, noise_detail=12.0,
):
    """SEM-microscope-style metallic material with rough grain.

    Two noise layers (coarse grain + fine speckle) → bump + roughness
    variation, giving the uneven look of e-beam evaporated aluminium
    viewed under a scanning electron microscope.
    """
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Alpha"].default_value = alpha
    # Low specular for diffuse SEM-like look
    for spec_name in ("Specular IOR Level", "Specular"):
        if spec_name in bsdf.inputs:
            bsdf.inputs[spec_name].default_value = 0.15
            break

    if alpha < 1.0:
        mat.blend_method = "BLEND"
        mat.shadow_method = "NONE"

    # --- Coarse grain noise (large bumps, deposited clusters) ---
    noise_coarse = nodes.new(type="ShaderNodeTexNoise")
    noise_coarse.inputs["Scale"].default_value = noise_scale * 0.3
    noise_coarse.inputs["Detail"].default_value = 6.0
    noise_coarse.inputs["Roughness"].default_value = 0.7
    noise_coarse.inputs["Distortion"].default_value = 0.8

    # --- Fine speckle noise (micro-roughness) ---
    noise_fine = nodes.new(type="ShaderNodeTexNoise")
    noise_fine.inputs["Scale"].default_value = noise_scale
    noise_fine.inputs["Detail"].default_value = noise_detail
    noise_fine.inputs["Roughness"].default_value = 0.5
    noise_fine.inputs["Distortion"].default_value = 0.2

    # --- Mix both noise layers (version-safe) ---
    try:
        mix_noise = nodes.new(type="ShaderNodeMix")
        mix_noise.data_type = "FLOAT"
        mix_noise.inputs[0].default_value = 0.4      # Factor
        links.new(noise_coarse.outputs["Fac"], mix_noise.inputs[2])  # A
        links.new(noise_fine.outputs["Fac"], mix_noise.inputs[3])    # B
        mix_noise_out = mix_noise.outputs[0]
    except Exception:
        # Blender < 3.4 fallback: MixRGB node
        mix_noise = nodes.new(type="ShaderNodeMixRGB")
        mix_noise.inputs["Fac"].default_value = 0.4
        links.new(noise_coarse.outputs["Fac"], mix_noise.inputs["Color1"])
        links.new(noise_fine.outputs["Fac"], mix_noise.inputs["Color2"])
        mix_noise_out = mix_noise.outputs["Color"]

    # --- Roughness variation via color ramp ---
    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "LINEAR"
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (rough * 0.6, rough * 0.6, rough * 0.6, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (min(rough * 1.6, 1.0),) * 3 + (1,)

    links.new(mix_noise_out, ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Roughness"])

    # --- Bump map (both layers stacked) ---
    bump_fine = nodes.new(type="ShaderNodeBump")
    bump_fine.inputs["Strength"].default_value = bump_strength * 0.6
    bump_fine.inputs["Distance"].default_value = 0.005
    links.new(noise_fine.outputs["Fac"], bump_fine.inputs["Height"])

    bump_coarse = nodes.new(type="ShaderNodeBump")
    bump_coarse.inputs["Strength"].default_value = bump_strength
    bump_coarse.inputs["Distance"].default_value = 0.015
    links.new(noise_coarse.outputs["Fac"], bump_coarse.inputs["Height"])
    links.new(bump_fine.outputs["Normal"], bump_coarse.inputs["Normal"])
    links.new(bump_coarse.outputs["Normal"], bsdf.inputs["Normal"])

    # --- Subtle base-colour variation (graininess in brightness) ---
    darker = tuple(c * 0.75 for c in color[:3]) + (1,)
    try:
        mix_rgb = nodes.new(type="ShaderNodeMix")
        mix_rgb.data_type = "RGBA"
        mix_rgb.inputs[0].default_value = 0.12        # Factor
        mix_rgb.inputs[6].default_value = color        # Color A
        mix_rgb.inputs[7].default_value = darker       # Color B
        links.new(mix_noise_out, mix_rgb.inputs[0])
        links.new(mix_rgb.outputs[2], bsdf.inputs["Base Color"])
    except Exception:
        mix_rgb = nodes.new(type="ShaderNodeMixRGB")
        mix_rgb.inputs["Fac"].default_value = 0.12
        mix_rgb.inputs["Color1"].default_value = color
        mix_rgb.inputs["Color2"].default_value = darker
        links.new(mix_noise_out, mix_rgb.inputs["Fac"])
        links.new(mix_rgb.outputs["Color"], bsdf.inputs["Base Color"])

    return mat


# Shared material palette (lazy-created on first use)
_MAT_CACHE: dict = {}

def get_material(key: str):
    """Return a shared material from a fixed palette."""
    if key not in _MAT_CACHE:
        # Niobium (blue-silver) for data qubits, gold for couplers,
        # medium-grey silicon substrate.
        #                       color                            metal  rough  bump   noise_scale
        palette = {
            "aluminum":  ((0.62, 0.66, 0.78, 1),               0.90,  0.40,  0.7,   500.0),   # Nb blue-silver
            "aluminum2": ((0.55, 0.60, 0.74, 1),               0.90,  0.45,  0.9,   600.0),   # Nb bridge layer
            "junction":  ((0.50, 0.53, 0.62, 1),               0.80,  0.50,  0.5,   400.0),   # Al oxide barrier
            "substrate": ((0.35, 0.35, 0.37, 1),               0.05,  0.12,  0.15,  150.0),   # Si wafer grey
            "coupler":   ((0.72, 0.63, 0.38, 1),               0.90,  0.35,  0.7,   500.0),   # TiN gold
        }
        color, metal, rough, bump_s, noise_s = palette[key]
        _MAT_CACHE[key] = create_material(
            f"Mat_{key}", color, metal, rough,
            bump_strength=bump_s, noise_scale=noise_s,
        )
    return _MAT_CACHE[key]


# ── scene helpers ───────────────────────────────────────────────────────

def clear_scene():
    """Delete every object and purge orphan data."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    _MAT_CACHE.clear()  # avoid stale references to deleted materials


# ── basic shapes ────────────────────────────────────────────────────────

def create_cuboid(location, dimensions, name="Cuboid", material=None,
                  rotation_euler=(0, 0, 0)):
    """Create a box with *dimensions* = (sx, sy, sz) half-extents via scale.

    ``size=2`` gives vertices at ±1, so ``scale = half_extents`` yields
    the correct full extent of ``2 × half_extents``.
    """
    bpy.ops.mesh.primitive_cube_add(size=2, location=location,
                                    rotation=rotation_euler)
    obj = bpy.context.object
    obj.name = name
    obj.scale = dimensions
    if material:
        obj.data.materials.append(material)
    return obj


# ── extruded path (bmesh ribbon with rectangular cross-section) ─────────

def create_extruded_path(
    points_2d,
    width,
    height,
    location=(0, 0, 0),
    name="ExtrudedPath",
    material=None,
    rotation_euler=(0, 0, 0),
):
    """Sweep a rectangular cross-section along a 2D polyline.

    Builds a fully closed mesh: at every centreline vertex we place four
    corners of the rectangle (oriented perpendicular to the path
    direction), then stitch adjacent quads for top, bottom, and two side
    walls, plus end-caps.

    Parameters
    ----------
    points_2d : sequence of (x, y)
        Centreline vertices in local coordinates.
    width : float
        Full width of the rectangular cross-section (perpendicular to
        the path direction, in the XY plane).
    height : float
        Full height of the cross-section (Z direction).
    location : (x, y, z)
        World offset applied to the whole object.
    """
    pts = list(points_2d)
    n = len(pts)
    if n < 2:
        return None

    hw = width / 2
    hh = height / 2

    mesh = bpy.data.meshes.new(name + "_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    # For each centreline point compute a perpendicular direction in XY,
    # then place 4 verts: bottom-left, bottom-right, top-right, top-left.
    rings = []  # list of (v_bl, v_br, v_tr, v_tl) per point

    for i in range(n):
        px, py = pts[i]

        # Tangent direction: average of segments before & after
        if i == 0:
            tx, ty = pts[1][0] - px, pts[1][1] - py
        elif i == n - 1:
            tx, ty = px - pts[i - 1][0], py - pts[i - 1][1]
        else:
            tx = pts[i + 1][0] - pts[i - 1][0]
            ty = pts[i + 1][1] - pts[i - 1][1]

        tlen = math.hypot(tx, ty)
        if tlen < 1e-9:
            tx, ty = 1.0, 0.0
        else:
            tx /= tlen
            ty /= tlen

        # Perpendicular (rotate tangent 90° CCW)
        nx, ny = -ty, tx

        # Four corners of the rectangle at this point
        v_bl = bm.verts.new((px + nx * hw, py + ny * hw, -hh))
        v_br = bm.verts.new((px - nx * hw, py - ny * hw, -hh))
        v_tr = bm.verts.new((px - nx * hw, py - ny * hw,  hh))
        v_tl = bm.verts.new((px + nx * hw, py + ny * hw,  hh))
        rings.append((v_bl, v_br, v_tr, v_tl))

    bm.verts.ensure_lookup_table()

    # Stitch adjacent rings with quad faces
    for i in range(n - 1):
        bl0, br0, tr0, tl0 = rings[i]
        bl1, br1, tr1, tl1 = rings[i + 1]

        # Bottom face (Z = -hh side)
        bm.faces.new((bl0, br0, br1, bl1))
        # Top face (Z = +hh side)
        bm.faces.new((tl0, tl1, tr1, tr0))
        # Left wall
        bm.faces.new((bl0, bl1, tl1, tl0))
        # Right wall
        bm.faces.new((br0, tr0, tr1, br1))

    # End caps
    bl, br, tr, tl = rings[0]
    bm.faces.new((bl, tl, tr, br))
    bl, br, tr, tl = rings[-1]
    bm.faces.new((bl, br, tr, tl))

    bm.to_mesh(mesh)
    bm.free()

    obj.location = location
    obj.rotation_euler = rotation_euler

    if material:
        obj.data.materials.append(material)
    return obj


# ── Dolan bridge (sigmoid-profile top electrode) ───────────────────────

def create_dolan_bridge(
    location,
    total_length,
    width,
    h_step,
    thickness,
    overlap_len,
    name="DolanBridge",
    material=None,
    steepness=15,
    rotation_euler=(0, 0, 0),
    res_x=120,
):
    """
    A closed-mesh thin-film strip whose bottom surface follows a
    double-sigmoid profile and whose top surface is offset by
    *thickness* above it.

    Physical picture (Dolan bridge):
      - The bridge is the *second* deposited aluminium layer.
      - Where it overlaps an island (first layer, height *h_step*),
        the bridge bottom sits at ``z = h_step`` and its top at
        ``z = h_step + thickness``.
      - In the gap between islands, the bridge bottom sits on the
        substrate at ``z = 0`` and its top at ``z = thickness``.
      - Two sigmoid ramps connect those levels.

    The mesh is fully closed (bottom face strip, top face strip,
    two side walls, two end-caps) so it renders correctly without
    any Solidify modifier.

    Parameters
    ----------
    total_length : float
        Full X extent of the bridge (gap + 2 × overlap).
    width : float
        Y extent.
    h_step : float
        Height of the bottom electrodes the bridge climbs onto.
    thickness : float
        Thickness of this (second) deposited layer.
    overlap_len : float
        How far the bridge extends onto each island.
    steepness : float
        Sigmoid sharpness.
    """
    mesh = bpy.data.meshes.new(name + "_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    xs = np.linspace(-total_length / 2, total_length / 2, res_x)
    left_step = -total_length / 2 + overlap_len
    right_step = total_length / 2 - overlap_len

    def sigmoid_z(x):
        """Bottom-surface Z: h_step on islands, 0 in gap."""
        s_left = 1 / (1 + math.exp(steepness * (x - left_step)))
        s_right = 1 / (1 + math.exp(-steepness * (x - right_step)))
        return h_step * (s_left + s_right)

    # Build four rows of vertices per x-slice:
    #   bottom-left, bottom-right, top-left, top-right
    bot_rows = []   # (v_bl, v_br)
    top_rows = []   # (v_tl, v_tr)
    hy = width / 2
    for x in xs:
        zb = sigmoid_z(x)
        zt = zb + thickness
        v_bl = bm.verts.new((x, -hy, zb))
        v_br = bm.verts.new((x,  hy, zb))
        v_tl = bm.verts.new((x, -hy, zt))
        v_tr = bm.verts.new((x,  hy, zt))
        bot_rows.append((v_bl, v_br))
        top_rows.append((v_tl, v_tr))

    bm.verts.ensure_lookup_table()
    n = len(xs)
    for i in range(n - 1):
        bl0, br0 = bot_rows[i]
        bl1, br1 = bot_rows[i + 1]
        tl0, tr0 = top_rows[i]
        tl1, tr1 = top_rows[i + 1]
        # bottom face (normal down)
        bm.faces.new((bl0, br0, br1, bl1))
        # top face (normal up)
        bm.faces.new((tl0, tl1, tr1, tr0))
        # left side wall (y = -hy, normal -Y)
        bm.faces.new((bl0, bl1, tl1, tl0))
        # right side wall (y = +hy, normal +Y)
        bm.faces.new((br0, tr0, tr1, br1))

    # end caps
    bl0, br0 = bot_rows[0]
    tl0, tr0 = top_rows[0]
    bm.faces.new((bl0, tl0, tr0, br0))     # left end
    bl_n, br_n = bot_rows[-1]
    tl_n, tr_n = top_rows[-1]
    bm.faces.new((bl_n, br_n, tr_n, tl_n)) # right end

    bm.to_mesh(mesh)
    bm.free()

    obj.location = location
    obj.rotation_euler = rotation_euler

    if material:
        obj.data.materials.append(material)
    return obj


# ── Half bridge (single sigmoid, one wing) ─────────────────────────────

def create_half_bridge(
    location,
    total_length,
    width,
    h_step,
    thickness,
    overlap_len,
    name="HalfBridge",
    material=None,
    steepness=15,
    rotation_euler=(0, 0, 0),
    res_x=80,
):
    """
    A closed-mesh strip with a *single* sigmoid transition.

    The strip starts at substrate level (``z = 0``) on the ``-X`` end
    and climbs to ``z = h_step`` over the last ``overlap_len`` on the
    ``+X`` end, forming one wing that sits on top of a neighbouring
    island.

    Used at the endpoints where two parallel JJ chains are connected:
    one bar is a plain island (Layer 1) that extends slightly past the
    midpoint, and the other bar is this half-bridge (Layer 2) that
    overlaps it.
    """
    mesh = bpy.data.meshes.new(name + "_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    xs = np.linspace(-total_length / 2, total_length / 2, res_x)
    # Sigmoid transition happens near the +X end
    step_x = total_length / 2 - overlap_len

    def sigmoid_z(x):
        s = 1 / (1 + math.exp(-steepness * (x - step_x)))
        return h_step * s

    bot_rows = []
    top_rows = []
    hy = width / 2
    for x in xs:
        zb = sigmoid_z(x)
        zt = zb + thickness
        v_bl = bm.verts.new((x, -hy, zb))
        v_br = bm.verts.new((x,  hy, zb))
        v_tl = bm.verts.new((x, -hy, zt))
        v_tr = bm.verts.new((x,  hy, zt))
        bot_rows.append((v_bl, v_br))
        top_rows.append((v_tl, v_tr))

    bm.verts.ensure_lookup_table()
    n = len(xs)
    for i in range(n - 1):
        bl0, br0 = bot_rows[i]
        bl1, br1 = bot_rows[i + 1]
        tl0, tr0 = top_rows[i]
        tl1, tr1 = top_rows[i + 1]
        bm.faces.new((bl0, br0, br1, bl1))   # bottom
        bm.faces.new((tl0, tl1, tr1, tr0))   # top
        bm.faces.new((bl0, bl1, tl1, tl0))   # left wall
        bm.faces.new((br0, tr0, tr1, br1))   # right wall

    # end caps
    bl0, br0 = bot_rows[0];   tl0, tr0 = top_rows[0]
    bm.faces.new((bl0, tl0, tr0, br0))
    bl_n, br_n = bot_rows[-1]; tl_n, tr_n = top_rows[-1]
    bm.faces.new((bl_n, br_n, tr_n, tl_n))

    bm.to_mesh(mesh)
    bm.free()

    obj.location = location
    obj.rotation_euler = rotation_euler

    if material:
        obj.data.materials.append(material)
    return obj

