"""
BEDROT's Clip Text Preview - ComfyUI Custom Node

Displays processed text after conditional bracket preprocessing.
Works alongside BedrotCLIPTextEncode to verify conditional syntax.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
