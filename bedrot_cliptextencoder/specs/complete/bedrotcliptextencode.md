You are an expert Python developer working inside a ComfyUI-compatible repository that already contains the standard positive CLIPTextEncode node.

Your task is to implement a NEW node that acts clip text encode, but extends the behavior of the existing positive CLIP text encoder with custom conditional bracket logic, and expose it in the UI as:

    BEDROT's Clip Text Encode

Do NOT remove or break the existing CLIPTextEncode node. Instead, create an additional node that reuses its functionality after performing a custom text preprocessing step.

================================
GOAL / HIGH-LEVEL REQUIREMENTS
================================

1. Locate the existing positive CLIP text encode node (typically `CLIPTextEncode` in `nodes.py` or equivalent).
2. Implement a new node class that:
   - Accepts the same inputs as the existing positive CLIPTextEncode node (at minimum: `clip`, `text`).
   - Performs additional preprocessing on `text` to apply a custom conditional bracket language (detailed below).
   - Calls the original CLIPTextEncode logic on the processed text.
   - Outputs a standard `CONDITIONING` tensor that can be wired anywhere the original node is used.
3. Register the new node with:
   - A clear class name, e.g. `BedrotCLIPTextEncode`.
   - A display name in `NODE_DISPLAY_NAME_MAPPINGS` exactly as: `BEDROT's Clip Text Encode`.
   - A category consistent with other CLIP/conditioning nodes (e.g. `"conditioning"`).

The new node must preserve all existing CLIP prompt semantics (including `()` weight syntax and `{}` random blocks) as implemented by the base CLIPTextEncode node. The only change is the additional preprocessing of the prompt string before it is passed to the base encoder.

==============================
CUSTOM BRACKET LANGUAGE SPEC
==============================

The new node must implement a minimal “conditional bracket” language that uses ONLY square brackets `[]` and integers. This logic operates on the FINAL resolved text string in the node’s `text` parameter, before sending it to the underlying CLIP encoder.

There are two kinds of bracket constructs:

1. FLAG TOKENS (“branch markers”)
2. CONDITIONAL BLOCKS (“content blocks”)

They are distinguished by whether they contain a colon `:`.

----------------------
1. FLAG TOKENS
----------------------

Syntax (flags):

    [N]

Where:
- `N` is a POSITIVE integer (no sign, digits only, e.g. `[1]`, `[2]`, `[10]`).
- These tokens are used as markers to indicate which “mode” or “branch” is active in a given resolved prompt.
- They will usually appear inside random-choice branches, e.g.:

    { face out of frame [1] | face focus [2] }

Semantics:

1. Scan the entire prompt text for tokens that match exactly the pattern `[N]` (no colon, no sign).
2. For each such token:
   - Parse `N` as an integer.
   - Add `N` to a set called `active_flags`.
3. Remove ALL of these `[N]` flag tokens from the text before further processing.

Notes:
- Only positive integers should be treated as flags.
- A token like `[-2]` (negative number, no colon) MUST NOT be treated as a flag and MUST be removed from the text as an invalid directive / noise.
- Do not treat arbitrary `[...]` as flags; only match `[N]` where N is one or more digits and there is no colon inside.

----------------------
2. CONDITIONAL BLOCKS
----------------------

Syntax (blocks):

    [K: some content here]

Where:
- `K` is an integer, and MAY be positive or negative (e.g. `2`, `-2`, `5`, `-5`).
- The first thing after `[` up to the colon `:` is the integer ID.
- Everything after the first colon up to the matching closing `]` is the block content.
- The content may contain any normal prompt text, including parentheses `()`, curly braces `{}`, commas, booru tags, etc.

Examples:

    [2: brown hair, blue eyes, button nose]
    [-2: faceless, back turned]
    [10: extremely busy background]

Semantics:

Let `active_flags` be the set of positive integers collected from FLAG TOKENS as described above.

For each block `[K: CONTENT]`:

- Parse `K` as an integer (allow leading `+` or `-`, but no decimal).
- If `K > 0` (positive ID):
    - KEEP the block content `CONTENT` **only if** `K` is in `active_flags`.
    - Otherwise, REMOVE the entire block (including brackets and content).
- If `K < 0` (negative ID):
    - Let `A = abs(K)`.
    - KEEP the block content `CONTENT` **only if** `A` is **NOT** in `active_flags`.
    - Otherwise, REMOVE the entire block.

After evaluating a block:
- Replace `[K: CONTENT]` with either:
  - `CONTENT` (when the block is kept), or
  - an empty string (when the block is removed).

This gives:

- Positive IDs: “show this when MODE N is active”
- Negative IDs: “show this when MODE N is NOT active”

If there are no active flags (i.e., `active_flags` is empty):
- Any `[K: ...]` with `K > 0` is removed.
- Any `[K: ...]` with `K < 0` is kept, because `abs(K)` is not in `active_flags`.

---------------------------------------------
3. FLAGS ARE GLOBAL ACROSS MULTIPLE BRACKETS
---------------------------------------------

Flags are GLOBAL within a single resolved prompt string:

- A given flag ID (e.g. `1`) can be referenced in multiple places.
- Any occurrence of `[1]` anywhere in the text activates flag `1`.
- All blocks whose ID is `1` or `-1` will be evaluated against this same global `active_flags` set.

In other words, flags can work across multiple tags and multiple conditional blocks.

Example:

Prompt text:

    test [1],
    [1: it will, get rid, of this],
    Blah blah, blah blah,
    (Random tags, heehee, {flags can also work across multiple tags [1] | random tags}),
    [1: and, it, will],
    Random tag,
    [1: get rid of, these tags too, if either, or both, words are active]

Processing for this example:

- Both `test [1]` and `flags can also work across multiple tags [1]` contribute the same flag ID:
    - `active_flags = {1}`.
- Every `[1: ...]` block in the prompt is evaluated against this same flag set.
- Because flag `1` is active, ALL `[1: ...]` blocks are treated consistently:
    - If the ID is `1` (positive) → block content is kept.
    - If the ID were `-1` (negative) → block content would be kept only when flag `1` is NOT active.

This demonstrates that a single flag ID can drive multiple conditional regions spread out across the prompt.

--------------------------
4. EXAMPLES (MUST MATCH)
--------------------------

Example 1: Face focus vs face out of frame

Input text in the node:

    masterpiece, best quality,
    [2: brown hair, blue eyes, button nose],
    [-2: faceless, back turned],
    { face out of frame [1] | face focus [2] },
    1girl, alley, neon, night

Case A: random choice resolves to `face out of frame [1]`

Resolved text BEFORE preprocessing:

    masterpiece, best quality,
    [2: brown hair, blue eyes, button nose],
    [-2: faceless, back turned],
    face out of frame [1],
    1girl, alley, neon, night

Processing:

- FLAG TOKENS:
    - `[1]` → `active_flags = {1}`
    - Remove `[1]` from the text.
- CONDITIONAL BLOCKS:
    - `[2: ...]`:
        - `K = 2` (positive).
        - 2 ∉ active_flags → REMOVE block.
    - `[-2: faceless, back turned]`:
        - `K = -2`, `A = 2`.
        - 2 ∉ active_flags → KEEP block as `faceless, back turned`.

Final text passed to CLIP:

    masterpiece, best quality,
    faceless, back turned,
    face out of frame,
    1girl, alley, neon, night

Case B: random choice resolves to `face focus [2]`

Resolved text BEFORE preprocessing:

    masterpiece, best quality,
    [2: brown hair, blue eyes, button nose],
    [-2: faceless, back turned],
    face focus [2],
    1girl, alley, neon, night

Processing:

- FLAG TOKENS:
    - `[2]` → `active_flags = {2}`
    - Remove `[2]`.
- CONDITIONAL BLOCKS:
    - `[2: ...]`:
        - `K = 2` (positive).
        - 2 ∈ active_flags → KEEP as `brown hair, blue eyes, button nose`.
    - `[-2: faceless, back turned]`:
        - `K = -2`, `A = 2`.
        - 2 ∈ active_flags → REMOVE this block.

Final text passed to CLIP:

    masterpiece, best quality,
    brown hair, blue eyes, button nose,
    face focus,
    1girl, alley, neon, night

This exact behavior MUST be preserved.

--------------------------
5. EDGE CASES & CLEANUP
--------------------------

1. Bare negative tokens like `[-2]` (no colon):
   - Must NOT create flags.
   - Must be removed from the text entirely.
2. Stray whitespace:
   - After all replacements, it is acceptable to normalize some spacing:
       - Collapse double spaces `"  "` to single `" "`.
       - Remove spaces before commas (e.g., `" ,"` → `","`).
       - Trim whitespace at start and end.
   - Do NOT otherwise alter the prompt content.
3. Non-matching brackets:
   - If a bracket pattern does not strictly match `[N]` or `[integer: ...]`, leave it as-is.
   - Do not try to “fix” arbitrary user text; be conservative and only transform known patterns.

=========================
INTEGRATION WITH CLIP
=========================

After conditional bracket processing is complete:

1. The resulting cleaned string MUST be passed into the original CLIPTextEncode logic, so that:
   - Parentheses `()` weighting, curly brace `{}` random blocks, and any other built-in CLIP prompt semantics behave exactly as they currently do.
2. You should instantiate or call the existing CLIPTextEncode implementation rather than re-implementing CLIP encoding yourself.
   - For example, create an instance of the original node and call its `encode` method with the modified `text` while passing `clip` through unchanged.

The new node should therefore conceptually do:

    - Input: clip, text
    - Step 1: parse text for [N], [K: ...] according to the rules above
    - Step 2: produce cleaned_text with conditional blocks applied
    - Step 3: call original CLIPTextEncode(clip, cleaned_text)
    - Output: CONDITIONING (as returned by the base node)

================================
NAMING & REGISTRATION DETAILS
================================

- Class name suggestion: `BedrotCLIPTextEncode`
- Return types: same as CLIPTextEncode (e.g. `("CONDITIONING",)`).
- Return name(s): e.g. `("conditioning",)`.
- Category: `"conditioning"` (or match the category of CLIPTextEncode in this repo).
- In `NODE_CLASS_MAPPINGS`, register the new class under a distinct key, e.g.:

      "BedrotCLIPTextEncode": BedrotCLIPTextEncode

- In `NODE_DISPLAY_NAME_MAPPINGS`, register the display name EXACTLY as:

      "BedrotCLIPTextEncode": "BEDROT's Clip Text Encode"

Make sure the node appears as a separate option in the ComfyUI node search, and that using it does NOT change the behavior of any existing graph that uses the original CLIPTextEncode node.

================================
QUALITY EXPECTATIONS
================================

- The implementation must be robust against long prompts with many booru-style tags, multiple `{}` random blocks, and mixed use of `()`, `{}`, and `[]`.
- The code should be clean, readable, and commented where necessary, especially around the text parsing logic (regex or manual parsing).
- Include brief comments explaining:
    - How flags are collected.
    - How conditional blocks are evaluated.
    - The meaning of positive vs negative block IDs.
    - That flags are global across the entire resolved prompt and affect all `[K: ...]` / `[-K: ...]` blocks sharing the same ID.

Your final result should be a working ComfyUI node named “BEDROT's Clip Text Encode” that users can drop in as a direct replacement for the positive CLIPTextEncode node, with the added power of the `[N]` / `[K: ...]` / `[-K: ...]` conditional bracket language and global flags across multiple brackets.
