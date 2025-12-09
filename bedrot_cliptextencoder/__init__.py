"""
BEDROT's Clip Text Encode - ComfyUI Custom Node

A CLIP text encoder with conditional bracket preprocessing.
Supports [N] flag tokens and [K: content] conditional blocks.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
