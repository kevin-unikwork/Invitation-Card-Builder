import numpy as np
from PIL import Image

img = Image.open('static/output/final_center_0.png').convert('RGB')
arr = np.array(img)
print('Image shape:', arr.shape)

# Find bounding box of non-white pixels
# White is [255, 255, 255]
is_not_white = np.any(arr < 250, axis=2)
y_indices, x_indices = np.where(is_not_white)

if len(x_indices) > 0:
    x_min, x_max = x_indices.min(), x_indices.max()
    y_min, y_max = y_indices.min(), y_indices.max()
    print(f'Content Bounding Box: x=[{x_min}, {x_max}], y=[{y_min}, {y_max}]')
    print(f'Content Width: {x_max - x_min}, Height: {y_max - y_min}')
else:
    print('Image is completely white.')
