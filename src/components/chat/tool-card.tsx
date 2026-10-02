"use client";

import * as React from "react";
import {
  BookOpen,
  Calculator,
  Check,
  ChevronDown,
  Clock,
  ExternalLink,
  Globe,
  Terminal,
  Wrench,
} from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import type { UiMessage } from "@/lib/types";

const TOOL_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  web_search: Globe,
  read_page: BookOpen,
  calculator: Calculator,
  run_js: Terminal,
  get_datetime: Clock,
};

const TOOL_LABELS: Record<string, string> = {
  web_search: "Recherche web",
  read_page: "Lecture de page",
  calculator: "Calculatrice",
  run_js: "Exécution JavaScript",
  get_datetime: "Date & heure",
};

function prettyArg(m: UiMessage): string {
  try {
    const args = m.toolArgs ? JSON.parse(m.toolArgs) : {};
    const keys = Object.keys(args);
    if (keys.length === 0) return "—";
    const first = args[keys[0]];
    if (typeof first === "string") return first.length > 120 ? first.slice(0, 120) + "…" : first;
    return JSON.stringify(args);
  } catch {
    return m.toolArgs ?? "—";
  }
}

function SearchResultBody({ m }: { m: UiMessage }) {
  let results: Array<{ url?: string; name?: string; snippet?: string }> = [];
  try {
    const parsed = m.toolResult ? JSON.parse(m.toolResult) : null;
    if (Array.isArray(parsed)) results = parsed;
    else if (parsed && Array.isArray(parsed.results)) results = parsed.results;
  } catch {
    /* fallback */
  }
  if (results.length === 0) return <FallbackJson m={m} />;
  return (
    <ul className="space-y-2">
      {results.slice(0, 6).map((r, i) => (
        <li key={i} className="rounded-md border bg-muted/30 p-2">
          {r.url ? (
            <a
              href={r.url}
              target="_blank"
              rel="noreferrer noopener"
              className="flex items-center gap-1 text-[13px] font-medium text-primary hover:underline"
            >
              <ExternalLink className="h-3 w-3 shrink-0" />
              <span className="truncate">{r.name || r.url}</span>
            </a>
          ) : (
            <p className="text-[13px] font-medium">{r.name}</p>
          )}
          {r.snippet && (
            <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{r.snippet}</p>
          )}
        </li>
      ))}
      {results.length > 6 && (
        <li className="text-xs text-muted-foreground">+{results.length - 6} autres résultats…</li>
      )}
    </ul>
  );
}

function PageBody({ m }: { m: UiMessage }) {
  let title = "";
  let url = "";
  let text = "";
  try {
    const parsed = m.toolResult ? JSON.parse(m.toolResult) : {};
    title = parsed.title || "";
    url = parsed.url || "";
    text = parsed.text || parsed.content || "";
  } catch {
    /* fallback */
  }
  if (!title && !text) return <FallbackJson m={m} />;
  return (
    <div className="space-y-1.5">
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer noopener"
          className="flex items-center gap-1 text-[13px] font-medium text-primary hover:underline"
        >
          <ExternalLink className="h-3 w-3 shrink-0" />
          <span className="truncate">{title || url}</span>
        </a>
      )}
      {!url && title && <p className="text-[13px] font-medium">{title}</p>}
      {text && (
        <p className="line-clamp-6 whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
          {text.slice(0, 900)}
          {text.length > 900 ? "…" : ""}
        </p>
      )}
    </div>
  );
}

function FallbackJson({ m }: { m: UiMessage }) {
  let display = m.toolResult ?? "";
  try {
    const parsed = m.toolResult ? JSON.parse(m.toolResult) : null;
    if (parsed !== null && parsed !== undefined) {
      display =
        typeof parsed === "string"
          ? parsed
          : JSON.stringify(parsed, null, 2);
    }
  } catch {
    /* keep raw */
  }
  return (
    <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-md bg-muted/40 p-2.5 font-mono text-xs leading-relaxed">
      {display.length > 4000 ? display.slice(0, 4000) + "…" : display || "—"}
    </pre>
  );
}

export function ToolCard({ message }: { message: UiMessage }) {
  const [open, setOpen] = React.useState(false);
  const Icon = TOOL_ICONS[message.toolName ?? ""] ?? Wrench;
  const label = TOOL_LABELS[message.toolName ?? ""] ?? message.toolName ?? "Outil";
  const running = message.pending;
  const isError = message.error === "tool_error";
  const isInterrupted = message.error === "interrompu";

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div
        className={cn(
          "rounded-xl border bg-card shadow-sm transition-colors",
          running && "border-primary/40",
          isError && "border-destructive/40"
        )}
      >
        <CollapsibleTrigger className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left hover:bg-accent/50 rounded-xl">
          <span
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border bg-muted/40",
              running && "border-primary/50"
            )}
          >
            {running ? (
              <span className="flex gap-0.5">
                <span className="dot-pulse h-1.5 w-1.5 rounded-full bg-primary" />
                <span className="dot-pulse h-1.5 w-1.5 rounded-full bg-primary [animation-delay:150ms]" />
                <span className="dot-pulse h-1.5 w-1.5 rounded-full bg-primary [animation-delay:300ms]" />
              </span>
            ) : (
              <Icon className={cn("h-4 w-4", isError ? "text-destructive" : "text-primary")} />
            )}
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-2">
              <span className="text-[13px] font-semibold">{label}</span>
              {!running && !isError && message.durationMs != null && (
                <span className="rounded-full bg-muted px-1.5 py-px text-[10px] font-medium text-muted-foreground">
                  {(message.durationMs / 1000).toFixed(1)}s
                </span>
              )}
              {isError && (
                <span className="rounded-full bg-destructive/10 px-1.5 py-px text-[10px] font-medium text-destructive">
                  erreur
                </span>
              )}
              {isInterrupted && (
                <span className="rounded-full bg-muted px-1.5 py-px text-[10px] font-medium text-muted-foreground">
                  interrompu
                </span>
              )}
            </span>
            <span className="mt-0.5 block truncate font-mono text-xs text-muted-foreground">
              {prettyArg(message)}
            </span>
          </span>
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
              open && "rotate-180"
            )}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="border-t px-3 py-2.5">
            <p className="mb-1.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Check className="h-3 w-3" /> Résultat
            </p>
            {message.toolName === "web_search" ? (
              <SearchResultBody m={message} />
            ) : message.toolName === "read_page" ? (
              <PageBody m={message} />
            ) : (
              <FallbackJson m={message} />
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
