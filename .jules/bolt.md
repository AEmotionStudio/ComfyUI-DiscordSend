## 2026-01-14 - BytesIO Stream Position
**Learning:** `img.save(bytes_io, ...)` writes to the buffer and leaves the cursor at the end. Subsequent reads return 0 bytes unless `bytes_io.seek(0)` is called.
**Action:** Always verify stream position when working with in-memory buffers before passing them to IO-consuming functions.

## 2026-01-14 - Image Encoding Performance (Bolt Optimization)
**Learning:**
- **OpenCV** (`cv2.imencode`) is **~3x faster** than Pillow (`img.save`) for **PNG** encoding.
- **Pillow** is **~30% faster** than OpenCV for **JPEG** encoding and avoids extra numpy conversion overhead.
- **PyTorch tensor operations** (`(tensor * 255).to(uint8).numpy()`) are **~70% faster** than naive `numpy` conversion (`tensor.numpy() * 255`) by avoiding large float64 intermediate arrays.
**Action:** Use PyTorch for tensor preprocessing. Use OpenCV for PNG, Pillow for JPEG/WebP.
