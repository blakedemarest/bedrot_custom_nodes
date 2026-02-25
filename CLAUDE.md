# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a ComfyUI custom nodes package providing two nodes:
- `BEDROT's Clip Text Encode` - CLIP text encoder with conditional bracket preprocessing
- `BEDROT's Load Image` - LoadImage with group-based folder organization

## Architecture

```
bedrot_custom_nodes/
  __init__.py                    # Root package - exports NODE_CLASS_MAPPINGS from submodules
  web/
    bedrot_loadimage.js          # Frontend extension for Load Image (drag-drop, preview, groups)
  bedrot_cliptextencoder/
    __init__.py                  # Subpackage - re-exports from nodes.py
    nodes.py                     # BedrotCLIPTextEncode node implementation
    bedrotcliptextencode.md      # Original specification document
  bedrot_loadimage/
    __init__.py                  # Subpackage - re-exports from nodes.py, registers routes
    nodes.py                     # BedrotLoadImage node implementation
    routes.py                    # API routes for group/image management
    config.py                    # Unified group registry (groups.json)
    groups.json                  # Persistent config: all groups as name->path entries
```

**Node Registration Pattern**: ComfyUI discovers custom nodes via `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` dicts exported from `__init__.py`. New nodes follow this chain: `node_module.py` -> `subpackage/__init__.py` -> `bedrot_custom_nodes/__init__.py`.

## Conditional Bracket Language

The node preprocesses text before CLIP encoding using:

- **Flag tokens `[N]`**: Positive integers that activate global flags (e.g., `[1]`, `[2]`)
- **Conditional blocks `[K: content]`**: Content included/excluded based on flag state
  - Positive K: Content kept when flag K is active
  - Negative K: Content kept when flag abs(K) is NOT active
- **Invalid tokens `[-N]`**: Bare negative integers (no colon) are removed as noise

Flags are global - a flag set anywhere in the prompt affects all conditional blocks with that ID.

## Development

**Location**: `E:\PROGRAMS\ComfyUI_windows_portable\ComfyUI\custom_nodes\bedrot_custom_nodes`

**Testing**: Restart ComfyUI after code changes. Test node behavior directly in the ComfyUI workflow editor by searching for "BEDROT's Clip Text Encode" in the node menu.

**Adding New Nodes**: Create a new subpackage directory with `__init__.py` and `nodes.py`, define `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`, then import and merge them in the root `__init__.py`.

## Key Implementation Details

### BEDROT's Clip Text Encode
- `BedrotCLIPTextEncode.encode()` calls `_preprocess_conditional_brackets()` before using CLIP's tokenizer
- Processing order: extract flags -> remove flag tokens -> remove invalid negatives -> evaluate conditional blocks -> clean whitespace
- The node directly uses CLIP's `tokenize()` and `encode_from_tokens_scheduled()` rather than instantiating CLIPTextEncode

### BEDROT's Load Image
- **Group system**: All groups are name->path entries in `groups.json`. A group is just a reference to any folder on the filesystem.
- **No `image_upload` flag**: The image widget does NOT use `image_upload: True` to avoid conflicts with ComfyUI's built-in upload handler. Drag-drop is handled by the custom `onDragDrop` prototype handler in `bedrot_loadimage.js`.
- **Upload flow**: Drag-drop -> `POST /bedrot/upload/image` -> file saved to group's folder -> image list refreshed -> preview updated
- **Add Group**: Folder picker dialog -> registers folder path in `groups.json` via `POST /bedrot/browse/folder`
- **Migration**: On first load, `config.py` migrates from old `linked_folders.json` format to unified `groups.json`
