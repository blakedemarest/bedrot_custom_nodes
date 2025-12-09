"""
BEDROT's Clip Text Encode - Custom ComfyUI Node

Extends the standard CLIPTextEncode with conditional bracket preprocessing.
Implements a minimal conditional bracket language using [N] flags and [K: content] blocks.

Bracket Language:
- [N] (positive integer): Flag token that activates flag N globally
- [K: content]: Conditional block where K is an integer
  - K > 0: Content is kept only if flag K is active
  - K < 0: Content is kept only if flag abs(K) is NOT active
- [-N] (negative integer, no colon): Invalid/noise, removed from text
"""

import re


class BedrotCLIPTextEncode:
    """
    ComfyUI node that preprocesses text with conditional bracket logic
    before passing it to the standard CLIP encoder.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "dynamicPrompts": True,
                    "tooltip": "The text to be encoded. Supports [N] flags and [K: content] conditional blocks."
                }),
                "clip": ("CLIP", {
                    "tooltip": "The CLIP model used for encoding the text."
                })
            }
        }

    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "processed_text")
    OUTPUT_TOOLTIPS = (
        "A conditioning containing the embedded text used to guide the diffusion model.",
        "The processed text after conditional bracket evaluation."
    )
    FUNCTION = "encode"
    CATEGORY = "conditioning"
    DESCRIPTION = "Encodes text with conditional bracket preprocessing. Use [N] to set flags and [K: content] or [-K: content] for conditional content."

    def encode(self, clip, text):
        """
        Preprocess text with conditional brackets, then encode with CLIP.

        Args:
            clip: The CLIP model for encoding
            text: Input text with optional [N] flags and [K: content] blocks

        Returns:
            Tuple containing (CONDITIONING tensor, processed text string)
        """
        if clip is None:
            raise RuntimeError(
                "ERROR: clip input is invalid: None\n\n"
                "If the clip is from a checkpoint loader node your checkpoint "
                "does not contain a valid clip or text encoder model."
            )

        # Preprocess text to apply conditional bracket logic
        processed_text = self._preprocess_conditional_brackets(text)

        # Encode with standard CLIP logic
        tokens = clip.tokenize(processed_text)
        conditioning = clip.encode_from_tokens_scheduled(tokens)
        return (conditioning, processed_text)

    def _preprocess_conditional_brackets(self, text):
        """
        Process the conditional bracket language in the input text.

        Processing steps:
        1. Extract flag tokens [N] (positive integers only) into active_flags set
        2. Remove all flag tokens [N] from text
        3. Remove invalid bare negative tokens [-N] (no colon)
        4. Evaluate conditional blocks [K: content] based on active_flags
        5. Clean up whitespace

        Flags are GLOBAL: a flag [1] anywhere in the text activates flag 1
        for ALL [1: ...] and [-1: ...] blocks throughout the entire prompt.

        Args:
            text: Input text with bracket syntax

        Returns:
            Processed text with brackets resolved
        """
        # Step 1: Find all flag tokens [N] where N is a positive integer
        # Pattern matches [digits] where there's no colon inside
        flag_pattern = r'\[(\d+)\]'
        active_flags = set()

        for match in re.finditer(flag_pattern, text):
            flag_id = int(match.group(1))
            active_flags.add(flag_id)

        # Step 2: Remove all flag tokens [N] from text
        text = re.sub(flag_pattern, '', text)

        # Step 3: Remove invalid bare negative tokens [-N] (negative number, no colon)
        # These are noise and should not create flags
        invalid_neg_pattern = r'\[-\d+\]'
        text = re.sub(invalid_neg_pattern, '', text)

        # Step 4: Evaluate conditional blocks [K: content]
        # K can be positive or negative integer
        # Use a function to evaluate each match
        def evaluate_block(match):
            """
            Evaluate a single conditional block.

            Positive K: Keep content if K is in active_flags
            Negative K: Keep content if abs(K) is NOT in active_flags
            """
            k = int(match.group(1))
            content = match.group(2)

            if k > 0:
                # Positive ID: show content when flag K is active
                if k in active_flags:
                    return content
                else:
                    return ''
            elif k < 0:
                # Negative ID: show content when flag abs(K) is NOT active
                abs_k = abs(k)
                if abs_k not in active_flags:
                    return content
                else:
                    return ''
            else:
                # K == 0: edge case, treat as always removed
                return ''

        # Pattern for conditional blocks: [integer: content]
        # The integer can have optional + or - sign
        # Content is everything after the colon until the closing bracket
        block_pattern = r'\[([+-]?\d+):\s*(.*?)\]'
        text = re.sub(block_pattern, evaluate_block, text)

        # Step 5: Clean up whitespace
        # Collapse multiple spaces to single space
        text = re.sub(r'  +', ' ', text)
        # Remove spaces before commas
        text = re.sub(r'\s+,', ',', text)
        # Trim leading and trailing whitespace
        text = text.strip()

        return text


# Node registration for ComfyUI
NODE_CLASS_MAPPINGS = {
    "BedrotCLIPTextEncode": BedrotCLIPTextEncode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BedrotCLIPTextEncode": "BEDROT's Clip Text Encode",
}
