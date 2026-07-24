import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

// Lightweight syntax highlighter — no external dependencies
const KEYWORDS = new Set([
  "import", "from", "export", "default", "const", "let", "var", "function",
  "return", "if", "else", "for", "while", "do", "switch", "case", "break",
  "continue", "try", "catch", "finally", "throw", "new", "delete", "typeof",
  "instanceof", "in", "of", "class", "extends", "super", "this", "static",
  "async", "await", "yield", "true", "false", "null", "undefined", "void",
  "type", "interface", "enum", "namespace", "module", "declare", "abstract",
  "public", "private", "protected", "readonly", "as", "is", "keyof",
  "def", "self", "print", "raise", "with", "pass", "lambda", "None",
  "True", "False", "elif", "except", "import", "from", "global", "nonlocal",
  "fn", "mut", "let", "match", "impl", "pub", "struct", "enum", "trait",
  "use", "mod", "crate", "where", "move", "ref", "async", "await",
]);

const PY_BUILTINS = new Set([
  "print", "len", "range", "str", "int", "float", "list", "dict", "set",
  "tuple", "bool", "type", "isinstance", "hasattr", "getattr", "setattr",
  "open", "input", "sorted", "enumerate", "zip", "map", "filter", "any",
  "all", "min", "max", "sum", "abs", "round", "super", "property",
]);

const PLACEHOLDER = '\x00';

function highlightCode(code: string, language: string): string {
  // Escape HTML first
  let html = code
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Tokenize to prevent double-highlighting: extract comments and strings
  // first, replace with placeholders, then highlight keywords on the clean text.
  const tokens: { placeholder: string; html: string }[] = [];
  let tokenIdx = 0;

  const makeToken = (raw: string, cls: string) => {
    const ph = `${PLACEHOLDER}${tokenIdx++}${PLACEHOLDER}`;
    tokens.push({ placeholder: ph, html: `<span class="${cls}">${raw}</span>` });
    return ph;
  };

  // 1. Multi-line comments
  html = html.replace(/(\/\*[\s\S]*?\*\/)/g, (m) => makeToken(m, "code-comment"));
  // Line comments
  html = html.replace(/(#.*$)/gm, (m) => makeToken(m, "code-comment"));
  // // line comments (JS/TS/Rust)
  html = html.replace(/(\/\/.*$)/gm, (m) => makeToken(m, "code-comment"));

  // 2. Strings (double, single, backtick)
  html = html.replace(/("(?:[^"\\]|\\.)*")/g, (m) => makeToken(m, "code-string"));
  html = html.replace(/('(?:[^'\\]|\\.)*')/g, (m) => makeToken(m, "code-string"));
  html = html.replace(/(`(?:[^`\\]|\\.)*`)/g, (m) => makeToken(m, "code-string"));

  // 3. Now highlight keywords/numbers on the safe text (comments & strings are placeholder'd)
  html = html.replace(/\b(\d+\.?\d*(?:e[+-]?\d+)?)\b/g, '<span class="code-number">$1</span>');

  const kwPattern = new RegExp(`\\b(${[...KEYWORDS].join("|")})\\b`, "g");
  html = html.replace(kwPattern, '<span class="code-keyword">$1</span>');

  if (language === "python" || language === "py") {
    const builtinPattern = new RegExp(`\\b(${[...PY_BUILTINS].join("|")})\\b`, "g");
    html = html.replace(builtinPattern, '<span class="code-builtin">$1</span>');
  }

  // Function calls: word followed by (
  html = html.replace(/\b([a-zA-Z_]\w*)\s*(?=\()/g, '<span class="code-function">$1</span>');

  // Decorators
  html = html.replace(/(@\w+)/g, '<span class="code-decorator">$1</span>');

  // 4. Restore tokens — comments and strings get their own spans, untouched by keyword highlighting
  for (const { placeholder, html: replacement } of tokens) {
    html = html.replace(placeholder, replacement);
  }

  return html;
}

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
}

export function CodeBlock({ code, language = "", filename }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const codeRef = useRef<HTMLPreElement>(null);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = code;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [code]);

  const lines = code.split("\n");
  const langLabel = language || "code";

  return (
    <div className="code-block rounded-xl border border-border overflow-hidden my-2 bg-[#0a0a0a]">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#111] border-b border-border">
        <div className="flex items-center gap-2">
          {/* Traffic light dots */}
          <div className="flex gap-1">
            <span className="w-2 h-2 rounded-full bg-[#ff5f57]" />
            <span className="w-2 h-2 rounded-full bg-[#febc2e]" />
            <span className="w-2 h-2 rounded-full bg-[#28c840]" />
          </div>
          {filename && (
            <span className="text-2xs font-mono text-text-muted">{filename}</span>
          )}
          <span className="text-2xs font-mono text-text-muted/50 px-1.5 py-0.5 rounded bg-surface-elevated">
            {langLabel}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="text-2xs font-mono text-text-muted hover:text-accent transition-colors px-2 py-0.5 rounded hover:bg-surface-elevated"
          title="Copy code"
        >
          <AnimatePresence mode="wait">
            {copied ? (
              <motion.span
                key="check"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                className="text-emerald"
              >
                ✓ Copied
              </motion.span>
            ) : (
              <motion.span
                key="copy"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
              >
                Copy
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>

      {/* Code content with line numbers */}
      <div className="overflow-x-auto">
        <pre ref={codeRef} className="p-3 text-xs leading-relaxed">
          <code>
            {lines.map((line, i) => (
              <div key={i} className="flex">
                <span className="code-line-number select-none w-8 inline-block text-right mr-3 text-text-muted/30">
                  {i + 1}
                </span>
                <span
                  className="code-line"
                  dangerouslySetInnerHTML={{
                    __html: highlightCode(line, language) || "&nbsp;",
                  }}
                />
              </div>
            ))}
          </code>
        </pre>
      </div>
    </div>
  );
}

/**
 * Parse markdown-like content and render code blocks inline.
 * Handles ```lang ... ``` fenced code blocks.
 */
export function RenderedMessage({ content }: { content: string }) {
  // Split on fenced code blocks
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <>
      {parts.map((part, i) => {
        const codeMatch = part.match(/^```(\w*)\n([\s\S]*?)```$/);
        if (codeMatch) {
          const [, lang, code] = codeMatch;
          return <CodeBlock key={i} code={code.trimEnd()} language={lang} />;
        }
        // Regular text — render inline code, bold, italic
        return (
          <span key={i} className="whitespace-pre-wrap">
            {renderInlineMarkdown(part)}
          </span>
        );
      })}
    </>
  );
}

/** Render inline markdown: `code`, **bold**, *italic* */
function renderInlineMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Match inline code, bold, and italic
  const regex = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    // Add text before match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[1]) {
      // Inline code
      parts.push(
        <code
          key={key++}
          className="px-1.5 py-0.5 rounded bg-surface-elevated border border-border text-accent text-xs font-mono"
        >
          {match[1].slice(1, -1)}
        </code>,
      );
    } else if (match[2]) {
      // Bold
      parts.push(
        <strong key={key++} className="font-semibold text-text">
          {match[2].slice(2, -2)}
        </strong>,
      );
    } else if (match[3]) {
      // Italic
      parts.push(
        <em key={key++} className="italic text-text-secondary">
          {match[3].slice(1, -1)}
        </em>,
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}
