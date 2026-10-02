"use client";

import type * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Réacteur ARC de J.A.R.V.I.S. — rendu CSS pur (conic-gradients masqués).
 *
 * États :
 * - idle      : rotations lentes (30-40 s/tour), glow doux
 * - listening : anneau externe 4 s, teinte plus verte-cyan, glow moyen
 * - thinking  : rotations contrariées (2 s dans un sens, 3 s dans l'autre)
 * - speaking  : pulsation forte (reactor-pulse-strong 1.2 s), glow maximal
 * - offline   : gris, aucune animation
 */
export type ReactorState = "idle" | "listening" | "thinking" | "speaking" | "offline";

interface ReactorVisual {
  /** Triplet oklch « L C H » (sans le wrapper oklch()) */
  c: string;
  outerCls: string;
  outerDur: string;
  midCls: string;
  midDur: string;
  innerCls: string;
  innerDur: string;
  coreCls: string;
  coreDur: string;
  haloCls: string;
  haloDur: string;
  /** Multiplicateur d'intensité du glow (0-1) */
  glow: number;
}

const VISUALS: Record<ReactorState, ReactorVisual> = {
  idle: {
    c: "0.8 0.105 205",
    outerCls: "animate-jarvis-spin",
    outerDur: "36s",
    midCls: "animate-jarvis-spin-rev",
    midDur: "46s",
    innerCls: "animate-jarvis-spin",
    innerDur: "58s",
    coreCls: "animate-glow-pulse",
    coreDur: "3.4s",
    haloCls: "animate-glow-pulse",
    haloDur: "3.4s",
    glow: 0.55,
  },
  listening: {
    c: "0.84 0.12 193",
    outerCls: "animate-jarvis-spin",
    outerDur: "4s",
    midCls: "animate-jarvis-spin-rev",
    midDur: "10s",
    innerCls: "animate-jarvis-spin",
    innerDur: "7s",
    coreCls: "animate-reactor-pulse",
    coreDur: "1.7s",
    haloCls: "animate-glow-pulse",
    haloDur: "1.7s",
    glow: 0.8,
  },
  thinking: {
    c: "0.86 0.1 212",
    outerCls: "animate-jarvis-spin",
    outerDur: "2s",
    midCls: "animate-jarvis-spin-rev",
    midDur: "3s",
    innerCls: "animate-jarvis-spin",
    innerDur: "1.3s",
    coreCls: "animate-reactor-pulse",
    coreDur: "0.9s",
    haloCls: "animate-glow-pulse",
    haloDur: "0.9s",
    glow: 0.9,
  },
  speaking: {
    c: "0.84 0.12 203",
    outerCls: "animate-jarvis-spin",
    outerDur: "6s",
    midCls: "animate-jarvis-spin-rev",
    midDur: "8s",
    innerCls: "animate-jarvis-spin",
    innerDur: "5s",
    coreCls: "animate-reactor-pulse-strong",
    coreDur: "1.2s",
    haloCls: "animate-glow-pulse",
    haloDur: "1.2s",
    glow: 1,
  },
  offline: {
    c: "0.56 0.02 240",
    outerCls: "",
    outerDur: "0s",
    midCls: "",
    midDur: "0s",
    innerCls: "",
    innerDur: "0s",
    coreCls: "",
    coreDur: "0s",
    haloCls: "",
    haloDur: "0s",
    glow: 0.18,
  },
};

const ARIA_LABELS: Record<ReactorState, string> = {
  idle: "Réacteur JARVIS : en attente",
  listening: "Réacteur JARVIS : en écoute",
  thinking: "Réacteur JARVIS : traitement en cours",
  speaking: "Réacteur JARVIS : élocution en cours",
  offline: "Réacteur JARVIS : hors ligne",
};

export function ArcReactor({
  size = 200,
  state = "idle",
  className,
  label,
}: {
  size?: number;
  state?: ReactorState;
  className?: string;
  label?: string;
}): React.JSX.Element {
  const v = VISUALS[state];
  const col = (alpha: number): string => `oklch(${v.c} / ${alpha})`;

  // Épaisseur des anneaux masqués
  const outerW = Math.max(3, Math.round(size * 0.03));
  const midW = Math.max(2, Math.round(size * 0.022));
  const ringMask = (w: number): string =>
    `radial-gradient(farthest-side, transparent calc(100% - ${w}px), #000 calc(100% - ${w - 1}px))`;

  // Cadre carré centré occupant `frac` de la taille totale (sans transform,
  // pour ne pas entrer en conflit avec les animations de rotation)
  const box = (frac: number): React.CSSProperties => {
    const d = Math.round(size * frac);
    return {
      width: d,
      height: d,
      top: Math.round((size - d) / 2),
      left: Math.round((size - d) / 2),
    };
  };

  return (
    <div className={cn("flex flex-col items-center", className)} role="img" aria-label={ARIA_LABELS[state]}>
      <div className="relative" style={{ width: size, height: size }}>
        {/* Halo respirant */}
        <div
          aria-hidden
          className={cn("absolute inset-0 rounded-full", v.haloCls)}
          style={{
            background: `radial-gradient(circle, ${col(0.06 + 0.3 * v.glow)} 0%, transparent 62%)`,
            animationDuration: v.haloDur,
          }}
        />

        {/* Anneau externe segmenté (32 segments) */}
        <div
          aria-hidden
          className={cn("absolute inset-0 rounded-full", v.outerCls)}
          style={{
            background: `repeating-conic-gradient(from 0deg, ${col(0.85)} 0deg 5deg, transparent 5deg 11.25deg)`,
            WebkitMaskImage: ringMask(outerW),
            maskImage: ringMask(outerW),
            animationDuration: v.outerDur,
          }}
        />

        {/* Anneau médian (graduations fines, contre-rotation) */}
        <div
          aria-hidden
          className={cn("absolute rounded-full", v.midCls)}
          style={{
            ...box(0.8),
            background: `repeating-conic-gradient(from 6deg, ${col(0.55)} 0deg 1.5deg, transparent 1.5deg 9deg)`,
            WebkitMaskImage: ringMask(midW),
            maskImage: ringMask(midW),
            animationDuration: v.midDur,
          }}
        />

        {/* Anneau interne fin */}
        <div
          aria-hidden
          className={cn("absolute rounded-full", v.innerCls)}
          style={{
            ...box(0.62),
            border: `${Math.max(1, Math.round(size * 0.008))}px solid ${col(0.5)}`,
            boxShadow: `inset 0 0 ${Math.round(size * 0.05)}px ${col(0.25)}`,
            animationDuration: v.innerDur,
          }}
        />

        {/* Cœur lumineux (glow cyan via .reactor-glow, gris si hors ligne) */}
        <div
          aria-hidden
          className={cn(
            "absolute rounded-full reactor-glow",
            v.coreCls,
          )}
          style={{
            ...box(0.36),
            background: `radial-gradient(circle at 50% 42%, oklch(0.99 0.02 200 / ${0.6 + 0.35 * v.glow}) 0%, ${col(0.95)} 38%, ${col(0.45)} 72%, transparent 100%)`,
            animationDuration: v.coreDur,
            ...(state === "offline"
              ? { boxShadow: `0 0 ${Math.round(size * 0.04)}px ${col(0.25)}` }
              : {}),
          }}
        />

        {/* Aura teintée selon l'état (par-dessus le glow cyan de base) */}
        <div
          aria-hidden
          className="absolute rounded-full"
          style={{
            ...box(0.36),
            boxShadow: [
              `0 0 ${Math.round(size * 0.06 * v.glow)}px ${Math.round(size * 0.012 * v.glow)}px ${col(0.5)}`,
              `0 0 ${Math.round(size * 0.2 * v.glow)}px ${Math.round(size * 0.05 * v.glow)}px ${col(0.28)}`,
              `0 0 ${Math.round(size * 0.45 * v.glow)}px ${Math.round(size * 0.12 * v.glow)}px ${col(0.14)}`,
            ].join(", "),
          }}
        />

        {/* Point central incandescent */}
        <div
          aria-hidden
          className="absolute rounded-full"
          style={{
            ...box(0.09),
            background: `radial-gradient(circle, oklch(0.99 0.01 200) 0%, ${col(0.9)} 60%, transparent 100%)`,
          }}
        />
      </div>

      {label ? <div className="hud-label mt-3 text-center">{label}</div> : null}
    </div>
  );
}
