import bpy
import bmesh
import math

def create_material(name, color, metal=1.0, rough=0.2):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Metallic'].default_value = metal
        bsdf.inputs['Roughness'].default_value = rough
    return mat

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

# 1. Setup
clear_scene()
al_mat = create_material("Aluminum", (0.8, 0.8, 0.9, 1))

# 2. Parameters
h1 = 0.3          # Height of bottom chunk
h2 = 0.15         # Thickness of top sheet
step_center = 0.5 # X location where the step occurs
steepness = 7    # Controls how "gradual" the slope is (Lower = Smoother)
res_x = 100       # High resolution for smooth bending
res_y = 20

# 3. Create Chunk 1 (Bottom Electrode)
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.5, 0, h1/2))
c1 = bpy.context.object
c1.name = "Bottom_Electrode"
c1.scale = (2.0, 1.0, h1)
c1.data.materials.append(al_mat)

# 4. Create Chunk 2 (The Smooth Flowing Layer)
# Start with a plane centered roughly where the step happens
bpy.ops.mesh.primitive_plane_add(size=1, location=(0.5, 0, 0))
c2 = bpy.context.object
c2.name = "Top_Smooth_Electrode"
# Scale X to cover the step area well
c2.scale = (3.0, 1.0, 1.0) 

# Apply scale to freeze dimensions before editing
bpy.ops.object.transform_apply(scale=True)

# Subdivide to give us vertices to move
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=res_x) 
bpy.ops.object.mode_set(mode='OBJECT')

# 5. Apply Sigmoid Function to Vertices
mesh = c2.data
for v in mesh.vertices:
    # Get world X coordinate
    world_x = (c2.matrix_world @ v.co).x
    
    # Sigmoid Logic: 
    # If x is far left, z -> h1 (top of step)
    # If x is far right, z -> 0 (ground)
    # Note: We reverse the typical sigmoid direction to step "down" or "up" as needed.
    # Here we want it to be HIGH on the left (on top of chunk 1) and LOW on the right.
    
    # Calculate Z using logistic function
    # The negative sign in "-steepness" makes it go from High to Low as X increases
    z_val = h1 / (1 + math.exp(steepness * (world_x - step_center)))
    
    v.co.z = z_val

mesh.update()

# 6. Add Thickness and Smoothing Modifiers
# Solidify: Gives it the aluminum thickness
mod_solid = c2.modifiers.new(name="Solidify", type='SOLIDIFY')
mod_solid.thickness = h2
mod_solid.offset = 1 

# Subdivision Surface: Makes it look like liquid/glassy smooth metal
mod_subsurf = c2.modifiers.new(name="Subsurf", type='SUBSURF')
mod_subsurf.levels = 2
mod_subsurf.render_levels = 3

# Shade Smooth
bpy.ops.object.shade_smooth()
c2.data.materials.append(al_mat)

# 7. Lighting
bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))
bpy.context.object.data.energy = 5
bpy.ops.object.camera_add(location=(3, -4, 2.5), rotation=(1.1, 0, 0.6))
bpy.context.scene.camera = bpy.context.object

print("Smooth Sigmoid Bridge Generated")