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

## Dynamic Presets with Flags

This is where the conditional bracket system truly shines. By placing `[N]` flags **inside** dynamic prompt options `{A|B}`, you can create sophisticated preset systems where one random selection controls your entire prompt.

### The Pattern

```
{option A [1] | option B [2] | option C [3]}
```

This randomly picks one option, which:
1. Outputs the text (e.g., "option A")
2. Activates the corresponding flag (e.g., flag 1)

Then all your `[1: ...]`, `[2: ...]`, `[3: ...]` blocks respond accordingly.

---

### Theme Packages

Build complete aesthetic presets that stay coherent:

```
1girl, portrait, {cyberpunk [1] | fantasy [2] | steampunk [3]},
[1: neon lights, rain, dark city, holographic jacket]
[2: ethereal glow, magical forest, elven dress]
[3: brass gears, Victorian era, corset and goggles]
```

**Possible outputs:**
- `1girl, portrait, cyberpunk, neon lights, rain, dark city, holographic jacket`
- `1girl, portrait, fantasy, ethereal glow, magical forest, elven dress`
- `1girl, portrait, steampunk, brass gears, Victorian era, corset and goggles`

No more mismatched aesthetics - each theme brings its full package.

---

### Character Classes

Define archetypes where class determines everything:

```
{a warrior [1] | a mage [2] | a rogue [3]},
[1: battle-scarred face, stern expression]
[2: wise eyes, mystical glow]
[3: cunning smile, shadowed features],
wearing [1: plate armor, wielding greatsword]
[2: flowing robes, ornate staff]
[3: leather armor, twin daggers],
standing in [1: a war-torn battlefield]
[2: an ancient arcane library]
[3: a moonlit back alley]
```

One random pick builds a complete character with matching appearance, gear, and setting.

---

### Time of Day

Coherent lighting and atmosphere:

```
landscape photo, {morning [1] | golden hour [2] | night [3]},
[1: soft diffused light, misty, dew on grass, birds in sky]
[2: warm orange tones, long shadows, sun on horizon]
[3: moonlight, stars visible, cool blue tones, quiet mood]
```

---

### Subject with Matching Props

Ensure subjects always get appropriate items:

```
{a black cat [1] | a golden retriever [2]},
playing with [1: a ball of yarn][-1: a tennis ball],
resting on [1: a velvet cushion][-1: a grass lawn]
```

**Outputs:**
- `a black cat, playing with a ball of yarn, resting on a velvet cushion`
- `a golden retriever, playing with a tennis ball, resting on a grass lawn`

The negative blocks `[-1: ...]` provide the alternative when flag 1 is NOT active.

---

### Weighted Rarity

Control the odds by repeating options:

```
character with {common [1] | common [1] | common [1] | rare [2]} hair,
[1: brown, shoulder-length]
[2: rainbow gradient, flowing dramatically]
```

This gives 75% chance of common hair, 25% chance of rare. Duplicate the options to weight your randomness.

---

### Role Swapping

Flip character roles while keeping both present:

```
two figures facing off,
{hero vs villain [1] | twist ending [2]},
[1: the knight stands victorious][-1: the knight lies defeated],
[1: the dragon retreats wounded][-1: the dragon looms triumphant]
```

One flag swap reverses the entire narrative.

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
