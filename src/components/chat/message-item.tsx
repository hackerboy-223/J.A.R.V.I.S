"use client";

import * as React from "react";
import { Check, Copy, TriangleAlert, User } from "lucide-react";
import { Markdown } from "@/components/chat/markdown";
import { ToolCard } from "@/components/chat/tool-card";
import { cn } from "@/lib/utils";
import type { UiMessage } from "@/lib/types";

/** Mini réacteur arc (avatar de JARVIS) */
function MiniReactor({ active }: { active?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-primary/40",
        active && "animate-glow-pulse"
      )}
      style={{ animationDuration: "1.6s" }}
    >
      <span className="absolute inset-1 rounded-full bg-primary/10" />
      <span
        className="absolute inset-[9px] rounded-full bg-primary/90"
        style={{ boxShadow: "0 0 10px 1px color-mix(in oklch, var(--primary) 70%, transparent)" }}
      />
      <span className="absolute inset-2 rounded-full border border-primary/30 border-dashed animate-jarvis-spin [animation-duration:14s]" />
    </span>
  );
}

// React.memo (perf) : pendant le streaming, seuls les messages qui changent
// re-render (les tokens arrivent par lots via le hook agent).
const MessageItemImpl = function MessageItem({ message }: { message: UiMessage }) {
  const [copied, setCopied] = React.useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  };

  if (message.role === "tool") {
    return (
      <div className="jarvis-message-row flex justify-start pl-0 sm:pl-10">
        <div className="w-full max-w-2xl">
          <ToolCard message={message} />
        </div>
      </div>
    );
  }

  const isUser = message.role === "user";

  return (
    <div className={cn("jarvis-message-row flex items-start gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      {isUser ? (
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-gold/40 bg-gold/10 text-gold"
          aria-hidden
        >
          <User className="h-4 w-4" />
        </div>
      ) : (
        <MiniReactor active={message.pending} />
      )}

      <div className={cn("min-w-0 max-w-[calc(100%-3rem)] flex flex-col gap-1", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 shadow-sm",
            isUser
              ? "rounded-tr-sm border border-gold/35 bg-gold/10 text-foreground"
              : "hud-panel rounded-tl-sm text-card-foreground"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words text-[15px] leading-relaxed">
              {message.content}
            </p>
          ) : message.pending ? (
            // PERF : pendant le streaming, texte brut (aucun re-parse
            // Markdown par token). Le Markdown complet est rendu une seule
            // fois, quand le message est terminé.
            <p
              className={cn(
                "whitespace-pre-wrap break-words text-[15px] leading-relaxed",
                message.content && "stream-cursor"
              )}
            >
              {message.content}
            </p>
          ) : (
            <div className="min-w-0">
              <Markdown content={message.content || "…"} />
            </div>
          )}
          {message.pending && !message.content && (
            <span className="flex gap-1 py-1">
              <span className="dot-pulse h-2 w-2 rounded-full bg-primary" />
              <span className="dot-pulse h-2 w-2 rounded-full bg-primary [animation-delay:150ms]" />
              <span className="dot-pulse h-2 w-2 rounded-full bg-primary [animation-delay:300ms]" />
            </span>
          )}
        </div>

        {message.error && (
          <p className="flex items-center gap-1.5 rounded-lg border border-destructive/30 bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
            <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
            {message.error}
          </p>
        )}

        {!isUser && !message.pending && message.content.length > 0 && (
          <button
            type="button"
            onClick={copy}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            aria-label="Copier la réponse"
          >
            {copied ? <Check className="h-3 w-3 text-primary" /> : <Copy className="h-3 w-3" />}
            {copied ? "Copié" : "Copier"}
          </button>
        )}
      </div>
    </div>
  );
};

export const MessageItem = React.memo(MessageItemImpl);
