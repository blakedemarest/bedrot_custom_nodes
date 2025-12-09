# Agent Task: Create BEDROT ClipText Preview Node

## Goal
Create a new observability node `BedrotCLIPTextPreview` that shows the final processed text after all bracket preprocessing logic is applied. This node works in conjunction with `BedrotCLIPTextEncode` - users feed the same text input to both nodes. The preview node displays what text would be sent to CLIP, allowing verification that conditional syntax is functioning correctly.

---

## Codebase Context

### Package Structure
```
bedrot_custom_nodes/
  __init__.py                    # Root package - exports NODE_CLASS_MAPPINGS
  CLAUDE.md                      # Project documentation
  bedrot_cliptextencoder/
    __init__.py                  # Subpackage - re-exports from nodes.py
    nodes.py                     # BedrotCLIPTextEncode implementation
```

### How BedrotCLIPTextEncode Preprocesses Text

The encoder's `_preprocess_conditional_brackets()` method implements a conditional bracket language:

1. **Flag Extraction**: Pattern `\[(\d+)\]` finds all `[N]` tokens (positive integers), adds them to an `active_flags` set
2. **Flag Removal**: All `[N]` markers are stripped from text
3. **Invalid Token Removal**: Pattern `\[-\d+\]` removes bare `[-N]` tokens (negative without colon)
4. **Conditional Block Evaluation**: Pattern `\[([+-]?\d+):\s*(.*?)\]` evaluates `[K: content]` blocks:
   - K > 0: Content kept only if flag K is active
   - K < 0: Content kept only if abs(K) is NOT active
5. **Whitespace Cleanup**: Collapses multiple spaces, removes pre-comma spaces, trims

### Text Flow Through System
```
User Input -> ComfyUI Dynamic Prompts ({a|b|c} -> b) -> Bracket Preprocessing -> CLIP Tokenizer
```

The preview node needs to show text after bracket preprocessing (same point the encoder sends to tokenizer).

---

## Intended Workflow
```
[Primitive/Text Input]
        |
        +---> [BedrotCLIPTextEncode] ---> CONDITIONING ---> KSampler
        |
        +---> [BedrotCLIPTextPreview] ---> displays processed text in UI
```

Both nodes receive the same text. The preview node mirrors the encoder's preprocessing logic and displays the result.

---

## Requirements

1. Create new node `BedrotCLIPTextPreview` in a new subpackage `bedrot_cliptextencoder_preview/`
2. The preview node must use identical preprocessing logic to `BedrotCLIPTextEncode`
3. Input: `text` (STRING, multiline, dynamicPrompts=True)
4. Output: Display processed text in the node's UI panel (use ComfyUI's `OUTPUT_NODE = True` and return `{"ui": {"text": [result]}, "result": (result,)}` pattern)
5. Register the new node in root `__init__.py` by merging NODE_CLASS_MAPPINGS from both subpackages

---

## Technical Notes

- Copy the `_preprocess_conditional_brackets()` function to the new subpackage (or extract to shared module)
- ComfyUI displays UI output when a node returns `{"ui": {...}, "result": (...)}` dict with `OUTPUT_NODE = True`
- Node registration follows the pattern in existing `bedrot_cliptextencoder/__init__.py`
