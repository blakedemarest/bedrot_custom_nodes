"""
BEDROT's Clip Text Encode - Custom ComfyUI Node

Extends the standard CLIPTextEncode with conditional bracket preprocessing.
Implements a conditional bracket language with flags, conditional blocks, and utility syntax.

Bracket Language:
- [N] (positive integer): Flag token that activates flag N globally
- [K: content]: Conditional block where K is an integer
  - K > 0: Content is kept only if flag K is active
  - K < 0: Content is kept only if flag abs(K) is NOT active
- [-N] (negative integer, no colon): Invalid/noise, removed from text

Utility Syntax:
- ---tag: Tag bypass - disables a single comma-separated tag
- ---(tag1, tag2): Tag bypass with grouping - removes entire bracketed group
- ///start...///end: Block comments - disables entire sections
- trigger/@/target1,target2/@/: Suppression rules - when trigger present, targets removed
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
                    "tooltip": "The text to be encoded. Supports [N] flags, [K: content] blocks, ---tag bypass, ///start...///end comments, and trigger/@/targets/@/ suppression."
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
    DESCRIPTION = "Encodes text with conditional bracket preprocessing. Use [N] flags, [K: content] blocks, ---tag bypass, ///start...///end comments, and trigger/@/targets/@/ suppression."

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

    def _process_tag_bypass(self, text):
        """
        Remove tags prefixed with --- with bracket-aware grouping.

        Syntax variants:
        - ---tag: Removes until next comma
        - ---(tag1, tag2): Removes entire parenthetical group
        - ---[1: conditional]: Removes entire bracket group
        - ---{opt1|opt2}: Removes entire curly brace group

        Examples:
            Input:  "masterpiece, ---brown hair, blue eyes"
            Output: "masterpiece, blue eyes"

            Input:  "masterpiece, ---(tag1, tag2, tag3), blue eyes"
            Output: "masterpiece, blue eyes"

            Input:  "test, ---[1: conditional block], visible"
            Output: "test, visible"

        Args:
            text: Input text potentially containing ---tag patterns

        Returns:
            Text with bypassed tags removed
        """
        result = []
        i = 0
        bracket_map = {'(': ')', '[': ']', '{': '}'}

        while i < len(text):
            # Check for --- pattern
            if text[i:i+3] == '---':
                i += 3  # Skip past ---

                # Check if followed by an opening bracket
                if i < len(text) and text[i] in bracket_map:
                    open_char = text[i]
                    close_char = bracket_map[open_char]
                    end = self._find_matching_bracket(text, i + 1, open_char, close_char)

                    if end != -1:
                        # Found matching bracket - skip to after it
                        i = end + 1
                    else:
                        # Unbalanced bracket - remove to end of string
                        break

                    # Skip trailing comma and whitespace
                    while i < len(text) and text[i] in ', \t':
                        i += 1
                    continue

                # No bracket - fall back to removing until comma
                while i < len(text) and text[i] != ',':
                    i += 1
                # Skip the comma and trailing whitespace
                if i < len(text) and text[i] == ',':
                    i += 1
                while i < len(text) and text[i] in ' \t':
                    i += 1
            else:
                result.append(text[i])
                i += 1

        return ''.join(result)

    def _process_block_comments(self, text):
        """
        Remove block comments delimited by ///start and ///end.

        Syntax: ///start ... ///end
        Everything between (and including) the markers is removed.

        Example:
            Input:  "tag1, ///start disabled content ///end tag2"
            Output: "tag1,  tag2"

        Args:
            text: Input text potentially containing block comments

        Returns:
            Text with block comments removed
        """
        # Non-greedy match to handle multiple blocks correctly
        return re.sub(r'///start[\s\S]*?///end', '', text)

    def _extract_suppress_rules(self, text):
        """
        Extract inline suppression rules and remove markers from text.

        Syntax: trigger/@/target1,target2/@/
        When trigger tag is present elsewhere, target tags are suppressed.

        Example:
            Input:  "brown hair/@/blonde hair,red hair/@/, blonde hair"
            Rules:  {"brown hair": ["blonde hair", "red hair"]}
            Output: "brown hair, blonde hair" (markers removed, suppression applied later)

        Args:
            text: Input text potentially containing suppression rules

        Returns:
            Tuple of (rules_dict, cleaned_text)
            - rules_dict: {trigger: [targets]} with lowercase keys/values
            - cleaned_text: text with /@/.../@/ portions removed
        """
        rules = {}
        # Match trigger (from start or after comma) followed by /@/targets/@/
        pattern = r'(?:^|,\s*)([^,/@]+)/@/([^/@]+)/@/'

        for match in re.finditer(pattern, text):
            trigger = match.group(1).strip().lower()
            targets = [t.strip().lower() for t in match.group(2).split(',')]
            if trigger in rules:
                rules[trigger].extend(targets)
            else:
                rules[trigger] = targets

        # Remove only the /@/.../@/ portions, keep trigger tag
        cleaned = re.sub(r'/@/[^/@]+/@/', '', text)
        return rules, cleaned

    def _apply_suppress_rules(self, text, rules):
        """
        Remove tags whose triggers are present in the text.

        Args:
            text: Comma-separated tag string
            rules: Dict mapping trigger tags to lists of tags to suppress

        Returns:
            Text with suppressed tags removed
        """
        if not rules:
            return text

        tags = [t.strip() for t in text.split(',')]
        tags_lower = [t.lower() for t in tags]

        # Find which targets to suppress based on present triggers
        to_suppress = set()
        for trigger, targets in rules.items():
            if trigger in tags_lower:
                to_suppress.update(targets)

        # Filter out suppressed tags (case-insensitive matching)
        result = [t for t, t_low in zip(tags, tags_lower)
                  if t_low not in to_suppress]
        return ', '.join(result)

    def _find_matching_bracket(self, text, start_pos, open_char, close_char):
        """
        Find the position of the matching closing bracket, respecting nesting.

        Handles nested brackets of the same type and tracks other bracket types
        to properly handle mixed nesting like [1: {a|b}] or ---(tag1, [2: x]).

        Args:
            text: The text to search in
            start_pos: Position to start searching (after the opening bracket)
            open_char: The opening bracket character (e.g., '(', '[', '{')
            close_char: The closing bracket character (e.g., ')', ']', '}')

        Returns:
            Position of the matching closing bracket, or -1 if not found
        """
        depth = 1
        pos = start_pos
        bracket_pairs = {'(': ')', '[': ']', '{': '}'}

        while pos < len(text) and depth > 0:
            char = text[pos]
            if char == close_char:
                depth -= 1
            elif char == open_char:
                depth += 1
            elif char in bracket_pairs and char != open_char:
                # Different bracket type - find its matching close to skip over it
                inner_close = bracket_pairs[char]
                inner_end = self._find_matching_bracket(text, pos + 1, char, inner_close)
                if inner_end != -1:
                    pos = inner_end
            pos += 1

        return pos - 1 if depth == 0 else -1

    def _evaluate_conditional_blocks(self, text, active_flags):
        """
        Evaluate conditional blocks [K: content] using bracket-aware parsing.

        Uses bracket counting to properly handle nested content like:
        - [1: {a|b|c}] - dynamic prompts inside conditional
        - [1: (text:1.2)] - weights inside conditional
        - [1: text [2: nested]] - nested conditionals

        Args:
            text: Text with conditional blocks to evaluate
            active_flags: Set of active flag IDs

        Returns:
            Text with conditional blocks resolved based on active flags
        """
        result = []
        i = 0

        while i < len(text):
            # Look for conditional block pattern: [K: or [-K:
            match = re.match(r'\[([+-]?\d+):\s*', text[i:])
            if match and text[i] == '[':
                flag_id = int(match.group(1))
                content_start = i + match.end()

                # Find matching ] using bracket counting
                end = self._find_matching_bracket(text, content_start, '[', ']')

                if end != -1:
                    content = text[content_start:end]

                    # Evaluate based on flag state
                    if flag_id > 0:
                        # Positive: keep if flag is active
                        if flag_id in active_flags:
                            # Recursively evaluate nested conditionals
                            result.append(self._evaluate_conditional_blocks(content, active_flags))
                    elif flag_id < 0:
                        # Negative: keep if flag is NOT active
                        if abs(flag_id) not in active_flags:
                            result.append(self._evaluate_conditional_blocks(content, active_flags))
                    # flag_id == 0: always remove (edge case)

                    i = end + 1
                    continue
                else:
                    # Unbalanced bracket - treat remaining text as content
                    # Keep the [ and continue character by character
                    result.append(text[i])
                    i += 1
                    continue

            result.append(text[i])
            i += 1

        return ''.join(result)

    def _preprocess_conditional_brackets(self, text):
        """
        Process the conditional bracket language in the input text.

        Processing steps:
        0. Tag bypass (---tag)
        0.5. Block comments (///start...///end)
        1. Extract flag tokens [N] (positive integers only) into active_flags set
        2. Remove all flag tokens [N] from text
        3. Remove invalid bare negative tokens [-N] (no colon)
        4. Evaluate conditional blocks [K: content] based on active_flags
        5. Extract and apply suppression rules (/@/.../@/)
        6. Clean up whitespace

        Flags are GLOBAL: a flag [1] anywhere in the text activates flag 1
        for ALL [1: ...] and [-1: ...] blocks throughout the entire prompt.

        Args:
            text: Input text with bracket syntax

        Returns:
            Processed text with brackets resolved
        """
        # Step 0: Process tag bypass (---tag)
        text = self._process_tag_bypass(text)

        # Step 0.5: Process block comments (///start...///end)
        text = self._process_block_comments(text)

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

        # Step 4: Evaluate conditional blocks [K: content] using bracket-aware parsing
        # This handles nested content like [1: {a|b}] and [1: (text:1.2)] correctly
        text = self._evaluate_conditional_blocks(text, active_flags)

        # Step 5: Extract and apply suppression rules (/@/.../@/)
        # This happens after conditional blocks so suppression can be defined inside [K: ...]
        suppress_rules, text = self._extract_suppress_rules(text)
        text = self._apply_suppress_rules(text, suppress_rules)

        # Step 6: Clean up whitespace and punctuation
        # Collapse multiple spaces to single space
        text = re.sub(r'  +', ' ', text)
        # Remove spaces before commas
        text = re.sub(r'\s+,', ',', text)
        # Collapse multiple commas (with optional whitespace) to single comma
        text = re.sub(r',(\s*,)+', ',', text)
        # Remove leading commas
        text = re.sub(r'^\s*,\s*', '', text)
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
