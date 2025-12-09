# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a ComfyUI custom nodes package that provides `BEDROT's Clip Text Encode` - a CLIP text encoder with conditional bracket preprocessing. The node extends standard CLIPTextEncode by adding a conditional bracket language for dynamic prompt control.

## Architecture

```
bedrot_custom_nodes/
  __init__.py                    # Root package - exports NODE_CLASS_MAPPINGS from submodules
  bedrot_cliptextencoder/
    __init__.py                  # Subpackage - re-exports from nodes.py
    nodes.py                     # BedrotCLIPTextEncode node implementation
    bedrotcliptextencode.md      # Original specification document
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

- `BedrotCLIPTextEncode.encode()` calls `_preprocess_conditional_brackets()` before using CLIP's tokenizer
- Processing order: extract flags -> remove flag tokens -> remove invalid negatives -> evaluate conditional blocks -> clean whitespace
- The node directly uses CLIP's `tokenize()` and `encode_from_tokens_scheduled()` rather than instantiating CLIPTextEncode
