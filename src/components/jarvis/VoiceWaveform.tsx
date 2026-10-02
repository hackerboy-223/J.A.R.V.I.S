"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Visualiseur vocal sur canvas (agent vocal J.A.R.V.I.S.).
 *
 * - `analyser` fourni (micro) : distribution de getByteFrequencyData sur `bars` barres.
 * - Sinon, simulation par état : idle = barres plates, listening = onde
 *   sinusoïdale douce, speaking = « voix » pseudo-aléatoire lissée.
 *
 * DPR-aware, arrondis avec fallback roundRect, glow via shadowBlur,
 * prefers-reduced-motion = rendu statique en une frame.
 */

type MaybeRoundRect = CanvasRenderingContext2D & {
  roundRect?: (x: number, y: number, w: number, h: number, radii?: number | number[]) => void;
};

function fillRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const rad = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  const c = ctx as MaybeRoundRect;
  if (typeof c.roundRect === "function") {
    c.roundRect(x, y, w, h, rad);
  } else {
    // Fallback manuel (compatibilité)
    ctx.moveTo(x + rad, y);
    ctx.lineTo(x + w - rad, y);
    ctx.arcTo(x + w, y, x + w, y + rad, rad);
    ctx.lineTo(x + w, y + h - rad);
    ctx.arcTo(x + w, y + h, x + w - rad, y + h, rad);
    ctx.lineTo(x + rad, y + h);
    ctx.arcTo(x, y + h, x, y + h - rad, rad);
    ctx.lineTo(x, y + rad);
    ctx.arcTo(x, y, x + rad, y, rad);
    ctx.closePath();
  }
  ctx.fill();
}

interface ParsedColor {
  l: number;
  c: number;
  h: number;
  ok: boolean;
}

function parsePrimary(raw: string): ParsedColor {
  const m = raw.match(/oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/);
  if (!m) return { l: 0, c: 0, h: 0, ok: false };
  return { l: Number(m[1]), c: Number(m[2]), h: Number(m[3]), ok: true };
}

export function VoiceWaveform({
  analyser,
  state,
  className,
  bars = 28,
}: {
  analyser: AnalyserNode | null;
  state: "idle" | "listening" | "speaking";
  className?: string;
  bars?: number;
}): React.JSX.Element {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const stateRef = React.useRef(state);
  const analyserRef = React.useRef<AnalyserNode | null>(analyser);

  React.useEffect(() => {
    stateRef.current = state;
  }, [state]);

  React.useEffect(() => {
    analyserRef.current = analyser;
  }, [analyser]);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const values: number[] = new Array<number>(bars).fill(0.05);
    let freqArr: Uint8Array<ArrayBuffer> | null = null;
    let raf = 0;
    let frame = 0;
    let color = parsePrimary(getComputedStyle(canvas).getPropertyValue("--primary"));
    let gradient: CanvasGradient | null = null;
    let gradKey = "";

    const css = (alpha: number, lighten = 0): string =>
      color.ok
        ? `oklch(${Math.min(1, color.l + lighten)} ${color.c} ${color.h} / ${alpha})`
        : `rgba(53, 224, 255, ${alpha})`;

    /** Calcule les valeurs cibles de chaque barre puis lisse. */
    const updateValues = (timeSec: number, instant: boolean): void => {
      const st = stateRef.current;
      const an = analyserRef.current;
      const smoothing = instant ? 1 : 0.28;

      if (an) {
        if (!freqArr || freqArr.length !== an.frequencyBinCount) {
          freqArr = new Uint8Array(an.frequencyBinCount);
        }
        an.getByteFrequencyData(freqArr);
        // On ignore les tout premiers bins (rumble DC) et le haut du spectre
        const usable = Math.max(bars, Math.floor(freqArr.length * 0.75));
        for (let i = 0; i < bars; i++) {
          const s = 2 + Math.floor((i * usable) / bars);
          const e = 2 + Math.floor(((i + 1) * usable) / bars);
          let sum = 0;
          let n = 0;
          for (let j = s; j < e && j < freqArr.length; j++) {
            sum += freqArr[j];
            n++;
          }
          const target = n > 0 ? sum / n / 255 : 0;
          values[i] += (target - values[i]) * smoothing;
        }
        return;
      }

      for (let i = 0; i < bars; i++) {
        let target: number;
        if (st === "idle") {
          target = 0.05;
        } else if (st === "listening") {
          target = 0.14 + 0.17 * (0.5 + 0.5 * Math.sin(timeSec * 2.4 + i * 0.55));
        } else {
          // Voix simulée : bruit pseudo-aléatoire lissé, enthousiaste
          target =
            0.12 +
            0.72 * Math.abs(Math.sin(i * 3.1 + timeSec * 7.1) * Math.sin(i * 1.7 - timeSec * 4.7)) +
            0.08 * Math.abs(Math.sin(i * 12.9 + timeSec * 11.3));
          target = Math.min(1, target);
        }
        values[i] += (target - values[i]) * (st === "idle" && !instant ? 0.08 : smoothing);
      }
    };

    const render = (timeSec: number, instant: boolean): void => {
      const dpr = window.devicePixelRatio || 1;
      const w = Math.round(canvas.clientWidth * dpr);
      const h = Math.round(canvas.clientHeight * dpr);
      if (w === 0 || h === 0) return;

      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
        gradient = null;
      }
      // Rafraîchit la couleur ~1 fois par seconde et demie (changement de thème)
      if (frame % 90 === 0) {
        color = parsePrimary(getComputedStyle(canvas).getPropertyValue("--primary"));
      }

      updateValues(timeSec, instant);

      const key = `${w}x${h}:${color.ok ? "t" : "f"}`;
      if (!gradient || gradKey !== key) {
        const g = ctx.createLinearGradient(0, h, 0, 0);
        g.addColorStop(0, css(0.55));
        g.addColorStop(0.55, css(0.85));
        g.addColorStop(1, css(0.95, 0.08));
        gradient = g;
        gradKey = key;
      }

      ctx.clearRect(0, 0, w, h);
      const st = stateRef.current;
      const pad = 2 * dpr;
      const usableH = h - pad * 2;
      const slot = w / bars;
      const barW = Math.max(2 * dpr, slot * 0.62);

      ctx.globalAlpha = st === "idle" ? 0.45 : st === "listening" ? 0.8 : 1;
      ctx.fillStyle = gradient ?? css(0.8);
      ctx.shadowColor = css(0.55);
      ctx.shadowBlur = 7 * dpr;

      for (let i = 0; i < bars; i++) {
        const bh = Math.max(2.5 * dpr, values[i] * usableH);
        const x = i * slot + (slot - barW) / 2;
        const y = h - pad - bh;
        fillRoundedRect(ctx, x, y, barW, bh, barW / 2);
      }
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1;
      frame++;
    };

    if (reduced) {
      // Une seule frame statique, pas de boucle
      render(0, true);
      return () => {
        /* rien à nettoyer */
      };
    }

    const loop = (t: number): void => {
      render(t / 1000, false);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [bars]);

  return (
    <div className={cn("relative h-full w-full", className)} aria-hidden="true">
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
    </div>
  );
}
