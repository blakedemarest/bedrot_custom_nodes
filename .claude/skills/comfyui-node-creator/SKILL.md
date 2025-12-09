---
name: comfyui-node-creator
description: Create new ComfyUI custom nodes for the bedrot_custom_nodes package. Use when the user wants to add a new node, create a node subpackage, or scaffold node boilerplate.
---

# ComfyUI Node Creator

Guide for creating new custom nodes in the `bedrot_custom_nodes` package.

## Workflow

### Step 1: Gather Requirements

Before creating a node, confirm:
- **Node name**: Internal class name (e.g., `BedrotImageBlend`)
- **Display name**: UI name (e.g., `BEDROT's Image Blend`)
- **Inputs**: What data the node receives (types and metadata)
- **Outputs**: What data the node returns
- **Category**: Where it appears in the menu (e.g., `conditioning`, `image`, `loaders`)
- **Functionality**: What the node does

### Step 2: Create Subpackage Structure

Create a new directory under `bedrot_custom_nodes/`:

```
bedrot_custom_nodes/
  [new_subpackage_name]/
    __init__.py
    nodes.py
```

### Step 3: Implement nodes.py

```python
"""
[Node description and documentation]
"""

class MyNodeName:
    """Node docstring"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_name": ("TYPE", {"tooltip": "Help text"}),
            },
            "optional": {
                "optional_input": ("TYPE", {"default": value}),
            }
        }

    RETURN_TYPES = ("OUTPUT_TYPE",)
    OUTPUT_TOOLTIPS = ("Output description",)
    FUNCTION = "execute"
    CATEGORY = "conditioning"
    DESCRIPTION = "Full node description shown in UI"

    def execute(self, input_name, optional_input=None):
        # Validate inputs
        if input_name is None:
            raise RuntimeError("ERROR: input_name is invalid: None")

        # Process
        result = self._process(input_name)

        # Return tuple matching RETURN_TYPES
        return (result,)

    def _process(self, data):
        """Helper method for processing logic"""
        return data

# Node registration
NODE_CLASS_MAPPINGS = {
    "MyNodeName": MyNodeName,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MyNodeName": "BEDROT's My Node",
}
```

### Step 4: Create Subpackage __init__.py

```python
"""
[Subpackage description]
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
```

### Step 5: Update Root __init__.py

Merge the new mappings into the root package:

```python
"""
BEDROT Custom Nodes for ComfyUI
"""

from .bedrot_cliptextencoder import NODE_CLASS_MAPPINGS as CLIP_MAPPINGS
from .bedrot_cliptextencoder import NODE_DISPLAY_NAME_MAPPINGS as CLIP_DISPLAY
from .new_subpackage import NODE_CLASS_MAPPINGS as NEW_MAPPINGS
from .new_subpackage import NODE_DISPLAY_NAME_MAPPINGS as NEW_DISPLAY

NODE_CLASS_MAPPINGS = {**CLIP_MAPPINGS, **NEW_MAPPINGS}
NODE_DISPLAY_NAME_MAPPINGS = {**CLIP_DISPLAY, **NEW_DISPLAY}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
```

### Step 6: Test

1. Restart ComfyUI
2. Search for your display name in the node menu
3. Check console for import errors

---

## Reference

### Input Types

| Type | Description | Example |
|------|-------------|---------|
| `STRING` | Text input | `("STRING", {"multiline": True})` |
| `INT` | Integer | `("INT", {"default": 1, "min": 0, "max": 100})` |
| `FLOAT` | Decimal | `("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01})` |
| `CLIP` | CLIP model | `("CLIP", {"tooltip": "CLIP model"})` |
| `MODEL` | Diffusion model | `("MODEL", {})` |
| `CONDITIONING` | Conditioning tensor | `("CONDITIONING", {})` |
| `IMAGE` | Image tensor | `("IMAGE", {})` |
| `LATENT` | Latent tensor | `("LATENT", {})` |
| `[list]` | Dropdown | `(["opt1", "opt2"], {"default": "opt1"})` |

### Input Metadata Options

| Option | Type | Description |
|--------|------|-------------|
| `default` | any | Default value |
| `min` | number | Minimum value (INT/FLOAT) |
| `max` | number | Maximum value (INT/FLOAT) |
| `step` | number | Increment step (INT/FLOAT) |
| `multiline` | bool | Multi-line text input |
| `dynamicPrompts` | bool | Enable dynamic prompt syntax |
| `tooltip` | string | Help text shown on hover |
| `display` | string | UI element type (e.g., `"slider"`) |

### Class Attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| `RETURN_TYPES` | Yes | Tuple of output types |
| `FUNCTION` | Yes | Method name to call |
| `CATEGORY` | Yes | Menu category |
| `DESCRIPTION` | No | Full description |
| `OUTPUT_TOOLTIPS` | No | Tuple of output help text |
| `RETURN_NAMES` | No | Custom output labels |
| `OUTPUT_IS_LIST` | No | Mark outputs as lists |

### Common Categories

- `conditioning` - Text/prompt processing
- `image` - Image manipulation
- `loaders` - Model loading
- `sampling` - Sampling operations
- `latent` - Latent space operations
- `mask` - Mask operations

### Error Handling Pattern

```python
def execute(self, clip, text):
    if clip is None:
        raise RuntimeError(
            "ERROR: clip input is invalid: None\n\n"
            "If the clip is from a checkpoint loader node your checkpoint "
            "does not contain a valid clip or text encoder model."
        )
    # ... rest of implementation
```

---

## Templates

### Basic Node

```python
class BedrotBasicNode:
    """Basic node template"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "tooltip": "Input text"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_TOOLTIPS = ("Processed text",)
    FUNCTION = "process"
    CATEGORY = "conditioning"
    DESCRIPTION = "Basic text processing node"

    def process(self, text):
        result = text.upper()
        return (result,)

NODE_CLASS_MAPPINGS = {"BedrotBasicNode": BedrotBasicNode}
NODE_DISPLAY_NAME_MAPPINGS = {"BedrotBasicNode": "BEDROT's Basic Node"}
```

### Node with Optional Inputs

```python
class BedrotOptionalNode:
    """Node with optional parameters"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Input image"}),
            },
            "optional": {
                "strength": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "Effect strength"
                }),
                "mode": (["normal", "multiply", "screen"], {
                    "default": "normal",
                    "tooltip": "Blend mode"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "process"
    CATEGORY = "image"

    def process(self, image, strength=1.0, mode="normal"):
        # Process with optional parameters
        return (image,)

NODE_CLASS_MAPPINGS = {"BedrotOptionalNode": BedrotOptionalNode}
NODE_DISPLAY_NAME_MAPPINGS = {"BedrotOptionalNode": "BEDROT's Optional Node"}
```

### Subpackage __init__.py

```python
"""
BEDROT's [Node Name] - ComfyUI Custom Node

[Brief description of what this node does]
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
```
