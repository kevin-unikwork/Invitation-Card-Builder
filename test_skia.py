import skia
import numpy as np

# Create an array that is 100 tall, 50 wide
arr = np.zeros((100, 50, 4), dtype=np.uint8)
arr[:, :, 3] = 255 # alpha
arr[0:10, 0:10, 0] = 255 # red square in top left

img = skia.Image.fromarray(arr, colorType=skia.ColorType.kRGBA_8888_ColorType)
print('Numpy shape:', arr.shape)
print('Skia Image w:', img.width(), 'h:', img.height())
img.save('test_skia.png')
