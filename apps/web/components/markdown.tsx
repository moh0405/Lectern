"use client";

import "highlight.js/styles/github-dark.css";
import "katex/dist/katex.min.css";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { cn } from "@/lib/utils";

/**
 * Renders Markdown from the model. Raw HTML in the text is NOT rendered (react-markdown
 * escapes it), so model output cannot inject markup. Supports GFM, KaTeX math and code highlighting.
 */
export function Markdown({
  children,
  className,
  streaming,
  breaks,
}: {
  children: string;
  className?: string;
  streaming?: boolean;
  /** Keep single newlines as line breaks (for plain-text problem statements). */
  breaks?: boolean;
}) {
  return (
    <div className={cn("md-body", streaming && "streaming-cursor", className)}>
      <ReactMarkdown
        remarkPlugins={breaks ? [remarkGfm, remarkMath, remarkBreaks] : [remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, [rehypeHighlight, { detect: false, ignoreMissing: true }]]}
        components={{
          a: ({ href, children: c }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {c}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
