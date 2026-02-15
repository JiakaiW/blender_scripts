"""
Full-chip 3D Blender renderer.

Reads the 2D lattice layout from ``visualization.lattice.SquareLattice``
and produces matching Blender geometry using the components defined in
this package.
"""

import bpy
import math
import numpy as np

from visualization.lattice import SquareLattice
from .components import Fluxonium3D, Coupler3D, LAYER_H
from .primitives import clear_scene, create_cuboid, get_material, GLOBAL_SCALE


class BlenderRenderer:
    """Render a full chip lattice in Blender, mirroring the 2D layout."""

    def __init__(self, lattice: SquareLattice):
        self.lattice = lattice
        self.fluxonium_3d = Fluxonium3D(lattice.fluxonium_dims)
        self.coupler_3d = Coupler3D(lattice.coupler_dims)

    def render(self):
        clear_scene()
        # Re-create components so material references are fresh
        self.fluxonium_3d = Fluxonium3D(self.lattice.fluxonium_dims)
        self.coupler_3d = Coupler3D(self.lattice.coupler_dims)
        self._draw_data_qubits()
        self._draw_couplers()
        self._draw_substrate()
        self._apply_global_scale()
        self._setup_scene()
        print("Rendering complete.")

    def _draw_data_qubits(self):
        print(f"Rendering {len(self.lattice.site_positions)} fluxoniums...")
        for idx, ((r, c), pos) in enumerate(
            sorted(self.lattice.site_positions.items())
        ):
            self.fluxonium_3d.place(
                (pos[0], pos[1], 0),
                angle_deg=0,
                name_prefix=f"D{idx}",
            )

    def _draw_couplers(self):
        print(f"Rendering {len(self.lattice.edge_positions)} couplers...")
        for idx, (edge_key, edge_info) in enumerate(
            sorted(self.lattice.edge_positions.items())
        ):
            pos = edge_info["xy"]
            direction = edge_info["direction"]
            angle = 0 if direction == "horizontal" else 90
            mirror = self.lattice._mirror_for_edge(edge_key, direction)

            self.coupler_3d.place(
                (pos[0], pos[1], 0),
                angle_deg=angle,
                mirror=mirror,
                name_prefix=f"C{idx}",
            )

    def _draw_substrate(self):
        (xmin, xmax), (ymin, ymax) = self.lattice.auto_lims(margin=200)
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        w = (xmax - xmin) * 5
        ht = (ymax - ymin) * 5

        # Flat plane slightly below z=0 to avoid z-fighting with object bottoms
        bpy.ops.mesh.primitive_plane_add(
            size=1,
            location=(cx, cy, -0.05),
        )
        sub = bpy.context.object
        sub.name = "Substrate"
        sub.scale = (w / 2, ht / 2, 1)
        mat = get_material("substrate")
        sub.data.materials.append(mat)

    def _apply_global_scale(self):
        """Scale all mesh objects by GLOBAL_SCALE to shrink to Blender-friendly size."""
        s = GLOBAL_SCALE
        bpy.ops.object.select_all(action="SELECT")
        # Apply scale to every object's location + dimensions
        for obj in bpy.context.selected_objects:
            obj.location = (obj.location.x * s, obj.location.y * s, obj.location.z * s)
            obj.scale = (obj.scale.x * s, obj.scale.y * s, obj.scale.z * s)
        bpy.ops.object.select_all(action="DESELECT")

    def _setup_scene(self):
        """SEM-microscope-style lighting: soft, even, low contrast."""
        s = GLOBAL_SCALE
        (xmin, xmax), (ymin, ymax) = self.lattice.auto_lims(margin=100)
        cx = (xmin + xmax) / 2 * s
        cy = (ymin + ymax) / 2 * s
        span = max(xmax - xmin, ymax - ymin) * s

        # Grey world background (like SEM vacuum chamber)
        world = bpy.context.scene.world
        if world is None:
            world = bpy.data.worlds.new("World")
            bpy.context.scene.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs["Color"].default_value = (0.02, 0.02, 0.02, 1)
            bg.inputs["Strength"].default_value = 0.3

        # Camera
        bpy.ops.object.camera_add(
            location=(cx, cy - span * 0.8, span * 0.7),
            rotation=(math.radians(50), 0, 0),
        )
        bpy.context.scene.camera = bpy.context.object

        # Main fill light — bright, soft overhead
        bpy.ops.object.light_add(
            type="AREA",
            location=(cx, cy, span * 0.5),
        )
        fill = bpy.context.object
        fill.data.energy = 200
        fill.data.size = span * 1.2
        fill.data.color = (0.95, 0.95, 1.0)
        fill.rotation_euler = (0, 0, 0)  # pointing straight down

        # Rim light — low angle from the side for edge contrast
        bpy.ops.object.light_add(
            type="AREA",
            location=(cx + span * 0.6, cy, span * 0.15),
        )
        rim = bpy.context.object
        rim.data.energy = 80
        rim.data.size = span * 0.5
        rim.data.color = (1.0, 1.0, 1.0)
        rim.rotation_euler = (math.radians(75), 0, math.radians(90))
