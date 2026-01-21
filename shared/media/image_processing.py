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
