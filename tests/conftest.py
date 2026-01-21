"""
Pytest configuration file for tests.

This module handles test isolation by ensuring that real packages are imported
before any mocking occurs, and by providing cleanup fixtures.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Store references to real modules before any mocking
# This ensures tests that need real numpy/PIL can use them
_real_numpy = None
_real_PIL = None

def pytest_configure(config):
    """Called after command line options have been parsed and all plugins loaded."""
    global _real_numpy, _real_PIL
    
    # Import real modules and store references
    try:
        import numpy
        _real_numpy = numpy
    except ImportError:
        pass
    
    try:
        import PIL
        import PIL.Image
        import PIL.PngImagePlugin
        _real_PIL = PIL
    except ImportError:
        pass


def get_real_numpy():
    """Get the real numpy module, not a mock."""
    if _real_numpy is None:
        import numpy
        return numpy
    return _real_numpy


def get_real_PIL():
    """Get the real PIL module, not a mock."""
    if _real_PIL is None:
        import PIL
        return PIL
    return _real_PIL
