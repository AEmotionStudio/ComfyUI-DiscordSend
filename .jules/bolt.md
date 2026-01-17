## 2026-01-14 - BytesIO Stream Position
**Learning:** `img.save(bytes_io, ...)` writes to the buffer and leaves the cursor at the end. Subsequent reads return 0 bytes unless `bytes_io.seek(0)` is called.
**Action:** Always verify stream position when working with in-memory buffers before passing them to IO-consuming functions.

## 2026-01-14 - Image Encoding Performance (Bolt Optimization)
**Learning:**
- **OpenCV** (`cv2.imencode`) is **~3x faster** than Pillow (`img.save`) for **PNG** encoding.
- **Pillow** is **~30% faster** than OpenCV for **JPEG** encoding and avoids extra numpy conversion overhead.
- **PyTorch tensor operations** (`(tensor * 255).to(uint8).numpy()`) are **~70% faster** than naive `numpy` conversion (`tensor.numpy() * 255`) by avoiding large float64 intermediate arrays.
**Action:** Use PyTorch for tensor preprocessing. Use OpenCV for PNG, Pillow for JPEG/WebP.

## 2026-01-14 - Tensor to Numpy Conversion Optimization
**Learning:**
- Naive conversion `np.clip(255. * tensor.cpu().numpy(), 0, 255).astype(np.uint8)` creates large intermediate float arrays on CPU.
- Performing scaling, clamping, and casting on the tensor *before* moving to CPU (`(tensor * 255.0).clamp(0, 255).to(dtype=torch.uint8).cpu().numpy()`) is significantly faster and more memory efficient.
**Action:** Always process tensors (scale/clamp/cast) before converting to numpy/CPU when preparing images for PIL/OpenCV.

## 2026-01-14 - Avoid Redundant PIL to Numpy Conversion
**Learning:**
- Converting a large PIL Image back to a Numpy array (`np.array(img)`) is surprisingly slow (measured ~500ms for 4K image).
- When the PIL Image wraps an existing Numpy array and hasn't been modified (e.g. resized), reusing the original Numpy array avoids this overhead completely.
**Action:** Track modifications to PIL images (like resizing) and reuse the source Numpy array for OpenCV operations if no modifications occurred.
