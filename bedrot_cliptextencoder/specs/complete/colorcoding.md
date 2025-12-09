You have already implemented a new ComfyUI node named:

    BEDROT's Clip Text Encode

This node extends the existing positive CLIPTextEncode behavior with a custom conditional bracket language using `[N]`, `[K: ...]`, and `[-K: ...]`, and then forwards the processed text to the base CLIP encoder.

Your next task is to enhance the USER EXPERIENCE of BEDROT's Clip Text Encode by adding **syntax-aware color coding** (syntax highlighting) for the prompt text in this node’s UI.

================================
GOAL / HIGH-LEVEL REQUIREMENTS
================================

1. Do NOT change the existing semantics or behavior of BEDROT's Clip Text Encode.
   - The conditional bracket preprocessing and subsequent CLIP encoding MUST remain identical to the previous implementation.
2. Modify or extend the frontend / widget behavior for BEDROT's Clip Text Encode so that its `text` input field provides syntax-aware visual highlighting.
3. The highlighting must at minimum visually distinguish:
   - Parentheses-based weighting `(...)`
   - Curly-brace random-choice blocks `{...}`
   - Square-bracket conditional constructs `[...]` as defined by BEDROT’s bracket language.

The purpose of this feature is to:
- Make large, complex prompts easier to read and maintain.
- Allow the user to quickly spot malformed or unintended constructs if the text sent to CLIP is broken.

==========================
HIGHLIGHTING REQUIREMENTS
==========================

BEDROT’s Clip Text Encode should treat its `text` field as a syntax-aware editor with the following behavior:

1. **Parentheses `(...)` (CLIP weighting syntax)**
   - Highlight the entire parenthesized group `( ... )` with a distinct color or style.
   - Inside a weighted group such as `(tag:1.2)`, it is acceptable (but not required) to give the numeric weight `:1.2` a slightly different emphasis from the tag text.
   - Unbalanced parentheses should be visually indicated as a potential error (e.g., unmatched `(` or `)` underlined or colored as “warning/error”).

2. **Curly braces `{...}` (random-choice / grouping syntax)**
   - Highlight `{ ... }` blocks with a different color or style than parentheses.
   - Within `{ ... }`, highlight the pipe separator `|` distinctly, since it divides alternatives, e.g. `{face out of frame [1] | face focus [2]}`.
   - Unbalanced or malformed curly brackets (e.g. a `{` without a matching `}`) should be visually flagged as a warning.

3. **Square brackets `[...]` (BEDROT conditional language)**
   This is the custom logic you previously implemented. The syntax highlighter must be aware of all three forms:

   a. **Flag tokens `[N]`**
      - Pattern: `[N]` where `N` is a positive integer and there is no colon.
      - These must be highlighted distinctly as **“flag markers”**.
      - Example: `test [1]`, `{face out of frame [1] | face focus [2]}`.
      - All occurrences referencing the same `N` should share the same visual style class (e.g. same color family) if feasible.

   b. **Positive conditional blocks `[K: CONTENT]` with `K > 0`**
      - Pattern: `[K: ...]` where `K` is a positive integer and `...` is arbitrary content.
      - These represent “show this content when flag K is active”.
      - Highlight:
        - The leading `[K:` portion as a directive (e.g. distinct color).
        - The `CONTENT` portion as normal prompt text but with a subtle boundary indication that it is conditionally controlled.
      - Example:
        - `[2: brown hair, blue eyes, button nose]`.

   c. **Negative conditional blocks `[K: CONTENT]` with `K < 0`**
      - Pattern: `[-K: ...]` where `K` is a positive integer.
      - These represent “show this content when flag K is NOT active”.
      - Highlight:
        - The `[-K:` directive in a way that is distinguishable from the positive `[K:` blocks (e.g. different hue or style).
        - The `CONTENT` portion similar to positive blocks but with a subtle distinction, if possible.
      - Example:
        - `[-2: faceless, back turned]`.

   d. **Global nature of flags**
      - Remember: flags are evaluated globally across the entire resolved prompt.
      - While you are not required to implement full static analysis, the syntax highlighter should at least treat all `[N]` and `[N: ...]` / `[-N: ...]` instances as belonging to the same “family” for visual grouping.
      - Example of intended usage:

        test [1],
        [1: it will, get rid, of this],
        Blah blah, blah blah,
        (Random tags, heehee, {flags can also work across multiple tags [1] | random tags}),
        [1: and, it, will],
        Random tag,
        [1: get rid of, these tags too, if either, or both, words are active]

      - Every `[1]` and `[1: ...]` in this prompt should be visually linked, clearly indicating they are part of the same conditional group.

4. **Invalid / malformed constructs**
   - Tokens like `[-2]` (negative number, no colon), which are treated by the backend as invalid directives and stripped, should be visually emphasized as “likely invalid” or “non-functional”.
   - Any bracketed segment that does not clearly match one of the known patterns:
     - `[N]` (flag token)
     - `[K: ...]` where `K` is an integer (content block)
   - Should either:
     - Be rendered in a neutral style, or
     - Be marked as suspicious / warning if it looks close to a valid pattern but fails (e.g., `[2 some text]` without a colon).

5. **General styling notes**
   - Do not alter the actual prompt text the user is editing; only adjust the visual representation.
   - The highlighting must be purely cosmetic and must not change the semantics of the generated string sent into the backend logic.
   - Make sure the UI still supports multiline editing, long strings, and large prompts with many tags.
   - If the repository already uses a shared text editor / highlighting component, integrate with that rather than introducing a new, inconsistent widget.

=========================
IMPLEMENTATION GUIDANCE
=========================

- Reuse as much of the existing ComfyUI frontend infrastructure as possible.
- If a code editor component (e.g. CodeMirror, Monaco, or a custom highlighter) is already present in the codebase, prefer to configure it for BEDROT’s Clip Text Encode rather than reinventing the entire editor.
- The core text that BEDROT’s Clip Text Encode passes down to the backend should be obtained from the plain underlying string, not from any rendered HTML or markup layer used for highlighting.
- The syntax recognition can be implemented with regular expressions and/or a lightweight parser that:
  - Identifies matching pairs of `()`, `{}`, and `[]`.
  - Applies CSS classes or style spans to matched regions.
  - Handles nested or overlapping constructs in a reasonable, robust manner.

=========================
NON-GOALS
=========================

- Do NOT implement or change any of the CLIP encoding logic.
- Do NOT modify how prompts are evaluated or how `[N]`, `[K: ...]`, or `[-K: ...]` are interpreted on the backend.
- Do NOT introduce breaking changes to any existing nodes or UI components beyond extending BEDROT’s Clip Text Encode editor with syntax highlighting.

================================
EXPECTED OUTCOME
================================

At the end of this task, the repository should contain:

- The previously implemented BEDROT’s Clip Text Encode node (functional, unchanged in semantics).
- An enhanced UI for BEDROT’s Clip Text Encode in which:
  - Parentheses `(...)`, curly braces `{...}`, and square-bracket constructs `[...]` are color-coded and visually distinct.
  - `[N]` flags, `[K: ...]` positive blocks, and `[-K: ...]` negative blocks are clearly recognizable as part of the conditional system.
  - Common user mistakes (unbalanced brackets, malformed directives, stray `[-N]` flags) are visually obvious, making it easy for the user to spot and correct issues when the CLIP text encode “sends bad text”.

The goal is to make BEDROT’s Clip Text Encode a powerful, visually organized editor for large, complex prompts with heavy use of conditional and weighted syntax.
