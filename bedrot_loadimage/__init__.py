"""
BEDROT's Load Image - ComfyUI Custom Node

A LoadImage node with group-based organization for better image management.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from . import routes  # Registers API routes on import

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
