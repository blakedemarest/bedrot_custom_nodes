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


class TestTagBypass:
    """Tests for ---tag bypass syntax."""

    def test_simple_bypass(self, encoder):
        """Basic ---tag removes until comma."""
        result = encoder._preprocess_conditional_brackets("tag1, ---tag2, tag3")
        assert result == "tag1, tag3"

    def test_bypass_parentheses_group(self, encoder):
        """---(group) removes entire parenthetical group."""
        result = encoder._preprocess_conditional_brackets("tag1, ---(a, b, c), tag3")
        assert result == "tag1, tag3"

    def test_bypass_bracket_group(self, encoder):
        """---[conditional] removes entire bracket group."""
        result = encoder._preprocess_conditional_brackets("tag1, ---[1: conditional], tag3")
        assert result == "tag1, tag3"

    def test_bypass_curly_group(self, encoder):
        """---{dynamic} removes entire curly brace group."""
        result = encoder._preprocess_conditional_brackets("tag1, ---{a|b|c}, tag3")
        assert result == "tag1, tag3"

    def test_bypass_not_triggered_inside_conditional(self, encoder):
        """--- inside a conditional block should be treated as content, not trigger."""
        result = encoder._preprocess_conditional_brackets("(mouth closed [3]), [-3: ---] mouth open,")
        # Flag 3 active -> [-3: ---] removed entirely
        # The --- inside the conditional is content, not a bypass trigger
        assert "mouth open" in result
        assert "---" not in result  # The [-3: ---] block was removed

    def test_bypass_not_triggered_mid_content(self, encoder):
        """--- in middle of tag content should not trigger."""
        result = encoder._preprocess_conditional_brackets("some---text, other")
        assert result == "some---text, other"

    def test_bypass_after_newline(self, encoder):
        """--- after newline should trigger."""
        result = encoder._preprocess_conditional_brackets("tag1,\n---tag2,\ntag3")
        assert "tag1" in result
        assert "tag2" not in result
        assert "tag3" in result

    def test_bypass_at_start(self, encoder):
        """--- at start of text should trigger."""
        result = encoder._preprocess_conditional_brackets("---removed, kept")
        assert result == "kept"

    def test_bypass_with_whitespace_after_comma(self, encoder):
        """--- after comma with whitespace should trigger."""
        result = encoder._preprocess_conditional_brackets("tag1,   ---tag2, tag3")
        assert result == "tag1, tag3"


class TestBlockComments:
    """Tests for ///start...///end block comment syntax."""

    def test_simple_block_comment(self, encoder):
        """Block comments are removed."""
        result = encoder._preprocess_conditional_brackets("visible ///start hidden ///end visible")
        assert result == "visible visible"

    def test_multiple_block_comments(self, encoder):
        """Multiple block comments are all removed."""
        result = encoder._preprocess_conditional_brackets("a ///start x ///end b ///start y ///end c")
        assert result == "a b c"

    def test_multiline_block_comment(self, encoder):
        """Block comments can span multiple lines."""
        prompt = """tag1, ///start
        this is all
        commented out
        ///end tag2"""
        result = encoder._preprocess_conditional_brackets(prompt)
        assert "tag1" in result
        assert "tag2" in result
        assert "commented" not in result

    def test_block_comment_with_conditionals_inside(self, encoder):
        """Conditionals inside block comments are ignored."""
        result = encoder._preprocess_conditional_brackets("visible ///start [1] [1: hidden] ///end visible")
        assert result == "visible visible"
        assert "hidden" not in result


class TestSuppressionRules:
    """Tests for trigger/@/targets/@/ suppression syntax."""

    def test_simple_suppression(self, encoder):
        """When trigger tag is present, target tags are removed."""
        # "brown hair" is the trigger, "blonde hair" is the target
        # Both appear in the prompt, so blonde hair should be suppressed
        result = encoder._preprocess_conditional_brackets("brown hair/@/blonde hair/@/, blonde hair")
        assert "brown hair" in result
        assert "blonde hair" not in result

    def test_suppression_trigger_is_always_present(self, encoder):
        """The trigger tag itself is always present (it defines the rule)."""
        # "red hair" is trigger with target "blonde hair"
        # Since "red hair" IS in the prompt, "blonde hair" gets suppressed
        result = encoder._preprocess_conditional_brackets("red hair/@/blonde hair/@/, blonde hair")
        assert "red hair" in result
        assert "blonde hair" not in result

    def test_suppression_multiple_targets(self, encoder):
        """A trigger can suppress multiple targets."""
        result = encoder._preprocess_conditional_brackets(
            "brown hair/@/blonde hair,red hair,black hair/@/, blonde hair, red hair, other"
        )
        assert "brown hair" in result
        assert "blonde hair" not in result
        assert "red hair" not in result
        assert "other" in result

    def test_suppression_case_insensitive(self, encoder):
        """Suppression matching is case-insensitive."""
        result = encoder._preprocess_conditional_brackets(
            "Brown Hair/@/blonde hair/@/, BLONDE HAIR"
        )
        assert "Brown Hair" in result
        assert "BLONDE HAIR" not in result


class TestBracketMatching:
    """Tests for bracket matching edge cases."""

    def test_nested_parens_in_conditional(self, encoder):
        """Parentheses inside conditionals are preserved."""
        result = encoder._preprocess_conditional_brackets("[1] [1: (tag1, tag2)]")
        assert result == "(tag1, tag2)"

    def test_dynamic_prompt_in_conditional(self, encoder):
        """Dynamic prompt syntax {a|b|c} inside conditionals."""
        result = encoder._preprocess_conditional_brackets("[1] [1: {red|blue|green} hair]")
        assert result == "{red|blue|green} hair"

    def test_weight_syntax_preserved(self, encoder):
        """Weight syntax (tag:1.5) is preserved."""
        result = encoder._preprocess_conditional_brackets("[1] [1: (detailed:1.5)]")
        assert result == "(detailed:1.5)"

    def test_deeply_nested_conditionals(self, encoder):
        """Three levels of nested conditionals."""
        result = encoder._preprocess_conditional_brackets(
            "[1] [2] [3] [1: level1 [2: level2 [3: level3]]]"
        )
        assert result == "level1 level2 level3"

    def test_unbalanced_bracket_preserved(self, encoder):
        """Unbalanced brackets are kept as-is (graceful handling)."""
        # Opening bracket without close - should not crash
        result = encoder._preprocess_conditional_brackets("text [unclosed")
        assert "[unclosed" in result

    def test_mixed_brackets_in_bypass(self, encoder):
        """Bypass with nested mixed brackets."""
        result = encoder._preprocess_conditional_brackets("tag1, ---(a, (b, c), d), tag2")
        assert result == "tag1, tag2"


class TestTagBypassEdgeCases:
    """Additional edge cases for --- tag bypass."""

    def test_bypass_at_end_no_comma(self, encoder):
        """--- at end of string with no trailing comma."""
        result = encoder._preprocess_conditional_brackets("kept, ---removed")
        assert result == "kept"
        assert "removed" not in result

    def test_multiple_bypasses(self, encoder):
        """Multiple --- bypasses in same prompt."""
        result = encoder._preprocess_conditional_brackets("a, ---b, c, ---d, e")
        assert result == "a, c, e"

    def test_bypass_entire_prompt(self, encoder):
        """--- at start removes everything if no comma."""
        result = encoder._preprocess_conditional_brackets("---everything")
        assert result == ""

    def test_bypass_with_nested_brackets(self, encoder):
        """Bypass group containing nested brackets."""
        result = encoder._preprocess_conditional_brackets("tag1, ---[1: (nested, stuff)], tag2")
        assert result == "tag1, tag2"


class TestProcessingOrder:
    """Tests verifying the correct order of processing steps."""

    def test_bypass_before_conditionals(self, encoder):
        """--- bypass runs before conditional evaluation."""
        # ---[1: x] at a tag boundary removes the entire block without evaluating
        # Even though flag 1 is active, the block is bypassed entirely
        result = encoder._preprocess_conditional_brackets("[1] kept, ---[1: bypassed not evaluated]")
        assert result == "kept"
        assert "bypassed" not in result

    def test_block_comment_before_flags(self, encoder):
        """Block comments are removed before flag extraction."""
        # The [1] inside the comment should NOT activate flag 1
        result = encoder._preprocess_conditional_brackets("///start [1] ///end [1: should not appear]")
        assert "should not appear" not in result

    def test_suppression_after_conditionals(self, encoder):
        """Suppression rules apply after conditional evaluation."""
        # Define suppression inside a conditional
        result = encoder._preprocess_conditional_brackets(
            "[1] [1: brown hair/@/blonde hair/@/], blonde hair"
        )
        assert "brown hair" in result
        assert "blonde hair" not in result
