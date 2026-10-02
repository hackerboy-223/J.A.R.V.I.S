"use client";

import * as React from "react";
import { ArrowUp, Loader2, Mic, Radio, Square, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { MicState } from "@/hooks/use-jarvis-voice";

interface ComposerProps {
  onSend: (text: string) => void;
  onStop: () => void;
  busy: boolean;
  disabled?: boolean;
  placeholder?: string;
  // Voix
  micState: MicState;
  micSupported: boolean;
  onMicToggle: () => void;
  speaking: boolean;
  voiceMode: boolean;
  onVoiceModeChange: (enabled: boolean) => void;
}

export function Composer({
  onSend,
  onStop,
  busy,
  disabled,
  placeholder,
  micState,
  micSupported,
  onMicToggle,
  speaking,
  voiceMode,
  onVoiceModeChange,
}: ComposerProps) {
  const [value, setValue] = React.useState("");
  const ref = React.useRef<HTMLTextAreaElement>(null);

  // Auto-resize
  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || busy || disabled) return;
    onSend(text);
    setValue("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const listening = micState === "listening";
  const transcribing = micState === "transcribing";
  const micDisabled = busy || disabled || transcribing;

  const micLabel = listening
    ? "Arrêter l'enregistrement et envoyer à JARVIS"
    : transcribing
      ? "Transcription en cours…"
      : micSupported
        ? "Parler à JARVIS — lien neural plein écran"
        : "Ouvrir le lien neural (saisie clavier disponible)";

  return (
    <div
      className={cn(
        "hud-panel rounded-2xl p-2 shadow-lg transition-shadow",
        (busy || listening) && "composer-active border-transparent shadow-xl"
      )}
    >
      <div className="flex items-end gap-1.5">
        {/* Micro */}
        <Button
          type="button"
          variant="outline"
          onClick={onMicToggle}
          disabled={micDisabled}
          aria-label={micLabel}
          title={micLabel}
          className={cn(
            "h-10 w-10 shrink-0 rounded-full border-primary/40",
            listening
              ? "animate-pulse border-destructive/60 bg-destructive/15 text-destructive shadow-[0_0_18px_-4px] shadow-destructive/60"
              : "bg-primary/5 text-primary hover:bg-primary/15 hover:text-primary"
          )}
        >
          {transcribing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Mic className={cn("h-4 w-4", listening && "animate-pulse")} />
          )}
        </Button>

        {/* Champ texte */}
        <div className="min-w-0 flex-1 rounded-[inherit]">
          <label htmlFor="composer-input" className="sr-only">
            Votre message
          </label>
          <textarea
            id="composer-input"
            ref={ref}
            rows={1}
            value={value}
            disabled={disabled}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={
              listening
                ? "J'écoute, Monsieur…"
                : (placeholder ?? "Parle à JARVIS : recherche, diagnostic machine, code…")
            }
            className="max-h-[200px] w-full resize-none bg-transparent px-2.5 py-2.5 text-[15px] leading-relaxed outline-none placeholder:text-muted-foreground disabled:opacity-60"
          />
        </div>

        {/* Mode vocal continu */}
        {micSupported && (
          <Button
            type="button"
            variant="outline"
            onClick={() => onVoiceModeChange(!voiceMode)}
            aria-pressed={voiceMode}
            aria-label={voiceMode ? "Désactiver le mode conversation vocale" : "Activer le mode conversation vocale continue"}
            title={
              voiceMode
                ? "Mode conversation vocale actif — JARVIS vous répond et vous réécoute"
                : "Activer le mode conversation vocale continue"
            }
            className={cn(
              "h-10 w-10 shrink-0 rounded-full border-primary/40",
              voiceMode
                ? "border-gold/60 bg-gold/15 text-gold shadow-[0_0_18px_-4px] shadow-gold/70"
                : "bg-primary/5 text-primary/70 hover:bg-primary/15 hover:text-primary"
            )}
          >
            <Radio className="h-4 w-4" />
          </Button>
        )}

        {/* Envoyer / Arrêter */}
        {busy || speaking ? (
          <Button
            type="button"
            size="icon"
            onClick={onStop}
            aria-label="Arrêter la génération et la voix"
            className="h-10 w-10 shrink-0 rounded-full bg-destructive text-white hover:bg-destructive/90"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
          </Button>
        ) : (
          <Button
            type="button"
            size="icon"
            onClick={submit}
            disabled={!value.trim() || disabled}
            aria-label="Envoyer le message"
            className="h-10 w-10 shrink-0 rounded-full"
          >
            <ArrowUp className="h-4 w-4" />
          </Button>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 px-1.5 pb-0.5 pt-0.5">
        <p className="hidden items-center gap-1.5 text-[11px] text-muted-foreground sm:flex">
          <kbd className="rounded border border-primary/25 bg-primary/5 px-1 py-0.5 font-sans text-[10px]">
            Entrée
          </kbd>
          envoyer
          <span className="text-primary/40">·</span>
          <kbd className="rounded border border-primary/25 bg-primary/5 px-1 py-0.5 font-sans text-[10px]">
            Maj+Entrée
          </kbd>
          nouvelle ligne
          {voiceMode && (
            <>
              <span className="text-primary/40">·</span>
              <span className="inline-flex items-center gap-1 font-medium text-gold">
                <Radio className="h-3 w-3" /> conversation vocale active
              </span>
            </>
          )}
        </p>
        <p className="text-[11px] text-muted-foreground sm:hidden">
          {listening ? "● REC — parle…" : "Entrée pour envoyer"}
        </p>
        {speaking && (
          <span className="flex items-center gap-1 text-[11px] font-medium text-primary">
            <X className="h-3 w-3 animate-pulse" /> voix en cours — bouton stop pour couper
          </span>
        )}
      </div>
    </div>
  );
}
