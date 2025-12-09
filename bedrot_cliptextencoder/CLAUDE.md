# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a ComfyUI custom node subpackage that provides `BedrotCLIPTextEncode` - a CLIP text encoder with conditional bracket preprocessing.

## File Structure

```
bedrot_cliptextencoder/
  __init__.py              # Exports NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
  nodes.py                 # BedrotCLIPTextEncode implementation
  bedrotcliptextencode.md  # Original specification document
```

## Bracket Language

The node implements a conditional text system using square brackets:

**Flag Tokens** - `[N]` where N is a positive integer:
- Activates flag N globally across the entire prompt
- Removed from final text after processing
- Example: `face focus [2]` activates flag 2

**Conditional Blocks** - `[K: content]`:
- `K > 0`: Content kept only if flag K is active
- `K < 0`: Content kept only if flag abs(K) is NOT active
- Example: `[2: brown hair]` shows only when flag 2 active
- Example: `[-2: faceless]` shows only when flag 2 NOT active

**Invalid tokens** - `[-N]` (negative without colon) are removed as noise.

## Testing

1. Restart ComfyUI after changes
2. Search "BEDROT's Clip Text Encode" in node menu
3. Check ComfyUI console for import errors

Test case for bracket logic:
```
Input:  "test [1], [1: kept], [-1: removed]"
Output: "test, kept"
```

## Integration

This node calls CLIP encoding directly via `clip.tokenize()` and `clip.encode_from_tokens_scheduled()` rather than instantiating the base CLIPTextEncode node. The preprocessing step runs before these calls.
