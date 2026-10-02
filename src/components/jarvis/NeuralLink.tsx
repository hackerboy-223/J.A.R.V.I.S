"use client";

import * as React from "react";
import { ExternalLink, Loader2, Mic, Send, Square, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { openStandalone, type MicFailure, type MicState } from "@/hooks/use-jarvis-voice";
import { ArcReactor } from "./ArcReactor";

export type NeuralPhase = "idle" | "listening" | "transcribing" | "thinking" | "speaking";

const PHASE_META: Record<
  NeuralPhase,
  { label: string; headline: string; className: string }
> = {
  idle: {
    label: "STANDBY",
    headline: "CORE ONLINE",
    className: "border-primary/40 bg-primary/10 text-primary",
  },
  listening: {
    label: "LISTENING",
    headline: "JE VOUS ÉCOUTE, MONSIEUR",
    className: "border-destructive/50 bg-destructive/10 text-destructive",
  },
  transcribing: {
    label: "TRANSCRIBING",
    headline: "ANALYSE DU CANAL VOCAL",
    className: "border-gold/50 bg-gold/10 text-gold",
  },
  thinking: {
    label: "THINKING",
    headline: "TRAITEMENT DES DONNÉES",
    className: "border-gold/50 bg-gold/10 text-gold",
  },
  speaking: {
    label: "SPEAKING",
    headline: "RÉPONSE VOCALE ACTIVE",
    className: "border-primary/50 bg-primary/15 text-primary",
  },
};

const MIC_HELP: Partial<Record<MicFailure, { title: string; hint: string; cta?: boolean }>> = {
  iframe: {
    title: "Micro bloqué dans l’aperçu",
    hint: "Ouvrez J.A.R.V.I.S. dans un onglet dédié pour autoriser le microphone.",
    cta: true,
  },
  denied: {
    title: "Microphone refusé",
    hint: "Autorisez le microphone dans les permissions du site puis rechargez la page.",
  },
  "no-device": {
    title: "Aucun microphone détecté",
    hint: "Branchez ou activez un microphone, ou utilisez le terminal texte.",
  },
  busy: {
    title: "Microphone occupé",
    hint: "Fermez l’application qui utilise déjà le microphone puis réessayez.",
  },
  insecure: {
    title: "Contexte non sécurisé",
    hint: "Le microphone nécessite localhost ou HTTPS.",
  },
  unknown: {
    title: "Microphone indisponible",
    hint: "Le terminal texte reste opérationnel.",
  },
};

function VoiceBars({ active }: { active: boolean }) {
  return (
    <div className="flex h-10 items-center justify-center gap-1" aria-hidden="true">
      {Array.from({ length: 18 }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "w-1 rounded-full bg-primary/70 shadow-[0_0_8px] shadow-primary/40",
            active ? "jarvis-voice-bar" : "h-1.5 opacity-35"
          )}
          style={
            active
              ? ({
                  "--voice-delay": `${(i % 7) * 70}ms`,
                  "--voice-height": `${10 + ((i * 11) % 26)}px`,
                } as React.CSSProperties)
              : undefined
          }
        />
      ))}
    </div>
  );
}

export function NeuralLink({
  open,
  phase,
  micState,
  micSupported,
  micError,
  transcript,
  responseText,
  statusText,
  streaming,
  speaking,
  onClose,
  onMicToggle,
  onSendText,
  onStop,
}: {
  open: boolean;
  phase: NeuralPhase;
  micState: MicState;
  micSupported: boolean;
  micError: MicFailure | null;
  micAnalyser: AnalyserNode | null;
  speakAnalyser: AnalyserNode | null;
  transcript: string | null;
  responseText: string | null;
  statusText: string | null;
  streaming: boolean;
  speaking: boolean;
  onClose: () => void;
  onMicToggle: () => void;
  onSendText: (text: string) => void;
  onStop: () => void;
}): React.JSX.Element | null {
  const [value, setValue] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  React.useEffect(() => {
    if (open && !micSupported) inputRef.current?.focus();
  }, [open, micSupported]);

  if (!open) return null;

  const meta = PHASE_META[phase];
  const busy = streaming || speaking || micState === "transcribing";
  const help = micError ? MIC_HELP[micError] ?? MIC_HELP.unknown : null;

  const submit = () => {
    const clean = value.trim();
    if (!clean || busy) return;
    onSendText(clean);
    setValue("");
  };

  const mainText =
    responseText ||
    (phase === "listening" && transcript ? transcript : null) ||
    (phase === "thinking" ? statusText || transcript || "Analyse en cours…" : null) ||
    (phase === "transcribing" ? transcript || "Phrase reçue…" : null) ||
    (phase === "listening" ? "Parlez naturellement, Monsieur…" : null);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Interface vocale J.A.R.V.I.S."
      className="dark fixed inset-0 z-[70] overflow-hidden bg-[#03070d] text-foreground"
    >
      <div aria-hidden className="hud-grid absolute inset-0 opacity-55" />
      <div aria-hidden className="hud-scanlines absolute inset-0 opacity-70" />
      <div
        aria-hidden
        className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,212,255,0.10),transparent_32%,rgba(0,0,0,0.86)_78%)]"
      />

      <div aria-hidden className="pointer-events-none absolute inset-4 sm:inset-7">
        <span className="hud-corner-tl" />
        <span className="hud-corner-tr" />
        <span className="hud-corner-bl" />
        <span className="hud-corner-br" />
      </div>

      <header className="absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-4 p-4 sm:p-6">
        <div>
          <p className="glow-text font-hud text-sm font-bold tracking-[0.32em] text-primary">
            J.A.R.V.I.S.
          </p>
          <p className="hud-label mt-1">VOICE COMMAND INTERFACE</p>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={cn(
              "rounded-sm border px-2.5 py-1 font-mono text-[10px] font-bold tracking-[0.16em]",
              meta.className
            )}
          >
            {meta.label}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center border border-primary/25 bg-primary/5 text-primary transition hover:bg-primary/15"
            aria-label="Fermer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </header>

      <main className="relative z-10 flex h-full flex-col items-center justify-center px-4 pb-32 pt-24 sm:px-8">
        <div className="relative flex items-center justify-center">
          <div aria-hidden className="jarvis-orbit-ring absolute h-64 w-64 rounded-full sm:h-80 sm:w-80" />
          <div aria-hidden className="jarvis-orbit-ring jarvis-orbit-ring-reverse absolute h-52 w-52 rounded-full sm:h-68 sm:w-68" />
          <ArcReactor
            size={phase === "idle" ? 150 : 168}
            state={
              phase === "listening"
                ? "listening"
                : phase === "thinking" || phase === "transcribing"
                  ? "thinking"
                  : phase === "speaking"
                    ? "speaking"
                    : "idle"
            }
          />
        </div>

        <h2 className="glow-text mt-8 text-center font-hud text-sm font-semibold tracking-[0.25em] text-primary sm:text-base">
          {meta.headline}
        </h2>

        <VoiceBars active={phase === "listening" || phase === "speaking"} />

        {phase === "listening" && (
          <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.2em] text-primary/70">
            Transcription en temps réel · mains libres
          </p>
        )}

        <section className="mt-3 min-h-28 w-full max-w-2xl border border-primary/20 bg-black/25 p-4 backdrop-blur-sm">
          {mainText ? (
            <p className="whitespace-pre-wrap text-center text-sm leading-7 text-foreground/90 sm:text-base">
              {mainText}
            </p>
          ) : (
            <p className="text-center font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
              En attente d’instructions, Monsieur.
            </p>
          )}
        </section>

        {help && phase === "idle" && !busy && (
          <div className="mt-4 w-full max-w-2xl border border-gold/35 bg-gold/10 p-3 text-left">
            <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-gold">
              {help.title}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-gold/80">{help.hint}</p>
            {help.cta && (
              <button
                type="button"
                onClick={openStandalone}
                className="mt-2 inline-flex items-center gap-1.5 border border-gold/35 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wider text-gold"
              >
                <ExternalLink className="h-3 w-3" /> Ouvrir dans un onglet
              </button>
            )}
          </div>
        )}
      </main>

      <footer className="absolute inset-x-0 bottom-0 z-20 border-t border-primary/20 bg-[#03070d]/95 px-4 py-4 backdrop-blur sm:px-6">
        <div className="mx-auto flex w-full max-w-3xl items-center gap-2">
          <button
            type="button"
            onClick={onMicToggle}
            disabled={!micSupported || micState === "transcribing"}
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center border transition",
              micState === "listening"
                ? "border-destructive/60 bg-destructive/15 text-destructive"
                : "border-primary/35 bg-primary/10 text-primary hover:bg-primary/20",
              (!micSupported || micState === "transcribing") && "opacity-40"
            )}
            aria-label={micState === "listening" ? "Arrêter l'écoute" : "Parler"}
          >
            {micState === "transcribing" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Mic className="h-4 w-4" />
            )}
          </button>

          <input
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
            }}
            placeholder="Speak freely, sir…"
            disabled={busy}
            className="h-11 min-w-0 flex-1 border border-primary/25 bg-black/30 px-3 font-mono text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/60"
          />

          {busy ? (
            <button
              type="button"
              onClick={onStop}
              className="flex h-11 w-11 shrink-0 items-center justify-center border border-destructive/50 bg-destructive/10 text-destructive"
              aria-label="Arrêter"
            >
              <Square className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={!value.trim()}
              className="flex h-11 w-11 shrink-0 items-center justify-center border border-primary/40 bg-primary/15 text-primary transition hover:bg-primary/25 disabled:opacity-35"
              aria-label="Envoyer"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </div>
      </footer>
    </div>
  );
}
