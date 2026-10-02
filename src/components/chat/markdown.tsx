"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Check, Copy } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

// PERF : le surligneur syntaxique (Prism + tous les langages, très lourd)
// est chargé à la demande, uniquement quand un bloc de code apparaît.
const LazySyntaxHighlighter = React.lazy(async () => {
  const mod = await import("react-syntax-highlighter");
  return { default: mod.Prism };
});

function CodeBlock({
  language,
  value,
}: {
  language: string;
  value: string;
}) {
  const { resolvedTheme } = useTheme();
  const [copied, setCopied] = React.useState(false);
  const isDark = resolvedTheme === "dark";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="group/code relative my-3 overflow-hidden rounded-lg border bg-muted/40">
      <div className="flex items-center justify-between border-b bg-muted/60 px-3 py-1.5">
        <span className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
          {language || "code"}
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label="Copier le code"
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-primary" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
      </div>
      <React.Suspense
        fallback={
          <pre className="overflow-x-auto p-3 font-mono text-[0.8125rem] leading-relaxed">
            <code>{value.replace(/\n$/, "")}</code>
          </pre>
        }
      >
        <LazySyntaxHighlighter
          language={language || "text"}
          style={isDark ? oneDark : oneLight}
          customStyle={{
            margin: 0,
            padding: "0.85rem",
            fontSize: "0.8125rem",
            background: "transparent",
          }}
          codeTagProps={{
            style: { fontFamily: "var(--font-geist-mono)" },
          }}
        >
          {value.replace(/\n$/, "")}
        </LazySyntaxHighlighter>
      </React.Suspense>
    </div>
  );
}

function extractText(node: React.ReactNode): string {
  if (node == null || node === false) return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (typeof node === "object" && node !== null && "props" in (node as unknown as Record<string, unknown>)) {
    const el = node as unknown as React.ReactElement<{ children?: React.ReactNode }>;
    return extractText(el.props?.children);
  }
  return "";
}

export function Markdown({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn("text-[15px] leading-relaxed", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code(props) {
            const { children, className, ...rest } = props;
            const match = /language-(\w+)/.exec(className || "");
            const raw = extractText(children);
            const isInline = !match && !raw.includes("\n");
            if (isInline) {
              return (
                <code
                  className="rounded bg-accent px-1.5 py-0.5 font-mono text-[13px] text-accent-foreground"
                  {...rest}
                >
                  {children}
                </code>
              );
            }
            return (
              <code className={className} {...rest}>
                {children}
              </code>
            );
          },
          pre({ children }) {
            const child = children as
              | React.ReactElement<{ className?: string; children?: React.ReactNode }>
              | undefined;
            const className = child?.props?.className || "";
            const match = /language-(\w+)/.exec(className);
            const raw = extractText(child?.props?.children);
            if (match || raw.includes("\n")) {
              return <CodeBlock language={match ? match[1] : ""} value={raw} />;
            }
            return <pre className="whitespace-pre-wrap">{children}</pre>;
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer noopener"
                className="font-medium text-primary underline underline-offset-2 hover:opacity-80"
              >
                {children}
              </a>
            );
          },
          ul({ children }) {
            return <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>;
          },
          li({ children }) {
            return <li className="leading-relaxed">{children}</li>;
          },
          p({ children }) {
            return <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>;
          },
          h1({ children }) {
            return <h1 className="mb-2 mt-4 text-xl font-bold">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="mb-2 mt-4 text-lg font-bold">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="mb-1.5 mt-3 text-base font-semibold">{children}</h3>;
          },
          table({ children }) {
            return (
              <div className="my-3 overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">{children}</table>
              </div>
            );
          },
          th({ children }) {
            return (
              <th className="border-b bg-muted/60 px-3 py-2 text-left font-semibold">
                {children}
              </th>
            );
          },
          td({ children }) {
            return <td className="border-b px-3 py-2 align-top">{children}</td>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-3 border-l-4 border-primary/40 pl-3 text-muted-foreground italic">
                {children}
              </blockquote>
            );
          },
          hr() {
            return <hr className="my-4 border-border" />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
