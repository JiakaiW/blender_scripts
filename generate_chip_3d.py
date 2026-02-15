import sys
import os

project_root = "/Users/jiakaiwang/Documents/Github/blender_scripts"
if project_root not in sys.path:
    sys.path.append(project_root)

# Force-reload so edits are picked up without restarting Blender
import importlib
import visualization_3d.primitives as _p
import visualization_3d.components as _c
import visualization_3d.renderer as _r
importlib.reload(_p)
importlib.reload(_c)
importlib.reload(_r)

from visualization.styles import LatticeConfig
from visualization.lattice import SquareLattice
from visualization_3d.renderer import BlenderRenderer

# Create a 6×6 lattice (pitch=0 → auto-compute)
lattice = SquareLattice(config=LatticeConfig(rows=6, cols=6, pitch=0))

# Render the full chip in Blender
renderer = BlenderRenderer(lattice)
renderer.render()
