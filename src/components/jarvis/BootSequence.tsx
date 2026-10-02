"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { ArcReactor } from "./ArcReactor";

/**
 * Séquence de démarrage plein écran de J.A.R.V.I.S. (~3.8 s).
 *
 * Timeline :
 * - 0.00–0.80 s : allumage du réacteur (boot-ignite)
 * - 0.45–2.72 s : 14 lignes de diagnostic (stagger 150 ms)
 * - 1.20–2.80 s : barre de progression cyan
 * - 2.75 s      : fondu des lignes, titre « J.A.R.V.I.S. » à 2.8 s
 * - 3.40–3.80 s : fondu de sortie global puis onDone()
 *
 * Un clic n'importe où saute immédiatement la séquence.
 */

interface BootLine {
  text: string;
  /** Badge « OK » or en fin de ligne */
  ok?: boolean;
  /** Valeur dorée en fin de ligne (ex. « ÉTABLIE ») */
  value?: string;
}

const LINES: BootLine[] = [
  { text: "INITIALISATION DU NOYAU J.A.R.V.I.S.", ok: true },
  { text: "CHARGEMENT DES MODULES COGNITIFS", ok: true },
  { text: "LIAISON HUGGING FACE", value: "ÉTABLIE" },
  { text: "CALIBRAGE DU SYNTHÉTISEUR VOCAL", ok: true },
  { text: "ANALYSE DES SYSTÈMES DE LA MACHINE", value: "100 %" },
  { text: "MOTEUR HOLOGRAPHIQUE", value: "EN LIGNE" },
  { text: "PROTOCOLES DE SÉCURITÉ STARK", ok: true },
  { text: "OUTILS EXTERNES · WEB / CODE / CALCUL", ok: true },
  { text: "INTERFACE VOCALE", value: "OPÉRATIONNELLE" },
  { text: "BASE DE DONNÉES LOCALE", value: "MONTÉE" },
  { text: "MÉMOIRE CONTEXTUELLE", value: "INDEXÉE" },
  { text: "SURVEILLANCE RADAR", value: "ACTIVE" },
  { text: "SYNCHRONISATION DES SOUS-ROUTINES", ok: true },
  { text: "TOUS SYSTÈMES NOMINAUX", ok: true },
];

/** Horodatage façon terminal, déterministe : 00:00.380, 00:00.532… */
function stamp(index: number): string {
  const t = 0.38 + index * 0.152;
  const s = Math.floor(t);
  const ms = Math.round((t - s) * 1000);
  return `00:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

const EXIT_AT_MS = 3400;
const DONE_AT_MS = 3800;

export function BootSequence({
  onDone,
  modelLabel,
}: {
  onDone: () => void;
  modelLabel?: string;
}): React.JSX.Element {
  const [leaving, setLeaving] = React.useState(false);
  const doneRef = React.useRef(false);
  const onDoneRef = React.useRef(onDone);

  React.useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  const finish = React.useCallback(() => {
    if (doneRef.current) return;
    doneRef.current = true;
    onDoneRef.current();
  }, []);

  React.useEffect(() => {
    const t1 = window.setTimeout(() => setLeaving(true), EXIT_AT_MS);
    const t2 = window.setTimeout(finish, DONE_AT_MS);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [finish]);

  return (
    <div
      role="status"
      aria-label="Séquence de démarrage JARVIS"
      onClick={finish}
      className={cn(
        "fixed inset-0 z-[100] flex cursor-pointer touch-manipulation flex-col items-center justify-center overflow-hidden transition-opacity duration-[400ms]",
        leaving ? "opacity-0" : "opacity-100",
      )}
      style={{ backgroundColor: "oklch(0.14 0.03 235)" }}
    >
      {/* Décor : grille holographique + scanlines + vignette */}
      <div aria-hidden className="hud-grid absolute inset-0 opacity-60" />
      <div aria-hidden className="hud-scanlines absolute inset-0" />
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 52%, oklch(0.09 0.03 238 / 55%) 100%)",
        }}
      />

      <div className="relative flex w-full max-w-[460px] flex-col items-center gap-6 px-6">
        {/* Réacteur qui s'allume */}
        <div className="animate-boot-ignite">
          <ArcReactor size={120} state="idle" />
        </div>

        {/* Console : lignes de diagnostic puis titre */}
        <div className="relative w-full">
          <div>
            {LINES.map((line, i) => (
              <div
                key={line.text}
                className="animate-boot-lifecycle flex items-baseline gap-2 font-mono text-[10.5px] leading-[1.75] text-primary/90 sm:text-[11px]"
                style={{ "--boot-delay": `${0.45 + i * 0.15}s` } as React.CSSProperties}
              >
                <span className="shrink-0 tabular-nums text-primary/45">{stamp(i)}</span>
                <span className="truncate">{line.text}</span>
                {line.ok ? (
                  <span className="ml-auto shrink-0 rounded-sm border border-gold/60 px-1 text-[9px] font-semibold uppercase tracking-widest text-gold">
                    OK
                  </span>
                ) : null}
                {line.value ? (
                  <span className="ml-auto shrink-0 text-[10px] uppercase tracking-wider text-gold/90">
                    {line.value}
                  </span>
                ) : null}
              </div>
            ))}
          </div>

          {/* Titre final */}
          <div className="animate-boot-title absolute inset-0 flex flex-col items-center justify-center gap-4 px-4 text-center">
            <h1 className="glow-text font-hud text-3xl font-semibold tracking-[0.35em] text-primary sm:text-5xl">
              <span className="animate-flicker">J.A.R.V.I.S.</span>
            </h1>
            <div aria-hidden className="relative h-px w-44 overflow-hidden bg-primary/25">
              <div className="animate-hud-sweep absolute inset-y-0 left-0 w-2/5 bg-gradient-to-r from-transparent via-primary to-transparent" />
            </div>
            <p className="hud-label text-primary/75">
              {modelLabel ?? "SYSTÈMES EN LIGNE — À VOTRE SERVICE, MONSIEUR"}
            </p>
          </div>
        </div>

        {/* Barre de progression */}
        <div className="h-[3px] w-full overflow-hidden rounded-full bg-primary/15">
          <div
            className="animate-boot-progress h-full w-full rounded-full"
            style={{
              background:
                "linear-gradient(90deg, color-mix(in oklch, var(--primary) 45%, transparent), var(--primary))",
            }}
          />
        </div>
      </div>
    </div>
  );
}
