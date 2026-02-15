from PIL import Image, ImageEnhance
import os

# Assuming all images are in the same folder and named sequentially
image_folder = "./"
image_files = sorted([f for f in os.listdir(image_folder) if f.endswith('.png')])  # or .jpg
brightness_factor = 1.2  # >1 = brighter, <1 = darker

# Collect and sort image filenames
image_files = sorted(f for f in os.listdir(image_folder) if f.endswith('.png'))

# Load and brighten images
bright_images = []
for fname in image_files:
    img_path = os.path.join(image_folder, fname)
    img = Image.open(img_path).convert("RGB")  # Convert to RGB to avoid palette issues
    enhancer = ImageEnhance.Brightness(img)
    bright_img = enhancer.enhance(brightness_factor)
    bright_images.append(bright_img)

# Save as animated GIF
bright_images[0].save("output.gif",
                      save_all=True,
                      append_images=bright_images[1:],
                      duration=41.66, # 24fps = 41.66ms per frame
                      loop=0)