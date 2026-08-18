"""Pilot-only workaround for a trainer with no --device override.

The public trainer automatically selects Apple MPS, while the installed
PyTorch/Transformers attention implementation cannot train with dropout on MPS.
Placing this directory first on PYTHONPATH makes the device probe choose CPU.
This is not a proposed production implementation.
"""

import torch


if hasattr(torch.backends, "mps"):
    torch.backends.mps.is_available = lambda: False
