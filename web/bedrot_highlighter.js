import { app } from "../../scripts/app.js";

/**
 * BEDROT Syntax Highlighter for BEDROT's Clip Text Encode
 *
 * Provides visual syntax highlighting for:
 * - Parentheses (...) - CLIP weighting
 * - Curly braces {...} - random choice blocks
 * - Square brackets [...] - BEDROT conditional language
 *
 * Also validates for common mistakes that cause silently broken prompts.
 */

// Load CSS stylesheet
function loadStylesheet() {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.type = "text/css";
    // Get the CSS file path relative to this JS file
    link.href = new URL("./bedrot_highlighter.css", import.meta.url).href;
    document.head.appendChild(link);
}

loadStylesheet();

// Token types for syntax highlighting
const TokenType = {
    TEXT: "text",
    PAREN_OPEN: "paren-open",
    PAREN_CLOSE: "paren-close",
    PAREN_CONTENT: "paren-content",
    PAREN_WEIGHT: "paren-weight",
    CURLY_OPEN: "curly-open",
    CURLY_CLOSE: "curly-close",
    CURLY_PIPE: "curly-pipe",
    FLAG_TOKEN: "flag-token",
    COND_POS_DIRECTIVE: "cond-pos-dir",
    COND_NEG_DIRECTIVE: "cond-neg-dir",
    COND_CLOSE: "cond-close",
    INVALID_TOKEN: "invalid-token",
    UNBALANCED: "unbalanced",
    WARNING: "warning",
    ORPHAN_FLAG: "orphan-flag",
    UNUSED_COND: "unused-cond",
    TAG_BYPASS: "tag-bypass",           // The --- marker and bypassed content
};

/**
 * Syntax highlighter class using sibling overlay pattern
 * Backdrop is inserted as sibling element, preserving ComfyUI's layout control
 */
class BedrotSyntaxHighlighter {
    constructor(textarea, node) {
        this.textarea = textarea;
        this.node = node;
        this.backdrop = null;
        this.originalParent = null;
        this.resizeObserver = null;
        this.enabled = true;
        this._lastText = null;
        this._highlightTimeout = null;

        this.setupDOM();
        this.bindEvents();
        this.highlight();
    }

    /**
     * Set up the DOM structure for backdrop highlighting
     * Uses sibling overlay pattern - backdrop is inserted as sibling, not wrapper
     * This preserves ComfyUI's control over textarea sizing
     */
    setupDOM() {
        // Store original parent for cleanup
        this.originalParent = this.textarea.parentNode;

        // Ensure parent has relative positioning for absolute backdrop
        const parentPosition = getComputedStyle(this.originalParent).position;
        if (parentPosition === 'static') {
            this.originalParent.style.position = 'relative';
        }

        // Create backdrop as sibling, not wrapper
        this.backdrop = document.createElement("div");
        this.backdrop.className = "bedrot-highlight-backdrop";

        // Insert backdrop before textarea (so textarea is on top via z-index)
        this.originalParent.insertBefore(this.backdrop, this.textarea);

        // Add class to textarea for transparent styling
        this.textarea.classList.add("bedrot-highlighted-textarea");

        // Match sizes
        this.syncSize();
    }

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Update highlighting on input
        this.textarea.addEventListener("input", () => this.highlight());

        // Immediate highlight on Enter for responsive feel (bypass debounce)
        this.textarea.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                // Use setTimeout to run after the Enter key inserts the newline
                setTimeout(() => this._doHighlight(), 0);
            }
        });

        // Sync scroll positions
        this.textarea.addEventListener("scroll", () => this.syncScroll());

        // Handle resize - CRITICAL for text wrapping on node resize
        this.resizeObserver = new ResizeObserver((entries) => {
            // Sync backdrop size first
            this.syncSize();
            // Force re-render of highlighted text so wrapping updates
            this._lastText = null; // Clear cache to force re-highlight
            this.highlight();
        });
        this.resizeObserver.observe(this.textarea);

        // Also observe parent for layout changes
        if (this.originalParent) {
            this.resizeObserver.observe(this.originalParent);
        }

        // Also sync on focus to catch any missed updates
        this.textarea.addEventListener("focus", () => this.highlight());
    }

    /**
     * Sync scroll position between textarea and backdrop
     */
    syncScroll() {
        if (this.backdrop) {
            this.backdrop.scrollTop = this.textarea.scrollTop;
            this.backdrop.scrollLeft = this.textarea.scrollLeft;
        }
    }

    /**
     * Sync size of backdrop to textarea
     * Backdrop is absolutely positioned as sibling, overlays textarea exactly
     * CRITICAL: Must match ALL font rendering properties for cursor alignment
     */
    syncSize() {
        if (!this.backdrop || !this.textarea) return;

        // Position backdrop to match textarea bounds
        this.backdrop.style.position = 'absolute';
        this.backdrop.style.left = (this.textarea.offsetLeft) + 'px';
        this.backdrop.style.top = (this.textarea.offsetTop) + 'px';
        this.backdrop.style.width = this.textarea.offsetWidth + 'px';
        this.backdrop.style.height = this.textarea.offsetHeight + 'px';

        // Match ALL typography and box model properties for identical wrapping
        const computed = getComputedStyle(this.textarea);
        this.backdrop.style.padding = computed.padding;
        this.backdrop.style.fontSize = computed.fontSize;
        this.backdrop.style.fontFamily = computed.fontFamily;
        this.backdrop.style.lineHeight = computed.lineHeight;
        this.backdrop.style.letterSpacing = computed.letterSpacing;
        this.backdrop.style.wordSpacing = computed.wordSpacing;
        this.backdrop.style.boxSizing = computed.boxSizing;

        // CRITICAL: Match text wrapping behavior
        this.backdrop.style.whiteSpace = 'pre-wrap';
        this.backdrop.style.wordWrap = 'break-word';
        this.backdrop.style.overflowWrap = 'break-word';

        // Match border so padding calculations align
        this.backdrop.style.borderWidth = computed.borderWidth;
        this.backdrop.style.borderStyle = 'solid';
        this.backdrop.style.borderColor = 'transparent';

        // CRITICAL: Match ALL font rendering properties for cursor alignment
        // These ensure the backdrop renders text identically to the textarea
        this.backdrop.style.fontWeight = computed.fontWeight;
        this.backdrop.style.fontStyle = computed.fontStyle;
        this.backdrop.style.fontVariant = computed.fontVariant;
        this.backdrop.style.fontStretch = computed.fontStretch;
        this.backdrop.style.fontFeatureSettings = computed.fontFeatureSettings;
        this.backdrop.style.fontKerning = computed.fontKerning;
        this.backdrop.style.fontVariantLigatures = computed.fontVariantLigatures;
        this.backdrop.style.textRendering = computed.textRendering;
        this.backdrop.style.textTransform = computed.textTransform;
        this.backdrop.style.textIndent = computed.textIndent;
        this.backdrop.style.tabSize = computed.tabSize;
        this.backdrop.style.hyphens = computed.hyphens;
        // Webkit-specific font smoothing
        this.backdrop.style.webkitFontSmoothing = computed.webkitFontSmoothing;
        // Firefox-specific font smoothing
        this.backdrop.style.MozOsxFontSmoothing = computed.MozOsxFontSmoothing;
    }

    /**
     * Enable or disable highlighting
     */
    setEnabled(enabled) {
        this.enabled = enabled;
        if (enabled) {
            this.textarea.classList.add("bedrot-highlighted-textarea");
            this.backdrop.style.display = "block";
            this.highlight();
        } else {
            this.textarea.classList.remove("bedrot-highlighted-textarea");
            this.backdrop.style.display = "none";
        }
    }

    /**
     * Main highlight function with debouncing
     */
    highlight() {
        if (!this.enabled) return;

        if (this._highlightTimeout) {
            clearTimeout(this._highlightTimeout);
        }

        this._highlightTimeout = setTimeout(() => {
            this._doHighlight();
        }, 16); // ~60fps
    }

    /**
     * Perform the actual highlighting
     */
    _doHighlight() {
        if (!this.enabled || !this.backdrop) return;

        const text = this.textarea.value;

        // Skip if text unchanged
        if (text === this._lastText) {
            return;
        }
        this._lastText = text;

        const { tokens, validation } = this.tokenize(text);
        const html = this.tokensToHTML(tokens, validation);
        this.backdrop.innerHTML = html;
        this.syncScroll();

        // Force scroll sync on next frame for multi-line changes (e.g., Enter key)
        requestAnimationFrame(() => this.syncScroll());
    }

    /**
     * Tokenize the text and perform validation
     * Returns tokens and validation info
     */
    tokenize(text) {
        const tokens = [];
        const validation = {
            flagsUsed: new Set(),        // Flag IDs that appear as [N]
            conditionalsUsed: new Set(), // Flag IDs referenced in [K: ...] or [-K: ...]
            unbalancedBrackets: [],      // Positions of unbalanced brackets
            nestedConditionals: [],      // Positions of nested conditionals
        };

        let pos = 0;
        const bracketStack = []; // Track bracket nesting
        let inConditional = false;
        let conditionalDepth = 0;

        while (pos < text.length) {
            let matched = false;
            const remaining = text.substring(pos);

            // Check for --- tag bypass pattern (must come first)
            if (remaining.startsWith('---')) {
                const bracketMap = { '(': ')', '[': ']', '{': '}' };
                let bypassEnd = pos + 3; // After ---

                if (bypassEnd < text.length && text[bypassEnd] in bracketMap) {
                    // Bracket-based bypass: ---(content), ---[content], ---{content}
                    const openChar = text[bypassEnd];
                    const closeChar = bracketMap[openChar];
                    const matchEnd = this.findMatchingBracket(text, bypassEnd + 1, openChar, closeChar);

                    if (matchEnd !== -1) {
                        // Found matching bracket - include everything
                        const fullBypass = text.substring(pos, matchEnd + 1);
                        tokens.push({
                            type: TokenType.TAG_BYPASS,
                            value: fullBypass,
                            start: pos,
                            end: matchEnd + 1,
                        });
                        pos = matchEnd + 1;
                    } else {
                        // Unbalanced - mark rest as bypass (will be removed)
                        const fullBypass = text.substring(pos);
                        tokens.push({
                            type: TokenType.TAG_BYPASS,
                            value: fullBypass,
                            start: pos,
                            end: text.length,
                            unbalanced: true,
                        });
                        pos = text.length;
                    }
                } else {
                    // Simple bypass: ---tag until comma
                    let endPos = bypassEnd;
                    while (endPos < text.length && text[endPos] !== ',') {
                        endPos++;
                    }
                    const fullBypass = text.substring(pos, endPos);
                    tokens.push({
                        type: TokenType.TAG_BYPASS,
                        value: fullBypass,
                        start: pos,
                        end: endPos,
                    });
                    pos = endPos;
                }
                matched = true;
                continue;
            }

            // Check for flag token [N] (positive integer, no colon)
            const flagMatch = remaining.match(/^\[(\d+)\]/);
            if (flagMatch) {
                const flagId = parseInt(flagMatch[1]);
                validation.flagsUsed.add(flagId);

                tokens.push({
                    type: TokenType.FLAG_TOKEN,
                    value: flagMatch[0],
                    start: pos,
                    end: pos + flagMatch[0].length,
                    flagId: flagId,
                });
                pos += flagMatch[0].length;
                matched = true;
                continue;
            }

            // Check for positive conditional block opening [K:
            const condPosMatch = remaining.match(/^\[(\d+):\s*/);
            if (condPosMatch) {
                const flagId = parseInt(condPosMatch[1]);
                validation.conditionalsUsed.add(flagId);

                if (conditionalDepth > 0) {
                    validation.nestedConditionals.push(pos);
                }
                conditionalDepth++;
                bracketStack.push({ type: 'cond-pos', pos: pos });

                tokens.push({
                    type: TokenType.COND_POS_DIRECTIVE,
                    value: condPosMatch[0],
                    start: pos,
                    end: pos + condPosMatch[0].length,
                    flagId: flagId,
                    isNested: conditionalDepth > 1,
                });
                pos += condPosMatch[0].length;
                inConditional = true;
                matched = true;
                continue;
            }

            // Check for negative conditional block opening [-K:
            // IMPORTANT: This must come BEFORE invalid bare negative check
            // so that [-1: text] is recognized as a conditional, not invalid
            const condNegMatch = remaining.match(/^\[(-\d+):\s*/);
            if (condNegMatch) {
                const flagId = Math.abs(parseInt(condNegMatch[1]));
                validation.conditionalsUsed.add(flagId);

                if (conditionalDepth > 0) {
                    validation.nestedConditionals.push(pos);
                }
                conditionalDepth++;
                bracketStack.push({ type: 'cond-neg', pos: pos });

                tokens.push({
                    type: TokenType.COND_NEG_DIRECTIVE,
                    value: condNegMatch[0],
                    start: pos,
                    end: pos + condNegMatch[0].length,
                    flagId: flagId,
                    isNested: conditionalDepth > 1,
                });
                pos += condNegMatch[0].length;
                inConditional = true;
                matched = true;
                continue;
            }

            // Check for invalid bare negative token [-N] (no colon)
            // This must come AFTER conditional checks so [-1: text] works
            const invalidNegMatch = remaining.match(/^\[-\d+\]/);
            if (invalidNegMatch) {
                tokens.push({
                    type: TokenType.INVALID_TOKEN,
                    value: invalidNegMatch[0],
                    start: pos,
                    end: pos + invalidNegMatch[0].length,
                });
                pos += invalidNegMatch[0].length;
                matched = true;
                continue;
            }

            // Check for closing bracket ] (for conditionals)
            if (text[pos] === ']' && bracketStack.length > 0) {
                const lastBracket = bracketStack[bracketStack.length - 1];
                if (lastBracket.type === 'cond-pos' || lastBracket.type === 'cond-neg') {
                    bracketStack.pop();
                    conditionalDepth--;

                    tokens.push({
                        type: TokenType.COND_CLOSE,
                        value: ']',
                        start: pos,
                        end: pos + 1,
                    });
                    pos++;
                    if (conditionalDepth === 0) {
                        inConditional = false;
                    }
                    matched = true;
                    continue;
                }
            }

            // Check for parentheses with optional weight (text:1.2)
            // Exclude square brackets from content match so conditionals inside parens are tokenized separately
            // Exclude curly braces and pipes from paren content so they tokenize separately
            // This allows {a|b} inside (...) to be highlighted correctly
            const parenMatch = remaining.match(/^\(([^()\[\]{}|]*?)(:\d+\.?\d*)?\)/);
            if (parenMatch) {
                const fullMatch = parenMatch[0];
                const content = parenMatch[1] || '';
                const weight = parenMatch[2] || '';

                tokens.push({
                    type: TokenType.PAREN_OPEN,
                    value: '(',
                    start: pos,
                    end: pos + 1,
                });

                if (content) {
                    tokens.push({
                        type: TokenType.PAREN_CONTENT,
                        value: content,
                        start: pos + 1,
                        end: pos + 1 + content.length,
                    });
                }

                if (weight) {
                    tokens.push({
                        type: TokenType.PAREN_WEIGHT,
                        value: weight,
                        start: pos + 1 + content.length,
                        end: pos + 1 + content.length + weight.length,
                    });
                }

                tokens.push({
                    type: TokenType.PAREN_CLOSE,
                    value: ')',
                    start: pos + fullMatch.length - 1,
                    end: pos + fullMatch.length,
                });

                pos += fullMatch.length;
                matched = true;
                continue;
            }

            // Check for opening parenthesis (when simple pattern didn't match)
            if (text[pos] === '(') {
                bracketStack.push({ type: 'paren', pos: pos });
                tokens.push({
                    type: TokenType.PAREN_OPEN,
                    value: '(',
                    start: pos,
                    end: pos + 1,
                });
                pos++;
                matched = true;
                continue;
            }

            // Check for closing parenthesis
            if (text[pos] === ')') {
                const lastBracket = bracketStack.length > 0 ? bracketStack[bracketStack.length - 1] : null;
                if (lastBracket && lastBracket.type === 'paren') {
                    bracketStack.pop();
                    tokens.push({
                        type: TokenType.PAREN_CLOSE,
                        value: ')',
                        start: pos,
                        end: pos + 1,
                    });
                } else {
                    tokens.push({
                        type: TokenType.UNBALANCED,
                        value: ')',
                        start: pos,
                        end: pos + 1,
                    });
                }
                pos++;
                matched = true;
                continue;
            }

            // Check for curly brace open
            if (text[pos] === '{') {
                bracketStack.push({ type: 'curly', pos: pos });
                tokens.push({
                    type: TokenType.CURLY_OPEN,
                    value: '{',
                    start: pos,
                    end: pos + 1,
                });
                pos++;
                matched = true;
                continue;
            }

            // Check for curly brace close
            if (text[pos] === '}') {
                const lastBracket = bracketStack.length > 0 ? bracketStack[bracketStack.length - 1] : null;
                if (lastBracket && lastBracket.type === 'curly') {
                    bracketStack.pop();
                    tokens.push({
                        type: TokenType.CURLY_CLOSE,
                        value: '}',
                        start: pos,
                        end: pos + 1,
                    });
                } else {
                    tokens.push({
                        type: TokenType.UNBALANCED,
                        value: '}',
                        start: pos,
                        end: pos + 1,
                    });
                }
                pos++;
                matched = true;
                continue;
            }

            // Check for pipe (in curly braces)
            if (text[pos] === '|') {
                tokens.push({
                    type: TokenType.CURLY_PIPE,
                    value: '|',
                    start: pos,
                    end: pos + 1,
                });
                pos++;
                matched = true;
                continue;
            }

            // Check for unmatched opening square bracket [
            if (text[pos] === '[') {
                // This is a [ that didn't match any pattern above
                tokens.push({
                    type: TokenType.UNBALANCED,
                    value: '[',
                    start: pos,
                    end: pos + 1,
                });
                pos++;
                matched = true;
                continue;
            }

            // Check for unmatched closing square bracket ]
            if (text[pos] === ']') {
                tokens.push({
                    type: TokenType.UNBALANCED,
                    value: ']',
                    start: pos,
                    end: pos + 1,
                });
                pos++;
                matched = true;
                continue;
            }

            // Regular text - accumulate until next special character
            if (!matched) {
                let textEnd = pos + 1;
                while (textEnd < text.length &&
                       !/[\[\](){}|]/.test(text[textEnd])) {
                    textEnd++;
                }

                tokens.push({
                    type: TokenType.TEXT,
                    value: text.substring(pos, textEnd),
                    start: pos,
                    end: textEnd,
                });
                pos = textEnd;
            }
        }

        // Mark any unclosed brackets as unbalanced
        for (const bracket of bracketStack) {
            validation.unbalancedBrackets.push(bracket.pos);
        }

        return { tokens, validation };
    }

    /**
     * Convert tokens to HTML with appropriate CSS classes
     */
    tokensToHTML(tokens, validation) {
        // Determine orphan flags (flags with no matching conditional)
        const orphanFlags = new Set();
        for (const flagId of validation.flagsUsed) {
            if (!validation.conditionalsUsed.has(flagId)) {
                orphanFlags.add(flagId);
            }
        }

        // Determine unused conditionals (conditionals referencing unused flags)
        const unusedConds = new Set();
        for (const flagId of validation.conditionalsUsed) {
            if (!validation.flagsUsed.has(flagId)) {
                unusedConds.add(flagId);
            }
        }

        return tokens.map(token => {
            const escaped = this.escapeHTML(token.value);

            if (token.type === TokenType.TEXT) {
                return escaped;
            }

            let className = `bedrot-${token.type}`;
            let extraClasses = [];

            // Add warning classes for validation issues
            if (token.type === TokenType.FLAG_TOKEN && orphanFlags.has(token.flagId)) {
                extraClasses.push("bedrot-orphan-flag");
            }

            if ((token.type === TokenType.COND_POS_DIRECTIVE ||
                 token.type === TokenType.COND_NEG_DIRECTIVE) &&
                unusedConds.has(token.flagId)) {
                extraClasses.push("bedrot-unused-cond");
            }

            if (token.isNested) {
                extraClasses.push("bedrot-nested-warning");
            }

            const allClasses = [className, ...extraClasses].join(" ");
            return `<span class="${allClasses}">${escaped}</span>`;
        }).join("");
    }

    /**
     * Escape HTML special characters
     */
    escapeHTML(str) {
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/ /g, " ") // Keep spaces as-is for pre-wrap
            .replace(/\n/g, "\n"); // Keep newlines for pre-wrap
    }

    /**
     * Find matching closing bracket position, respecting nesting.
     * Used for bracket-aware --- bypass detection.
     *
     * @param {string} text - Text to search in
     * @param {number} startPos - Position after the opening bracket
     * @param {string} openChar - Opening bracket character
     * @param {string} closeChar - Closing bracket character
     * @returns {number} Position of matching close bracket, or -1 if not found
     */
    findMatchingBracket(text, startPos, openChar, closeChar) {
        const bracketPairs = { '(': ')', '[': ']', '{': '}' };
        let depth = 1;
        let pos = startPos;

        while (pos < text.length && depth > 0) {
            const char = text[pos];
            if (char === closeChar) {
                depth--;
            } else if (char === openChar) {
                depth++;
            } else if (char in bracketPairs && char !== openChar) {
                // Different bracket type - find its matching close to skip over it
                const innerClose = bracketPairs[char];
                const innerEnd = this.findMatchingBracket(text, pos + 1, char, innerClose);
                if (innerEnd !== -1) {
                    pos = innerEnd;
                }
            }
            pos++;
        }

        return depth === 0 ? pos - 1 : -1;
    }

    /**
     * Clean up when removing highlighter
     */
    destroy() {
        // Disconnect resize observer
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        // Remove backdrop element
        if (this.backdrop && this.backdrop.parentNode) {
            this.backdrop.parentNode.removeChild(this.backdrop);
        }
        // Remove transparent styling from textarea
        if (this.textarea) {
            this.textarea.classList.remove("bedrot-highlighted-textarea");
        }
    }
}

// Store highlighter instances by node ID
const highlighters = new Map();

// Register the ComfyUI extension
app.registerExtension({
    name: "bedrot.CLIPTextEncodeHighlighter",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "BedrotCLIPTextEncode") {
            return;
        }

        // Store original onNodeCreated
        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function() {
            // Call original if exists
            if (onNodeCreated) {
                onNodeCreated.apply(this, arguments);
            }

            const node = this;

            // Add toggle widget for syntax highlighting
            const toggleWidget = node.addWidget(
                "toggle",
                "Syntax Highlighting",
                true, // Default enabled
                (value) => {
                    const highlighter = highlighters.get(node.id);
                    if (highlighter) {
                        highlighter.setEnabled(value);
                    }
                },
                { serialize: true }
            );

            // Wait for DOM to be ready, then set up highlighter
            setTimeout(() => {
                const textWidget = node.widgets?.find(w => w.name === "text");
                if (textWidget && textWidget.inputEl) {
                    const highlighter = new BedrotSyntaxHighlighter(textWidget.inputEl, node);
                    highlighters.set(node.id, highlighter);

                    // Apply current toggle state
                    highlighter.setEnabled(toggleWidget.value);
                }
            }, 100);
        };

        // Clean up on node removal
        const onRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function() {
            const highlighter = highlighters.get(this.id);
            if (highlighter) {
                highlighter.destroy();
                highlighters.delete(this.id);
            }

            if (onRemoved) {
                onRemoved.apply(this, arguments);
            }
        };
    },

    // Handle loaded graphs (restore toggle state)
    async loadedGraphNode(node) {
        if (node.type !== "BedrotCLIPTextEncode") {
            return;
        }

        // Re-apply toggle state after load
        setTimeout(() => {
            const toggleWidget = node.widgets?.find(w => w.name === "Syntax Highlighting");
            const highlighter = highlighters.get(node.id);

            if (toggleWidget && highlighter) {
                highlighter.setEnabled(toggleWidget.value);
            }
        }, 200);
    }
});
