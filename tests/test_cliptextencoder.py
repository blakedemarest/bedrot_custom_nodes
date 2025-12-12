"""
Unit tests for BedrotCLIPTextEncode conditional bracket preprocessing.

Run with: pytest tests/ -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path so we can import the node
sys.path.insert(0, str(Path(__file__).parent.parent))

from bedrot_cliptextencoder.nodes import BedrotCLIPTextEncode


@pytest.fixture
def encoder():
    """Create a BedrotCLIPTextEncode instance for testing."""
    return BedrotCLIPTextEncode()


class TestFlagExtraction:
    """Tests for flag token [N] extraction and removal."""

    def test_single_flag_removed(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] hello")
        assert result == "hello"

    def test_multiple_flags_removed(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [2] [3] hello")
        assert result == "hello"

    def test_flag_in_middle(self, encoder):
        result = encoder._preprocess_conditional_brackets("hello [1] world")
        assert result == "hello world"

    def test_flag_at_end(self, encoder):
        result = encoder._preprocess_conditional_brackets("hello [1]")
        assert result == "hello"


class TestInvalidNegativeTokens:
    """Tests for invalid bare negative tokens [-N] removal."""

    def test_bare_negative_removed(self, encoder):
        result = encoder._preprocess_conditional_brackets("[-1] hello")
        assert result == "hello"

    def test_multiple_bare_negatives_removed(self, encoder):
        result = encoder._preprocess_conditional_brackets("[-1] [-2] hello")
        assert result == "hello"


class TestPositiveConditionalBlocks:
    """Tests for [K: content] blocks where K > 0."""

    def test_positive_block_kept_when_flag_active(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [1: kept]")
        assert result == "kept"

    def test_positive_block_removed_when_flag_inactive(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1: removed]")
        assert result == ""

    def test_positive_block_with_surrounding_text(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] before [1: middle] after")
        assert result == "before middle after"

    def test_multiple_positive_blocks_same_flag(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [1: a] [1: b]")
        assert result == "a b"

    def test_positive_blocks_different_flags(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [2] [1: one] [2: two] [3: three]")
        assert result == "one two"


class TestNegativeConditionalBlocks:
    """Tests for [-K: content] blocks (negative conditional)."""

    def test_negative_block_kept_when_flag_inactive(self, encoder):
        result = encoder._preprocess_conditional_brackets("[-1: kept]")
        assert result == "kept"

    def test_negative_block_removed_when_flag_active(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [-1: removed]")
        assert result == ""

    def test_negative_block_with_surrounding_text(self, encoder):
        result = encoder._preprocess_conditional_brackets("before [-1: middle] after")
        assert result == "before middle after"


class TestMixedConditionals:
    """Tests for combinations of positive and negative conditionals."""

    def test_opposite_conditionals(self, encoder):
        """[1: x] and [-1: y] should be mutually exclusive."""
        # Flag active: positive shown, negative hidden
        result = encoder._preprocess_conditional_brackets("[1] [1: shown] [-1: hidden]")
        assert result == "shown"

        # Flag inactive: positive hidden, negative shown
        result = encoder._preprocess_conditional_brackets("[1: hidden] [-1: shown]")
        assert result == "shown"

    def test_complex_mixed_scenario(self, encoder):
        """Realistic prompt with multiple flags and conditionals."""
        prompt = "[1] face focus, [1: brown hair], [-1: faceless], [2: blue eyes]"
        result = encoder._preprocess_conditional_brackets(prompt)
        assert result == "face focus, brown hair, blue eyes"


class TestNestedConditionals:
    """Tests for nested conditional blocks."""

    def test_simple_nested(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [1: outer [1: inner]]")
        assert result == "outer inner"

    def test_nested_with_different_flags(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [2] [1: outer [2: inner]]")
        assert result == "outer inner"

    def test_nested_inner_inactive(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [1: outer [2: inner]]")
        assert result == "outer"


class TestWhitespaceCleanup:
    """Tests for whitespace normalization."""

    def test_multiple_spaces_collapsed(self, encoder):
        result = encoder._preprocess_conditional_brackets("hello    world")
        assert result == "hello world"

    def test_space_before_comma_removed(self, encoder):
        result = encoder._preprocess_conditional_brackets("hello , world")
        assert result == "hello, world"

    def test_leading_trailing_trimmed(self, encoder):
        result = encoder._preprocess_conditional_brackets("  hello  ")
        assert result == "hello"

    def test_cleanup_after_removal(self, encoder):
        """Whitespace should be cleaned after conditional removal."""
        result = encoder._preprocess_conditional_brackets("[1: removed] hello")
        assert result == "hello"


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_string(self, encoder):
        result = encoder._preprocess_conditional_brackets("")
        assert result == ""

    def test_no_brackets(self, encoder):
        result = encoder._preprocess_conditional_brackets("plain text without brackets")
        assert result == "plain text without brackets"

    def test_zero_flag_ignored(self, encoder):
        """[0: content] should always be removed (edge case)."""
        result = encoder._preprocess_conditional_brackets("[0: removed]")
        assert result == ""

    def test_empty_conditional_content(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [1: ]")
        assert result == ""

    def test_flag_order_doesnt_matter(self, encoder):
        """Flags are global, so order shouldn't matter."""
        result1 = encoder._preprocess_conditional_brackets("[1: kept] [1]")
        result2 = encoder._preprocess_conditional_brackets("[1] [1: kept]")
        assert result1 == result2 == "kept"

    def test_special_characters_in_content(self, encoder):
        result = encoder._preprocess_conditional_brackets("[1] [1: (special:1.2)]")
        assert result == "(special:1.2)"


class TestRealisticPrompts:
    """Tests with realistic ComfyUI prompt patterns."""

    def test_prompt_with_weights(self, encoder):
        prompt = "[1] beautiful woman, [1: (brown hair:1.2)], [-1: bald], detailed"
        result = encoder._preprocess_conditional_brackets(prompt)
        assert result == "beautiful woman, (brown hair:1.2), detailed"

    def test_prompt_with_lora_syntax(self, encoder):
        prompt = "[1] portrait, [1: <lora:add_detail:0.8>], high quality"
        result = encoder._preprocess_conditional_brackets(prompt)
        assert result == "portrait, <lora:add_detail:0.8>, high quality"

    def test_multiline_prompt(self, encoder):
        prompt = """[1] masterpiece, best quality,
[1: detailed face],
[-1: simple background],
4k resolution"""
        result = encoder._preprocess_conditional_brackets(prompt)
        assert "detailed face" in result
        assert "simple background" not in result
