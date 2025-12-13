# Prompting Guide for BEDROT's Clip Text Encode

Welcome! This guide covers all the special syntax you can use when writing prompts with BEDROT's Clip Text Encode node. You'll learn both ComfyUI's built-in features and the conditional bracket system unique to this node.

---

## ComfyUI Native Syntax

These features work in any ComfyUI CLIP text encoder, including this one.

### Weighting with Parentheses

Control how strongly the model pays attention to specific words or phrases.

| Syntax | Effect |
|--------|--------|
| `(word)` | 1.1x emphasis (default boost) |
| `(word:1.5)` | Custom weight (1.5x emphasis) |
| `((word))` | Stacked emphasis (~1.21x) |
| `(phrase here:0.8)` | Reduced weight (de-emphasis) |

**Examples:**
```
(masterpiece:1.2), best quality, 1girl
detailed background, (blurry:0.5)
((highly detailed face)), beautiful eyes
```

The number after the colon is a multiplier. Values above 1.0 increase emphasis, values below 1.0 decrease it. You can nest parentheses for compounding effect.

---

### Random Choice with Curly Braces

Pick one option randomly from a set of alternatives. Great for generating variations.

**Syntax:** `{option1|option2|option3}`

**Examples:**
```
1girl with {blonde|brunette|red} hair
{sunny day|rainy night|golden hour} lighting
portrait of a {happy|serious|mysterious} woman
```

Each time you queue a prompt, one option is selected at random. This is handled by ComfyUI's dynamic prompts feature before the text reaches the encoder.

---

### Escape Characters

If you need literal parentheses in your prompt without triggering weight syntax:

| Syntax | Result |
|--------|--------|
| `\(` | Literal `(` |
| `\)` | Literal `)` |

**Example:**
```
photo of a sign saying \(hello world\)
```

---

### Embeddings

Load trained embedding files directly in your prompt.

**Syntax:** `embedding:filename`

**Example:**
```
masterpiece, embedding:my_art_style, 1girl, detailed
```

The embedding file should be in your ComfyUI embeddings folder (without the file extension in the prompt).

---

## BEDROT's Conditional Bracket System

This is where things get interesting. The conditional bracket system lets you toggle parts of your prompt on and off using simple flags. It's perfect for A/B testing, creating prompt variants, or building reusable prompt templates.

### Flag Tokens: `[N]`

Place `[N]` anywhere in your prompt to activate flag N (where N is any positive integer).

```
portrait of a woman [1] [2]
```

This activates flags 1 and 2. The flag tokens themselves disappear from the final text - they're just switches.

**Key point:** Flags are global. A flag set anywhere in your prompt affects all conditional blocks throughout the entire text.

---

### Conditional Blocks: `[K: content]`

Content inside these blocks appears or disappears based on whether a flag is active.

| Syntax | Behavior |
|--------|----------|
| `[1: content]` | Content appears when flag 1 is ON |
| `[-1: content]` | Content appears when flag 1 is OFF |

**Example - Toggle between two options:**
```
portrait [1], [1: with glasses], [-1: without glasses]
```

With `[1]` present: `portrait, with glasses`
Without `[1]`: `portrait, without glasses`

The negative syntax `[-K: content]` is the inverse - it shows the content only when that flag is NOT set.

---

### Invalid Tokens: `[-N]`

A bare negative number like `[-1]` (without a colon) doesn't do anything useful - it's treated as noise and removed. This is by design: you can't "deactivate" a flag, only activate them.

---

## Practical Examples

### A/B Testing Styles

Create one prompt with multiple style toggles:

```
[1] [2]
1girl, standing in forest,
[1: photorealistic, detailed skin, pores],
[-1: anime style, cel shading],
[2: dramatic lighting, volumetric fog],
[-2: flat lighting, simple background]
```

Toggle `[1]` and `[2]` to quickly test 4 different combinations without editing the prompt.

---

### Character Variants

Build a reusable character prompt:

```
[1] [2] [3]
1girl,
[1: long flowing hair], [-1: short pixie cut],
[2: blue eyes], [-2: green eyes],
[3: wearing armor], [-3: wearing casual clothes]
```

Mix and match flags to generate different versions of the same character.

---

### Quality Presets

Quick toggle between draft and final quality:

```
[1]
portrait of a man,
[1: masterpiece, best quality, highly detailed, 8k],
[-1: sketch, rough, simple]
```

Remove `[1]` for quick drafts, add it back for final renders.

---

### Combining with Native Syntax

All ComfyUI syntax works alongside conditional brackets:

```
[1]
(masterpiece:1.2), {1girl|1boy},
[1: (detailed face:1.3), beautiful eyes],
[-1: faceless, silhouette],
embedding:my_style
```

This combines weighting `()`, random choice `{}`, embeddings, and conditional blocks all in one prompt.

---

### Nested Conditionals

You can nest conditional blocks up to 10 levels deep:

```
[1] [2]
character,
[1: hero [2: wearing shiny armor], standing tall]
```

- Flags 1 only: `character, hero, standing tall`
- Flags 1 and 2: `character, hero wearing shiny armor, standing tall`
- No flags: `character`

---

## Tips

1. **Flags are global** - Set a flag once and it applies everywhere. No need to repeat `[1]` multiple times.

2. **Default state is OFF** - Without a flag token, all `[K: ...]` blocks are hidden and all `[-K: ...]` blocks are shown.

3. **Use any positive integer** - `[1]`, `[2]`, `[99]`, `[1000]` - use whatever numbering makes sense for your workflow.

4. **Whitespace is cleaned automatically** - Multiple spaces collapse to one, and awkward spacing around commas gets tidied up.

5. **Group related toggles** - Put all your flag tokens at the start of the prompt for easy management:
   ```
   [1] [2] [3]
   rest of your prompt here...
   ```

---

## Quick Reference

| Syntax | What it does |
|--------|--------------|
| `(word)` | 1.1x weight boost |
| `(word:1.5)` | Custom weight |
| `((word))` | Stacked weight (~1.21x) |
| `{a\|b\|c}` | Random choice |
| `\(` `\)` | Literal parentheses |
| `embedding:name` | Load embedding |
| `[N]` | Activate flag N |
| `[K: text]` | Show text when flag K is ON |
| `[-K: text]` | Show text when flag K is OFF |
| `[-N]` | Ignored (noise) |

---

Happy prompting!
