## 2024-03-24 - Image Encoding Performance
**Learning:** `cv2.imencode` is ~4x faster than PIL's `save` for PNG images, even with low compression levels. However, PIL is ~30% faster for JPEG and avoids the overhead of converting PIL images back to Numpy/OpenCV format.
**Action:** Use a hybrid approach: Stick to OpenCV for PNG encoding, but use PIL directly for JPEG/WebP to save memory and CPU cycles on conversion.
