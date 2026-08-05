"use client";

import { useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import ReactMarkdown from "react-markdown";

function extractText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node && typeof node === "object" && "props" in node) {
    const props = node.props as { children?: ReactNode };
    return extractText(props.children);
  }
  return "";
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <button type="button" className="copy-button" onClick={copy} aria-label="Copy To Codex">
      <span className="copy-icon" aria-hidden="true" />
      <span>{copied ? "Copied" : "Copy To Codex"}</span>
    </button>
  );
}

function parseImageMeta(title?: string | null) {
  const tokens = (title ?? "").split(/\s+/).filter(Boolean);
  const widthToken = tokens.find((token) => token.startsWith("w="));
  const width = widthToken ? Number(widthToken.slice(2)) : undefined;
  const align = tokens.includes("center") ? "center" : "";
  return {
    align,
    style: width && Number.isFinite(width) ? ({ maxWidth: `${width}px` } satisfies CSSProperties) : undefined,
  };
}

export default function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        components={{
          pre({ children }) {
            const text = extractText(children).replace(/\n$/, "");
            return (
              <div className="code-card">
                <div className="code-toolbar">
                  <CopyButton text={text} />
                </div>
                <pre>{children}</pre>
              </div>
            );
          },
          img({ src, alt, title }) {
            const meta = parseImageMeta(title);
            return (
              <span className={`markdown-image ${meta.align}`} style={meta.style}>
                {/* eslint-disable-next-line @next/next/no-img-element -- Markdown task assets are authored as static public images. */}
                <img src={src ?? ""} alt={alt ?? ""} />
              </span>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
