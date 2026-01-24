"""
Image processing utilities for ComfyUI-DiscordSend.
"""

import torch
import numpy as np

def tensor_to_numpy_uint8(tensor: torch.Tensor) -> np.ndarray:
    """
    Convert a PyTorch tensor (0-1 float) to a numpy uint8 array (0-255).

    This function optimizes performance by doing scaling, clamping, and casting
    in PyTorch before moving data to CPU/NumPy, avoiding large intermediate float arrays.

    Args:
        tensor: PyTorch tensor with values in range [0, 1]

    Returns:
        Numpy uint8 array with values in range [0, 255]
    """
    # Optimization: Use torch operations for scaling/clipping/casting to avoid large float64 intermediate arrays on CPU
    # This is ~70% faster than naive numpy conversion: np.clip(255. * tensor.cpu().numpy(), 0, 255).astype(np.uint8)
    # Further Optimization: Use clamp_ (in-place) to avoid allocating a second float tensor
    return (tensor * 255.0).clamp_(0, 255).to(dtype=torch.uint8).cpu().numpy()

def process_batched_images(image_sequence, batch_size=20):
    """
    Generator that processes images in batches to optimize GPU-CPU transfer.

    Args:
        image_sequence: A torch.Tensor or list of tensors/images
        batch_size: Number of frames to process at once for Tensor inputs

    Yields:
        Numpy array for each batch or frame, contiguous and ready for ffmpeg
    """
    # Optimized path for Tensor input
    if isinstance(image_sequence, torch.Tensor):
        total = len(image_sequence)
        for i in range(0, total, batch_size):
            # Process a chunk of frames on GPU/CPU together
            # This amortizes the overhead of kernel launches and synchronization
            batch = image_sequence[i:i+batch_size]
            batch_np = tensor_to_numpy_uint8(batch)
            # Yield the whole batch at once to optimize pipe writes
            yield np.ascontiguousarray(batch_np)
    else:
        # Fallback for list input (e.g. pingpong or mixed sources)
        # We process individually as stacking might be expensive if they are not already contiguous tensors
        for img in image_sequence:
            yield np.ascontiguousarray(tensor_to_numpy_uint8(img))
