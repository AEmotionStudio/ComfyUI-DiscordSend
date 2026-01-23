import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dependencies before importing nodes.video_node
mock_torch = MagicMock()
sys.modules["torch"] = mock_torch
sys.modules["folder_paths"] = MagicMock()
sys.modules["comfy"] = MagicMock()
sys.modules["comfy.cli_args"] = MagicMock()
sys.modules["comfy.utils"] = MagicMock()
sys.modules["server"] = MagicMock()

# Mock PIL
mock_pil = MagicMock()
sys.modules["PIL"] = mock_pil
sys.modules["PIL.Image"] = mock_pil
sys.modules["PIL.PngImagePlugin"] = MagicMock()
sys.modules["cv2"] = MagicMock()

# Mock shared modules
mock_shared = MagicMock()
sys.modules["shared"] = mock_shared
sys.modules["shared.media"] = MagicMock()
sys.modules["shared.media.image_processing"] = MagicMock()

# Define the function logic we want to verify (simulating the generator consumer)
def consume_chunks(chunks):
    pil_images = []
    for chunk in chunks:
        # Proposed logic for nodes/video_node.py
        if len(chunk.shape) == 4:
            # Batched chunk (B, H, W, C)
            for i in range(chunk.shape[0]):
                pil_images.append(f"image_from_batch_{i}")
        else:
            # Single frame chunk (H, W, C)
            pil_images.append("image_from_single")
    return pil_images

class TestPILBatchOptimization(unittest.TestCase):

    def test_consumer_logic_mixed_chunks(self):
        """Test that the consumer logic correctly handles mixed 4D and 3D chunks."""

        # 1. 4D Chunk (Batch of 2)
        chunk_batch = np.zeros((2, 10, 10, 3), dtype=np.uint8)

        # 2. 3D Chunk (Single frame) - simulating what happens if generator yields single frame
        chunk_single = np.zeros((10, 10, 3), dtype=np.uint8)

        chunks = [chunk_batch, chunk_single]

        # Run consumer logic
        images = consume_chunks(chunks)

        # Verify results
        # Should have 2 from batch + 1 from single = 3 images
        self.assertEqual(len(images), 3)
        self.assertEqual(images[0], "image_from_batch_0")
        self.assertEqual(images[1], "image_from_batch_1")
        self.assertEqual(images[2], "image_from_single")

    def test_process_batched_images_integration(self):
        """
        Verify that we can import and run process_batched_images with mocks,
        and that it chunks correctly.
        """
        # Import needs to happen after mocks are set up
        from nodes.video_node import process_batched_images

        # Setup mock tensor
        # We need to make sure isinstance(t, torch.Tensor) works

        tensor_len = 5
        batch_size = 2

        # Mock slicing
        def getitem(self, idx):
            # idx is a slice object
            start = idx.start
            stop = idx.stop
            if stop > tensor_len:
                stop = tensor_len
            size = stop - start
            return f"slice_{size}"

        # Create a class with __len__ and __getitem__ defined
        class MockTensor:
            def __len__(self):
                return tensor_len
            def __getitem__(self, idx):
                return getitem(self, idx)

        mock_torch.Tensor = MockTensor

        mock_tensor = mock_torch.Tensor()

        # Mock tensor_to_numpy_uint8 to return numpy arrays of appropriate shape
        # It needs to return (Size, H, W, C)
        with patch('nodes.video_node.tensor_to_numpy_uint8') as mock_t2n:
            def side_effect(slice_obj):
                # parse size from string "slice_N"
                size = int(slice_obj.split('_')[1])
                return np.zeros((size, 10, 10, 3), dtype=np.uint8)

            mock_t2n.side_effect = side_effect

            # Run generator
            generator = process_batched_images(mock_tensor, batch_size=batch_size)
            chunks = list(generator)

            # Expected:
            # 5 items, batch 2
            # 1. Size 2
            # 2. Size 2
            # 3. Size 1

            self.assertEqual(len(chunks), 3)
            self.assertEqual(chunks[0].shape[0], 2)
            self.assertEqual(chunks[1].shape[0], 2)
            self.assertEqual(chunks[2].shape[0], 1)

            # Verify they are all 4D arrays (B, H, W, C)
            for c in chunks:
                self.assertEqual(len(c.shape), 4)

if __name__ == '__main__':
    unittest.main()
