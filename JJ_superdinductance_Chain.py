import bpy

# Clear existing objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Parameters for the unit cell
unit_length = 1.0  # Adjust the size as needed
length_ratio = 15
width_ratio = 6
height_ratio = 1
num_cells = 50         # Number of unit cells to duplicate in each layer
y_interval = 4         # Spacing between each unit cell along the Y-axis
layer_offset_y = 2     # Offset for the second layer in the Y-axis
x_offset = 30           # Spacing between each duplicated chain along the X-axis
num_chains = 2         # Number of chains to duplicate along the X-axis

# Calculate the dimensions based on the ratios
unit_cell_length = unit_length * length_ratio
unit_cell_width = unit_length * width_ratio
unit_cell_height = unit_length * height_ratio

# Create a single unit cell as the basis
bpy.ops.mesh.primitive_cube_add(size=1)
unit_cell = bpy.context.object
unit_cell.scale = (unit_cell_length / 2, unit_cell_width / 2, unit_cell_height / 2)
unit_cell.location = (0, 0, unit_cell_height / 2)
unit_cell.name = "Unit_Cell"

# Function to create a chain with two layers at a specific X location
def create_chain(x_location):
    first_layer = []
    # First layer
    for i in range(num_cells):
        new_cell = unit_cell.copy()
        new_cell.data = unit_cell.data.copy()  # Ensure each object has its own mesh data
        new_cell.location = (x_location, i * y_interval, unit_cell_height / 2)
        bpy.context.collection.objects.link(new_cell)
        first_layer.append(new_cell)

    # Second layer, offset in Z and Y
    for cell in first_layer:
        new_cell = cell.copy()
        new_cell.data = cell.data.copy()  # Ensure each object has its own mesh data
        new_cell.location = (cell.location[0], cell.location[1] + layer_offset_y, cell.location[2] + unit_cell_height / 2)
        bpy.context.collection.objects.link(new_cell)

# Create multiple chains along the X-axis
for j in range(num_chains):
    create_chain(x_location=j * x_offset)

# Create a background plane at Z = 0, aligned with the XY plane
bpy.ops.mesh.primitive_plane_add(size=500, enter_editmode=False, align='WORLD')
background_plane = bpy.context.object
background_plane.location = (0, 0, 0)  # Place it at the origin on the XY plane
background_plane.rotation_euler = (0, 0, 0)  # Ensure alignment with XY plane
background_plane.name = "Background_Plane"





# Function to create a realistic metallic material with adjustable bump strength and noise scale
def create_realistic_metallic_material(name, base_color, bump_strength=0.1, noise_scale=50.0):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Set up the base Principled BSDF node
    principled_node = nodes.get("Principled BSDF")
    principled_node.inputs["Base Color"].default_value = base_color
    principled_node.inputs["Metallic"].default_value = 0.5
    principled_node.inputs["Roughness"].default_value = 0.3

    # Add a noise texture node for roughness variation
    noise_texture = nodes.new(type="ShaderNodeTexNoise")
    noise_texture.inputs["Scale"].default_value = noise_scale  # Adjust fine-grained roughness
    noise_texture.inputs["Detail"].default_value = 10.0
    noise_texture.inputs["Roughness"].default_value = 0.5

    # Add a bump map for subtle surface texture
    bump_node = nodes.new(type="ShaderNodeBump")
    bump_node.inputs["Strength"].default_value = bump_strength  # Adjustable bump strength

    # Add a color ramp to control roughness variation
    color_ramp = nodes.new(type="ShaderNodeValToRGB")
    color_ramp.color_ramp.interpolation = 'LINEAR'
    color_ramp.color_ramp.elements[0].position = 0.4
    color_ramp.color_ramp.elements[1].position = 0.6

    # Connect noise texture to color ramp and bump node
    links.new(noise_texture.outputs["Fac"], color_ramp.inputs["Fac"])
    links.new(color_ramp.outputs["Color"], principled_node.inputs["Roughness"])
    links.new(noise_texture.outputs["Fac"], bump_node.inputs["Height"])
    links.new(bump_node.outputs["Normal"], principled_node.inputs["Normal"])

    return material

# Apply the more realistic metallic material to unit cells with higher bumpiness and fine-grain detail
realistic_metallic_material = create_realistic_metallic_material(
    "Realistic_Microchip_Metal", (0.4, 0.4, 0.4, 1), bump_strength=1.3, noise_scale=500.0)
for obj in bpy.context.collection.objects:
    if "Unit_Cell" in obj.name:
        obj.data.materials.clear()  # Clear any existing material
        obj.data.materials.append(realistic_metallic_material)

# Apply a smoother, less bumpy material with coarser texture to the background plane
background_color = (0.1, 0.1, 0.1, 1)  # Dark, non-metallic color
background_material = create_realistic_metallic_material(
    "Background_Material", background_color, bump_strength=0.6, noise_scale=10000.0)
background_plane.data.materials.clear()  # Clear any existing material
background_plane.data.materials.append(background_material)






# Positioning parameters
chain_start_x = 1.8  # X position of the first chain
chain_end_x = (num_chains - 1) * x_offset - 2  # X position of the last chain
chain_y_position = 0  # Y position for the connection

bpy.ops.mesh.primitive_cube_add(size=1)
connector = bpy.context.object
connector.scale = (x_offset+unit_cell_length/2, unit_cell_width * 2 / 2, unit_cell_height / 2)
connector.location = ((num_chains - 1) * x_offset/2, chain_y_position - y_interval / 2, unit_cell_height / 2)
connector.name = "Connector"


connector.data.materials.clear()
connector.data.materials.append(realistic_metallic_material)

print("C-shaped connector added to link the ends of the two chains.")













# Set up a uniform environment light with lower strength to emphasize shadows
bpy.context.scene.world.use_nodes = True
world_nodes = bpy.context.scene.world.node_tree.nodes

# Clear existing nodes
for node in world_nodes:
    world_nodes.remove(node)

# Add a Background node with reduced brightness for softer ambient light
background_node = world_nodes.new(type="ShaderNodeBackground")
background_node.inputs["Color"].default_value = (0.3, 0.3, 0.3, 1)  # Darker gray for subtle ambient light
background_node.inputs["Strength"].default_value = 0.3  # Lower strength to allow shadows to be more visible

# Add an Output node and link to the background
output_node = world_nodes.new(type="ShaderNodeOutputWorld")
bpy.context.scene.world.node_tree.links.new(background_node.outputs["Background"], output_node.inputs["Surface"])

# Add a Sun lamp to cast directional light and shadows
bpy.ops.object.light_add(type='SUN', align='WORLD', location=(10, -10, 20))
sun_light = bpy.context.object
sun_light.data.energy = 5.0  # Adjust brightness of the sun as needed
sun_light.rotation_euler = (0.785, 0.785, 0)  # Set angle for shadow direction
sun_light.data.shadow_soft_size = 0.5  # Adjust softness of shadows
sun_light.data.use_shadow = True  # Enable shadow casting

print("Environment light set to subtle ambient with a directional light for shadows.")


# Define camera position and rotation based on provided parameters
camera_location = (20, 20, 20)  # Location from the image
camera_rotation = (50,0,50)  # Rotation in degrees from the image

# Convert rotation from degrees to radians (Blender uses radians for rotation)
from math import radians
camera_rotation = tuple(radians(angle) for angle in camera_rotation)

# Add a camera to the scene with the specified location and rotation
bpy.ops.object.camera_add(location=camera_location, rotation=camera_rotation)
camera = bpy.context.object
camera.name = "Main_Camera"

# Set the camera as the active camera in the scene
bpy.context.scene.camera = camera

# Adjust the focal length for a suitable field of view if necessary
camera.data.lens = 125  # Set lens focal length (you can adjust this as needed)

# Align the viewport to the camera view
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        override = {'area': area, 'region': area.regions[-1], 'space': area.spaces.active}
        bpy.ops.view3d.view_camera(override)
        break

print("Camera added and positioned based on the specified parameters.")
