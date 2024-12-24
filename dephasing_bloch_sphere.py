import bpy
import math
import mathutils
import random
import numpy as np
# Parameters
sphere_radius = 2.0
arrow_thickness_list = [0.02,0.03,0.04,0.05,0.04,0.03,0.02]
theta_list = np.array([-0.5,-0.3,-0.15,0,0.15,0.3,0.5])*1.5 - 1
velocity_arrow_length_list = theta_list - np.mean(theta_list) + 1 
velocity_arrow_length_list = velocity_arrow_length_list / np.mean(velocity_arrow_length_list) * 0.5

output_file_path = "C:/Users/jiaka/Desktop/rendered_image.png"  # Output file path for the rendered image

# Seed for reproducibility
random.seed(42)

# Function to create the Bloch sphere with finer mesh and proper transparency
def create_bloch_sphere(radius, segments=256, rings=128):
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius, 
        location=(0, 0, 0), 
        segments=segments, 
        ring_count=rings
    )
    sphere = bpy.context.object
    sphere.name = "BlochSphere"
    
    # Create material and set up transparency using Principled BSDF
    material = bpy.data.materials.new(name="SphereMaterial")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    
    # Clear existing nodes
    for node in nodes:
        nodes.remove(node)
    
    # Add Principled BSDF node
    principled_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_bsdf.location = (0, 0)
    
    # Configure Principled BSDF for transparency
    principled_bsdf.inputs["Base Color"].default_value = (0.15, 0.33, 0.33, 0.4)  # Slight grey color
    principled_bsdf.inputs["Transmission"].default_value = 0.7  # High transmission for transparency
    principled_bsdf.inputs["Roughness"].default_value = 0.05  # Slight roughness
    principled_bsdf.inputs["Specular"].default_value = 0.3  # Specular for subtle highlights
    principled_bsdf.inputs["Alpha"].default_value = 0.2  # Control overall transparency
    
    # Connect Principled BSDF to Material Output
    material_output = nodes.new(type='ShaderNodeOutputMaterial')
    material_output.location = (200, 0)
    links.new(principled_bsdf.outputs["BSDF"], material_output.inputs["Surface"])
    
    # Assign material to sphere
    sphere.data.materials.append(material)
    
    # Set blend method to BLEND for proper transparency
    sphere.active_material.blend_method = 'BLEND'
    sphere.active_material.shadow_method = 'NONE'  # Disable shadows for the sphere

# Function to create an arrow (shaft + cone) with varying thickness and velocity
def create_arrow(start, end, arrow_thickness, velocity, name, red_material):
    direction = mathutils.Vector(end) - mathutils.Vector(start)
    length = direction.length
    direction.normalize()
    
    # Create cylinder for the arrow shaft
    bpy.ops.mesh.primitive_cylinder_add(
        radius=arrow_thickness, 
        depth=length * 0.87,  # Increased from 0.8 to 0.9 to leave just enough space for the cone
        location=(0, 0, 0)
    )
    arrow_shaft = bpy.context.object
    arrow_shaft.name = f"{name}_Shaft"

    # Position/rotate the arrow shaft - Moved closer to start point
    offset_vector = direction * (length * 0.45)  # Move shaft closer to start point
    shaft_position = mathutils.Vector(start) + offset_vector
    arrow_shaft.location = shaft_position
    arrow_shaft.rotation_mode = 'QUATERNION'
    arrow_shaft.rotation_quaternion = direction.to_track_quat('Z', 'Y')
    
    # Create the cone for the arrow tip
    cone_length = length * 0.1  # Reduced from 0.2 to 0.1 to match new proportions
    bpy.ops.mesh.primitive_cone_add(
        radius1=arrow_thickness * 2,  # a bit wider than the shaft
        radius2=0.0,
        depth=cone_length,
        location=end  # will reposition precisely below
    )
    arrow_tip = bpy.context.object
    arrow_tip.name = f"{name}_Tip"
    
    # Reposition and rotate the tip so its base aligns with the shaft end
    arrow_tip.rotation_mode = 'QUATERNION'
    arrow_tip.rotation_quaternion = direction.to_track_quat('Z', 'Y')
    
    # Move the tip back along its local Z axis by half its depth to align
    tip_offset = mathutils.Vector((0, 0, -cone_length / 2))
    tip_offset.rotate(arrow_tip.rotation_quaternion)
    arrow_tip.location = mathutils.Vector(end) + tip_offset

    # Combine the shaft and tip materials
    arrow_material = bpy.data.materials.new(name=f"{name}Material")
    arrow_material.use_nodes = True
    bsdf = arrow_material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        # Simple black color for both shaft and tip
        bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)  # Black
        bsdf.inputs["Roughness"].default_value = 0.3
        bsdf.inputs["Specular"].default_value = 0.1
    
    # Apply the same material to both parts
    arrow_shaft.data.materials.append(arrow_material)
    arrow_shaft.active_material.blend_method = 'OPAQUE'
    arrow_shaft.active_material.shadow_method = 'NONE'
    
    arrow_tip.data.materials.append(arrow_material)
    arrow_tip.active_material.blend_method = 'OPAQUE'
    arrow_tip.active_material.shadow_method = 'NONE'
    
    # --- Create Small Red Arrow Indicating Frequency ---
    # Determine the tangential direction (perpendicular to the main arrow)
    # For arrows lying on the XY-plane, a tangent is (-y, x, 0)
    # Normalize the tangent vector
    tangent_dir = mathutils.Vector((-direction.y, direction.x, 0))
    if tangent_dir.length != 0:
        tangent_dir.normalize()
    else:
        tangent_dir = mathutils.Vector((1, 0, 0))  # Default if zero length
    
    # Define small arrow length based on velocity
    small_arrow_length = velocity * 0.5  # Adjust the scaling factor as needed
    
    # Define the start and end points of the small arrow
    small_arrow_start = mathutils.Vector(end)
    small_arrow_end = small_arrow_start + tangent_dir * small_arrow_length
    
    # Create cylinder for the small arrow shaft
    bpy.ops.mesh.primitive_cylinder_add(
        radius=arrow_thickness * 0.5,  # Thinner than main arrow
        depth=small_arrow_length * 0.8,
        location=(0, 0, 0)
    )
    small_arrow_shaft = bpy.context.object
    small_arrow_shaft.name = f"{name}_Small_Shaft"
    
    # Position/rotate the small arrow shaft
    mid_point_small_shaft = (small_arrow_start + small_arrow_end) / 2
    small_arrow_shaft.location = mid_point_small_shaft
    small_arrow_shaft.rotation_mode = 'QUATERNION'
    small_arrow_shaft.rotation_quaternion = tangent_dir.to_track_quat('Z', 'Y')
    
    # Create the cone for the small arrow tip
    small_cone_length = small_arrow_length * 0.2
    bpy.ops.mesh.primitive_cone_add(
        radius1=arrow_thickness,  # Adjusted radius for small arrow
        radius2=0.0,
        depth=small_cone_length,
        location=small_arrow_end
    )
    small_arrow_tip = bpy.context.object
    small_arrow_tip.name = f"{name}_Small_Tip"
    
    # Reposition and rotate the small tip so its base aligns with the shaft end
    small_arrow_tip.rotation_mode = 'QUATERNION'
    small_arrow_tip.rotation_quaternion = tangent_dir.to_track_quat('Z', 'Y')
    
    # Move the tip back along its local Z axis by half its depth to align
    small_tip_offset = mathutils.Vector((0, 0, -small_cone_length / 2))
    small_tip_offset.rotate(small_arrow_tip.rotation_quaternion)
    small_arrow_tip.location = small_arrow_end + small_tip_offset
    
    # Assign red material to small arrow
    small_arrow_shaft.data.materials.append(red_material)
    small_arrow_shaft.active_material.blend_method = 'OPAQUE'
    small_arrow_shaft.active_material.shadow_method = 'NONE'
    
    small_arrow_tip.data.materials.append(red_material)
    small_arrow_tip.active_material.blend_method = 'OPAQUE'
    small_arrow_tip.active_material.shadow_method = 'NONE'
    
    return arrow_shaft, arrow_tip, small_arrow_shaft, small_arrow_tip

# Function to add lighting to the scene
def add_lighting():
    # Remove existing lights
    bpy.ops.object.select_by_type(type='LIGHT')
    bpy.ops.object.delete()
    
    # Add a key light - main illumination from upper right
    bpy.ops.object.light_add(type='AREA', location=(8, -2, 7))
    key_light = bpy.context.object
    key_light.name = "KeyLight"
    key_light.data.energy = 800
    key_light.data.size = 5
    key_light.rotation_euler = (math.radians(45), math.radians(15), 0)
    
    # Add a fill light - softer light from left side
    bpy.ops.object.light_add(type='AREA', location=(-6, 4, 3))
    fill_light = bpy.context.object
    fill_light.name = "FillLight"
    fill_light.data.energy = 400
    fill_light.data.size = 7
    fill_light.rotation_euler = (math.radians(30), math.radians(-20), 0)
    
    # Add a rim light - creates separation from background
    bpy.ops.object.light_add(type='AREA', location=(-2, -7, 6))
    rim_light = bpy.context.object
    rim_light.name = "RimLight"
    rim_light.data.energy = 600
    rim_light.data.size = 4
    rim_light.rotation_euler = (math.radians(60), math.radians(-30), 0)

# Function to create coordinate axis arrow
def create_axis_arrow(start, end, color, name):
    direction = mathutils.Vector(end) - mathutils.Vector(start)
    length = direction.length
    direction.normalize()
    
    # Create cylinder for the arrow shaft
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.02,  # Thin shaft for coordinate arrows
        depth=length * 0.9,
        location=(0, 0, 0)
    )
    arrow_shaft = bpy.context.object
    arrow_shaft.name = f"{name}_Shaft"

    # Position/rotate the arrow shaft
    mid_point_shaft = (mathutils.Vector(start) + mathutils.Vector(end)) / 2
    arrow_shaft.location = mid_point_shaft
    arrow_shaft.rotation_mode = 'QUATERNION'
    arrow_shaft.rotation_quaternion = direction.to_track_quat('Z', 'Y')
    
    # Create the cone for the arrow tip
    cone_length = length * 0.1
    bpy.ops.mesh.primitive_cone_add(
        radius1=0.04,  # Wider tip for visibility
        radius2=0.0,
        depth=cone_length,
        location=end
    )
    arrow_tip = bpy.context.object
    arrow_tip.name = f"{name}_Tip"
    
    # Reposition and rotate the tip
    arrow_tip.rotation_mode = 'QUATERNION'
    arrow_tip.rotation_quaternion = direction.to_track_quat('Z', 'Y')
    
    # Move the tip back along its local Z axis by half its depth to align
    tip_offset = mathutils.Vector((0, 0, -cone_length / 2))
    tip_offset.rotate(arrow_tip.rotation_quaternion)
    arrow_tip.location = mathutils.Vector(end) + tip_offset

    # Create and apply colored material
    axis_material = bpy.data.materials.new(name=f"{name}Material")
    axis_material.use_nodes = True
    bsdf = axis_material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.8
        bsdf.inputs["Roughness"].default_value = 0.2
    
    arrow_shaft.data.materials.append(axis_material)
    arrow_tip.data.materials.append(axis_material)
    
    return arrow_shaft, arrow_tip

# Function to create text label
def create_text_label(text, location, size=0.2):
    bpy.ops.object.text_add(location=location)
    text_obj = bpy.context.object
    text_obj.data.body = text
    text_obj.data.size = size
    
    # Create material for text
    text_material = bpy.data.materials.new(name=f"Text_{text}_Material")
    text_material.use_nodes = True
    bsdf = text_material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.1, 0.1, 0.1, 1.0)  # Dark grey
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Roughness"].default_value = 0.5
    
    text_obj.data.materials.append(text_material)
    
    # Rotate text to face camera
    text_obj.rotation_euler = (math.radians(90), 0, 0)
    
    return text_obj

# Function to create a curved arrow between two points
def create_curved_arrow(start_theta, end_theta, radius, thickness=0.02, name="CurvedArrow", num_points=4):
    # Create a curved path using a Bezier curve
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 32
    curve_data.bevel_depth = thickness  # Thickness of the curve
    
    # Create the curve object and link it to the scene
    curve_obj = bpy.data.objects.new(name, curve_data)
    bpy.context.scene.collection.objects.link(curve_obj)
    
    # Create a new spline in the curve
    spline = curve_data.splines.new('BEZIER')
    
    # Normalize angles to be between -π and π
    start_theta = ((start_theta + math.pi) % (2 * math.pi)) - math.pi
    end_theta = ((end_theta + math.pi) % (2 * math.pi)) - math.pi
    
    # Add points along the arc
    num_segments = num_points  # Number of segments for smooth curve
    spline.bezier_points.add(num_segments - 1)  # Add points (first one is created by default)
    
    # Calculate the angle difference and direction
    angle_diff = end_theta - start_theta
    if abs(angle_diff) > math.pi:
        # Take the shorter path
        if angle_diff > 0:
            angle_diff = angle_diff - 2 * math.pi
        else:
            angle_diff = angle_diff + 2 * math.pi
    
    for i in range(num_segments):
        t = i / (num_segments - 1)
        angle = start_theta + angle_diff * t
        
        # Calculate point position
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        point = spline.bezier_points[i]
        point.co = (x, y, 0)
        
        # Calculate tangent direction for smooth curve
        tangent_x = -radius * math.sin(angle)
        tangent_y = radius * math.cos(angle)
        tangent_length = 0.2 * radius  # Control handle length
        
        # Set handle positions for smooth curve
        point.handle_left = (
            x - tangent_x * tangent_length,
            y - tangent_y * tangent_length,
            0
        )
        point.handle_right = (
            x + tangent_x * tangent_length,
            y + tangent_y * tangent_length,
            0
        )
        point.handle_left_type = 'ALIGNED'
        point.handle_right_type = 'ALIGNED'
    
    # Create arrow tip (cone) at the end
    end_angle = start_theta + angle_diff
    tip_direction = mathutils.Vector((-math.sin(end_angle), math.cos(end_angle), 0))
    cone_length = thickness * 8
    bpy.ops.mesh.primitive_cone_add(
        radius1=thickness * 3,
        radius2=0,
        depth=cone_length,
        location=(radius * math.cos(end_angle), radius * math.sin(end_angle), 0)
    )
    tip = bpy.context.object
    tip.name = f"{name}_Tip"
    
    # Calculate rotation for the tip
    rot_quat = tip_direction.to_track_quat('-Z', 'Y')
    tip.rotation_mode = 'QUATERNION'
    tip.rotation_quaternion = rot_quat
    
    # Create and apply material
    arrow_material = bpy.data.materials.new(name=f"{name}Material")
    arrow_material.use_nodes = True
    bsdf = arrow_material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.1, 0.1, 0.1, 1.0)  # Dark grey
        bsdf.inputs["Metallic"].default_value = 0.3
        bsdf.inputs["Roughness"].default_value = 0.4
    
    curve_obj.data.materials.append(arrow_material)
    tip.data.materials.append(arrow_material)
    
    return curve_obj, tip

# --- MAIN SCRIPT EXECUTION ---

# Delete all objects in the scene for a clean start (optional)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Create Bloch sphere with finer mesh
create_bloch_sphere(sphere_radius)

# Create a red material for the small arrows
red_material = bpy.data.materials.new(name="RedMaterial")
red_material.use_nodes = True
bsdf_red = red_material.node_tree.nodes.get("Principled BSDF")
if bsdf_red:
    bsdf_red.inputs["Base Color"].default_value = (1.0, 0.0, 0.0, 1.0)  # Pure red
    bsdf_red.inputs["Roughness"].default_value = 0.3
    bsdf_red.inputs["Specular"].default_value = 0.5
    
# Create arrows with Poisson-like (Gaussian) distribution
arrows = []
for theta,arrow_thickness,velocity in zip(theta_list,arrow_thickness_list,velocity_arrow_length_list):
    x = sphere_radius * math.cos(theta)
    y = sphere_radius * math.sin(theta)
    z = 0
    start = (0, 0, 0)
    end = (x, y, z)
    arrow_shaft, arrow_tip, small_arrow_shaft, small_arrow_tip = create_arrow(
        start, end, arrow_thickness, velocity, f"Arrow{theta}", red_material
    )
    arrows.append((arrow_shaft, arrow_tip, small_arrow_shaft, small_arrow_tip))

# Create coordinate axes
axis_length = sphere_radius * 1.2  # Make axes slightly longer than sphere radius
axes = []

# X-axis (red)
x_arrow = create_axis_arrow((0,0,0), (axis_length,0,0), (0.2,0.2,0.2), "X_Axis")
x_label = create_text_label("x", (axis_length + 0.2, 0, 0))
axes.extend([*x_arrow, x_label])

# Y-axis (green)
y_arrow = create_axis_arrow((0,0,0), (0,axis_length,0), (0.2,0.2,0.2), "Y_Axis")
y_label = create_text_label("y", (0, axis_length + 0.2, 0))
axes.extend([*y_arrow, y_label])

# Z-axis (blue)
z_arrow = create_axis_arrow((0,0,0), (0,0,axis_length), (0.2,0.2,0.2), "Z_Axis")
z_label = create_text_label("z", (0, 0, axis_length + 0.2))
axes.extend([*z_arrow, z_label])

# Calculate positions of first and last arrow tips
first_theta = theta_list[0]
last_theta = theta_list[-1]
radius = sphere_radius * 1.2  # Slightly larger radius for the curved arrow
first_x = radius * math.cos(first_theta)
first_y = radius * math.sin(first_theta)
last_x = radius * math.cos(last_theta)
last_y = radius * math.sin(last_theta)

first_tip = (first_x, first_y, 0)
last_tip = (last_x, last_y, 0)

# Create curved arrow between the tips
curved_arrow, curved_tip = create_curved_arrow(theta_list[0], theta_list[-1], radius, thickness=0.015, name="PhotonNumberArrow")

# Add lighting
add_lighting()

# Set up camera  
camera_data = bpy.data.cameras.new("Camera")
camera_object = bpy.data.objects.new("Camera", camera_data)
bpy.context.scene.collection.objects.link(camera_object)
bpy.context.scene.camera = camera_object
camera_object.location = (5, -5, 5)
camera_object.rotation_euler = (math.radians(60), 0, math.radians(45))

# Cycles render settings for better quality
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 128         # Increased samples for better quality
bpy.context.scene.cycles.max_bounces = 12      # Increased bounces for better light accuracy
bpy.context.scene.cycles.caustics_reflective = False
bpy.context.scene.cycles.caustics_refractive = False
bpy.context.scene.cycles.transparent_min_bounces = 8
bpy.context.scene.cycles.transparent_max_bounces = 32

# Optimize settings for faster rendering without significant quality loss
# Uncomment below lines if render times are too long
# bpy.context.scene.cycles.samples = 64
# bpy.context.scene.cycles.max_bounces = 8

# Set resolution for high-quality render
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1920
bpy.context.scene.render.resolution_percentage = 100

# Set output file path
bpy.context.scene.render.filepath = output_file_path

# Enable transparency in render settings (if needed)
bpy.context.scene.render.film_transparent = False  # Set to True if you want a transparent background

# Set up world settings for a truly white background
bpy.context.scene.world.use_nodes = True
world_nodes = bpy.context.scene.world.node_tree.nodes
# Clear existing nodes
for node in world_nodes:
    world_nodes.remove(node)

# Add Background node
bg_node = world_nodes.new(type='ShaderNodeBackground')
bg_node.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)  # Pure white
bg_node.inputs['Strength'].default_value = 1.0  # Adjust as needed

# Add Output node
world_output = world_nodes.new(type='ShaderNodeOutputWorld')
world_output.location = (200, 0)

# Connect Background to Output
links = bpy.context.scene.world.node_tree.links
links.new(bg_node.outputs['Background'], world_output.inputs['Surface'])

# Render the image to file
bpy.ops.render.render('INVOKE_DEFAULT', animation=False, write_still=True)
print("Static visualization setup complete. Rendered image saved to:", output_file_path)
