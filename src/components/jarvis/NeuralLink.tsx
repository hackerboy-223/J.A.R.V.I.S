"use client";

import * as React from "react";
import { ExternalLink, Loader2, Mic, Send, Square, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { openStandalone, type MicFailure, type MicState } from "@/hooks/use-jarvis-voice";

/**
 * INTERFACE HOLOGRAPHIQUE — animation plein écran façon « réseau de neurones » (style Techenclair).
 *
 * Canvas 2D avec projection 3D :
 *  - nuage de nœuds dans un ellipsoïde (RNG seedé → déterministe)
 *  - connexions vers les plus proches voisins
 *  - impulsions lumineuses qui voyagent le long des connexions (réactions en chaîne)
 *  - rotation lente + parallaxe pointeur
 *
 * Réactivité vocale :
 *  - ÉCOUTE   : niveau du micro (AnalyserNode) → le réseau vibre, impulsions centripètes
 *  - TRAITEMENT: scintillement or, impulsions rapides
 *  - ÉLOCUTION : amplitude réelle de la voix JARVIS (AnalyserNode) → ondes concentriques
 *    qui traversent le réseau + impulsions centrifuges (le cerveau « parle »)
 *
 * Fallback clavier intégré (champ texte) si le micro est indisponible.
 */

export type NeuralPhase = "idle" | "listening" | "transcribing" | "thinking" | "speaking";

interface NeuralSignals {
  phase: NeuralPhase;
  micAnalyser: AnalyserNode | null;
  speakAnalyser: AnalyserNode | null;
}

// ============================================================
// Utilitaires
// ============================================================

/** RNG déterministe (mulberry32) — layout stable du réseau */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface ParsedColor {
  l: number;
  c: number;
  h: number;
  ok: boolean;
}

function parseOklch(raw: string): ParsedColor {
  const m = raw.match(/oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/);
  if (!m) return { l: 0, c: 0, h: 0, ok: false };
  return { l: Number(m[1]), c: Number(m[2]), h: Number(m[3]), ok: true };
}

/** Fabrique un sprite de halo (dégradé radial) pour dessiner les nœuds sans shadowBlur */
function makeGlowSprite(col: (alpha: number, lighten?: number) => string): HTMLCanvasElement {
  const s = 64;
  const c = document.createElement("canvas");
  c.width = s;
  c.height = s;
  const g = c.getContext("2d");
  if (!g) return c;
  const grad = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grad.addColorStop(0, "rgba(255,255,255,0.95)");
  grad.addColorStop(0.22, col(0.9, 0.06));
  grad.addColorStop(0.55, col(0.32));
  grad.addColorStop(1, col(0));
  g.fillStyle = grad;
  g.fillRect(0, 0, s, s);
  return c;
}

// ============================================================
// Moteur de rendu du réseau neuronal
// ============================================================

interface NeuralNode {
  x: number;
  y: number;
  z: number;
  /** distance radiale normalisée (0 = centre, 1 = bord) */
  d: number;
  r: number;
  phase: number;
  speed: number;
  flash: number;
}

interface NeuralEdge {
  a: number;
  b: number;
  /** index du nœud le plus proche du centre */
  inner: number;
  outer: number;
  len: number;
}

interface NeuralPulse {
  edge: number;
  t: number;
  dur: number;
  /** +1 : centre → extérieur, -1 : extérieur → centre */
  dir: 1 | -1;
  gold: boolean;
  hops: number;
}

interface NeuralWave {
  r: number;
  a: number;
}

function startNeuralEngine(
  canvas: HTMLCanvasElement,
  signals: React.RefObject<NeuralSignals>
): () => void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => undefined;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const rng = mulberry32(0x4a525653); // "JARS" :)

  // ---- Construction du réseau ----
  const nodes: NeuralNode[] = [];
  const NODE_COUNT = 108;
  while (nodes.length < NODE_COUNT) {
    let x = rng() * 2 - 1;
    let y = rng() * 2 - 1;
    let z = rng() * 2 - 1;
    // ellipsoïde aplati (forme « cerveau »), densité variable via re-échantillonnage
    if ((x * x + (y / 0.62) * (y / 0.62) + (z / 0.82) * (z / 0.82)) > 1) continue;
    if (rng() < 0.3) {
      // resserre un tiers des nœuds vers le cœur → densité nucléaire
      x *= 0.55;
      y *= 0.55;
      z *= 0.55;
    }
    const d = Math.sqrt(x * x + y * y + z * z);
    nodes.push({
      x,
      y,
      z,
      d: Math.min(1.15, d),
      r: 1.5 + rng() * 1.9,
      phase: rng() * Math.PI * 2,
      speed: 0.5 + rng() * 1.6,
      flash: 0,
    });
  }

  // Connexions : 3 plus proches voisins par nœud
  const edgeSet = new Set<string>();
  const edges: NeuralEdge[] = [];
  for (let i = 0; i < nodes.length; i++) {
    const dists: Array<{ j: number; d2: number }> = [];
    for (let j = 0; j < nodes.length; j++) {
      if (i === j) continue;
      const dx = nodes[i].x - nodes[j].x;
      const dy = nodes[i].y - nodes[j].y;
      const dz = nodes[i].z - nodes[j].z;
      dists.push({ j, d2: dx * dx + dy * dy + dz * dz });
    }
    dists.sort((a, b) => a.d2 - b.d2);
    for (let k = 0; k < 3 && k < dists.length; k++) {
      const j = dists[k].j;
      const key = i < j ? `${i}-${j}` : `${j}-${i}`;
      if (edgeSet.has(key)) continue;
      edgeSet.add(key);
      const len = Math.sqrt(dists[k].d2);
      const inner = nodes[i].d <= nodes[j].d ? i : j;
      const outer = inner === i ? j : i;
      edges.push({ a: i, b: j, inner, outer, len });
    }
  }

  // Étoiles de fond (espace écran, léger scintillement)
  const stars: Array<{ x: number; y: number; r: number; phase: number; sp: number }> = [];
  for (let i = 0; i < 72; i++) {
    stars.push({
      x: rng(),
      y: rng(),
      r: 0.4 + rng() * 1.1,
      phase: rng() * Math.PI * 2,
      sp: 0.4 + rng() * 1.4,
    });
  }

  // ---- Couleurs (lues depuis le thème, re-lues périodiquement) ----
  let primary = parseOklch(getComputedStyle(canvas).getPropertyValue("--primary"));
  let gold = parseOklch(getComputedStyle(canvas).getPropertyValue("--gold"));
  const cyan = (a: number, lighten = 0): string =>
    primary.ok
      ? `oklch(${Math.min(1, primary.l + lighten)} ${primary.c} ${primary.h} / ${a})`
      : `rgba(53, 224, 255, ${a})`;
  const amber = (a: number, lighten = 0): string =>
    gold.ok
      ? `oklch(${Math.min(1, gold.l + lighten)} ${gold.c} ${gold.h} / ${a})`
      : `rgba(255, 186, 66, ${a})`;

  let spriteCyan = makeGlowSprite(cyan);
  let spriteGold = makeGlowSprite(amber);

  // ---- État d'animation ----
  const pulses: NeuralPulse[] = [];
  const waves: NeuralWave[] = [];
  let smoothed = 0.12; // niveau lissé (énergie globale 0-1)
  let lastWaveAt = -1;
  let rotY = 0;
  let rotX = 0.1;
  let parTX = 0;
  let parTY = 0;
  let parX = 0;
  let parY = 0;
  let last = performance.now();
  let frame = 0;
  let raf = 0;
  let freqArr: Uint8Array<ArrayBuffer> | null = null;

  const onPointer = (e: PointerEvent) => {
    const rect = canvas.getBoundingClientRect();
    parTX = ((e.clientX - rect.left) / rect.width - 0.5) * 0.55;
    parTY = ((e.clientY - rect.top) / rect.height - 0.5) * 0.4;
  };
  window.addEventListener("pointermove", onPointer);

  /** RMS de l'analyser (0-1), ou valeur négative si indisponible */
  const readAnalyser = (an: AnalyserNode | null): number => {
    if (!an) return -1;
    if (!freqArr || freqArr.length !== an.frequencyBinCount) {
      freqArr = new Uint8Array(an.frequencyBinCount);
    }
    an.getByteFrequencyData(freqArr);
    let sum = 0;
    const n = Math.min(freqArr.length, 96);
    for (let i = 2; i < n; i++) sum += freqArr[i];
    return sum / Math.max(1, n - 2) / 255;
  };

  const spawnPulse = (edgeIdx: number, dir: 1 | -1, goldPulse: boolean, hops: number): void => {
    if (pulses.length > 90) return;
    const e = edges[edgeIdx];
    pulses.push({
      edge: edgeIdx,
      t: 0,
      dur: 0.3 + e.len * 0.45,
      dir,
      gold: goldPulse,
      hops,
    });
  };

  const render = (now: number): void => {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const t = now / 1000;
    const ph = signals.current?.phase ?? "idle";

    // Re-lecture des couleurs ~ toutes les 2 s (changement de thème)
    if (frame % 120 === 0) {
      const p2 = parseOklch(getComputedStyle(canvas).getPropertyValue("--primary"));
      const g2 = parseOklch(getComputedStyle(canvas).getPropertyValue("--gold"));
      if (p2.ok && (p2.l !== primary.l || p2.h !== primary.h || !primary.ok)) {
        primary = p2;
        spriteCyan = makeGlowSprite(cyan);
      }
      if (g2.ok && (g2.l !== gold.l || g2.h !== gold.h || !gold.ok)) {
        gold = g2;
        spriteGold = makeGlowSprite(amber);
      }
    }

    // ---- Niveau cible selon la phase ----
    let target: number;
    if (ph === "speaking") {
      const v = readAnalyser(signals.current?.speakAnalyser ?? null);
      target =
        v >= 0
          ? Math.min(1, v * 2.6)
          : Math.min(1, 0.34 + 0.34 * Math.abs(Math.sin(t * 5.2) * Math.sin(t * 2.3)) + 0.08 * Math.sin(t * 13.7));
    } else if (ph === "listening") {
      const v = readAnalyser(signals.current?.micAnalyser ?? null);
      target = v >= 0 ? Math.min(1, v * 2.4) : 0.2 + 0.1 * Math.sin(t * 2.2) + 0.05 * Math.sin(t * 3.9);
    } else if (ph === "thinking" || ph === "transcribing") {
      target = 0.44 + 0.2 * Math.sin(t * 5.4) + 0.09 * Math.sin(t * 9.7);
    } else {
      target = 0.1 + 0.05 * Math.sin(t * 0.9);
    }
    smoothed += (Math.max(0, Math.min(1, target)) - smoothed) * Math.min(1, dt * 7.5);
    const energy = smoothed;

    // ---- Ondes concentriques pendant l'élocution ----
    if (ph === "speaking" && energy > 0.26 && t - lastWaveAt > 0.3) {
      waves.push({ r: 0.05, a: Math.min(1, energy + 0.25) });
      lastWaveAt = t;
    }
    for (let i = waves.length - 1; i >= 0; i--) {
      const w = waves[i];
      w.r += dt * 1.15;
      w.a *= 1 - dt * 1.15;
      if (w.a < 0.02 || w.r > 1.5) waves.splice(i, 1);
    }

    // ---- Impulsions le long des connexions ----
    const thinking = ph === "thinking" || ph === "transcribing";
    const speaking = ph === "speaking";
    const listening = ph === "listening";
    const rate = 0.8 + energy * 9 + (thinking ? 9 : 0) + (speaking ? 7 : 0);
    if (Math.random() < Math.min(0.9, rate * dt)) {
      const idx = Math.floor(Math.random() * edges.length);
      const dir: 1 | -1 = listening ? -1 : 1;
      const goldP = thinking ? Math.random() < 0.72 : Math.random() < 0.1;
      spawnPulse(idx, dir, goldP, 0);
    }
    for (let i = pulses.length - 1; i >= 0; i--) {
      const p = pulses[i];
      p.t += dt / p.dur;
      if (p.t >= 1) {
        const e = edges[p.edge];
        const arrival = p.dir === 1 ? e.outer : e.inner;
        nodes[arrival].flash = 1;
        // réaction en chaîne (propagation du signal)
        if (p.hops < 2 && Math.random() < 0.42) {
          const candidates = edges
            .map((ed, k) => ({ ed, k }))
            .filter(({ ed }) => ed.a === arrival || ed.b === arrival);
          if (candidates.length > 0) {
            const pick = candidates[Math.floor(Math.random() * candidates.length)];
            spawnPulse(pick.k, p.dir, p.gold, p.hops + 1);
          }
        }
        pulses.splice(i, 1);
      }
    }
    for (const n of nodes) {
      if (n.flash > 0) n.flash = Math.max(0, n.flash - dt * 2.4);
    }

    // ---- Rotation + parallaxe ----
    parX += (parTX - parX) * Math.min(1, dt * 3);
    parY += (parTY - parY) * Math.min(1, dt * 3);
    rotY += dt * (0.1 + energy * 0.22);
    rotX = 0.12 * Math.sin(t * 0.13) + parY;
    const cosY = Math.cos(rotY + parX);
    const sinY = Math.sin(rotY + parX);
    const cosX = Math.cos(rotX);
    const sinX = Math.sin(rotX);

    // ---- Projection ----
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.round(canvas.clientWidth * dpr);
    const h = Math.round(canvas.clientHeight * dpr);
    if (w === 0 || h === 0) {
      raf = requestAnimationFrame(render);
      return;
    }
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    const cx = w / 2;
    const cy = h / 2;
    const unit = Math.min(w, h) * 0.46;
    const F = 3.2;

    const px = new Float32Array(nodes.length);
    const py = new Float32Array(nodes.length);
    const ps = new Float32Array(nodes.length); // échelle de perspective
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i];
      const x1 = n.x * cosY - n.z * sinY;
      const z1 = n.x * sinY + n.z * cosY;
      const y2 = n.y * cosX - z1 * sinX;
      const z2 = n.y * sinX + z1 * cosX;
      const s = F / (F + z2);
      px[i] = cx + x1 * unit * s;
      py[i] = cy + y2 * unit * s * 0.94;
      ps[i] = s;
    }

    ctx.clearRect(0, 0, w, h);

    // ---- Étoiles ----
    for (const st of stars) {
      const tw = 0.5 + 0.5 * Math.sin(t * st.sp + st.phase);
      ctx.globalAlpha = 0.12 + 0.3 * tw;
      ctx.fillStyle = cyan(0.8);
      ctx.beginPath();
      ctx.arc(st.x * w, st.y * h, st.r * dpr, 0, Math.PI * 2);
      ctx.fill();
    }

    // ---- Anneaux orbitaux (cercles 3D projetés) ----
    const drawRing = (radius: number, tilt: number, spin: number, alpha: number, color: string): void => {
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(1, dpr * 0.8);
      ctx.beginPath();
      const SEG = 72;
      for (let k = 0; k <= SEG; k++) {
        const a = (k / SEG) * Math.PI * 2 + spin;
        let rx = Math.cos(a) * radius;
        const ry = Math.sin(a) * radius;
        const rz = rx * tilt;
        rx *= Math.cos(tilt * 0.7);
        const x1 = rx * cosY - rz * sinY;
        const z1 = rx * sinY + rz * cosY;
        const y2 = ry * cosX - z1 * sinX;
        const z2 = ry * sinX + z1 * cosX;
        const s = F / (F + z2);
        const X = cx + x1 * unit * s;
        const Y = cy + y2 * unit * s * 0.94;
        if (k === 0) ctx.moveTo(X, Y);
        else ctx.lineTo(X, Y);
      }
      ctx.globalAlpha = alpha;
      ctx.stroke();
    };
    drawRing(1.18, 0.42, t * 0.12, 0.16 + energy * 0.12, cyan(0.85));
    drawRing(1.34, -0.3, -t * 0.08, 0.1 + energy * 0.1, cyan(0.7));

    // ---- Connexions ----
    ctx.lineWidth = Math.max(1, dpr * 0.7);
    for (const e of edges) {
      const sAvg = (ps[e.a] + ps[e.b]) / 2;
      const flashBoost = (nodes[e.a].flash + nodes[e.b].flash) * 0.5;
      const alpha = (0.1 + 0.26 * energy + flashBoost) * Math.max(0.3, Math.min(1, sAvg * 0.95));
      ctx.globalAlpha = Math.min(0.85, alpha);
      ctx.strokeStyle = thinking && (e.a + e.b) % 3 === 0 ? amber(0.8) : cyan(0.8);
      ctx.beginPath();
      ctx.moveTo(px[e.a], py[e.a]);
      ctx.lineTo(px[e.b], py[e.b]);
      ctx.stroke();
    }

    // ---- Nœuds ----
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i];
      const pulse = 0.5 + 0.5 * Math.sin(t * n.speed + n.phase);
      let waveBoost = 0;
      for (const wv of waves) {
        const dd = n.d - wv.r;
        waveBoost += wv.a * Math.exp(-(dd * dd) / 0.02);
      }
      const glow = Math.min(1.5, 0.32 + energy * 0.45 + waveBoost * 0.85 + n.flash * 0.9);
      const size = n.r * dpr * ps[i] * (3.4 + pulse * 1.1 + n.flash * 2.6 + waveBoost * 1.6);
      ctx.globalAlpha = Math.min(1, (0.42 + glow * 0.58) * Math.max(0.35, Math.min(1, ps[i])));
      const sprite = thinking && (n.phase * 10) % 3 < 1 ? spriteGold : spriteCyan;
      ctx.drawImage(sprite, px[i] - size, py[i] - size, size * 2, size * 2);
    }

    // ---- Impulsions ----
    for (const p of pulses) {
      const e = edges[p.edge];
      const from = p.dir === 1 ? e.inner : e.outer;
      const to = p.dir === 1 ? e.outer : e.inner;
      const x = px[from] + (px[to] - px[from]) * p.t;
      const y = py[from] + (py[to] - py[from]) * p.t;
      const fade = Math.sin(Math.PI * Math.min(1, Math.max(0, p.t)));
      const size = (6 + 8 * fade) * dpr * ps[to];
      ctx.globalAlpha = 0.55 + 0.45 * fade;
      ctx.drawImage(p.gold ? spriteGold : spriteCyan, x - size, y - size, size * 2, size * 2);
      // trace courte derrière l'impulsion
      const back = Math.max(0, p.t - 0.16);
      const bx = px[from] + (px[to] - px[from]) * back;
      const by = py[from] + (py[to] - py[from]) * back;
      ctx.globalAlpha = 0.35 * fade;
      ctx.strokeStyle = p.gold ? amber(0.9) : cyan(0.9);
      ctx.lineWidth = Math.max(1, dpr * 1.1);
      ctx.beginPath();
      ctx.moveTo(bx, by);
      ctx.lineTo(x, y);
      ctx.stroke();
    }

    // ---- Cœur central (noyau du réseau) ----
    const coreR = (30 + energy * 42) * dpr;
    const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
    coreGrad.addColorStop(0, "rgba(255,255,255,0.9)");
    coreGrad.addColorStop(0.18, thinking ? amber(0.75) : cyan(0.8));
    coreGrad.addColorStop(0.55, thinking ? amber(0.22) : cyan(0.22));
    coreGrad.addColorStop(1, thinking ? amber(0) : cyan(0));
    ctx.globalAlpha = 0.55 + energy * 0.4;
    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
    ctx.fill();

    // Anneau du noyau + ondes visibles
    ctx.globalAlpha = 0.5 + energy * 0.3;
    ctx.strokeStyle = thinking ? amber(0.9) : cyan(0.9);
    ctx.lineWidth = Math.max(1, dpr * 1.2);
    ctx.beginPath();
    ctx.arc(cx, cy, (16 + energy * 22) * dpr, 0, Math.PI * 2);
    ctx.stroke();
    for (const wv of waves) {
      ctx.globalAlpha = wv.a * 0.3;
      ctx.lineWidth = Math.max(1, dpr * 1.4);
      ctx.beginPath();
      ctx.arc(cx, cy, wv.r * unit, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.globalAlpha = 1;
    frame++;

    if (!reduced) raf = requestAnimationFrame(render);
  };

  if (reduced) {
    // Une seule frame statique
    last = performance.now();
    render(last);
    return () => window.removeEventListener("pointermove", onPointer);
  }

  raf = requestAnimationFrame(render);
  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener("pointermove", onPointer);
  };
}

// ============================================================
// Composant
// ============================================================

const PHASE_META: Record<
  NeuralPhase,
  { label: string; headline: string; pillCls: string }
> = {
  idle: {
    label: "VEILLE",
    headline: "INTERFACE HOLOGRAPHIQUE ÉTABLIE",
    pillCls: "border-primary/40 bg-primary/10 text-primary",
  },
  listening: {
    label: "ÉCOUTE",
    headline: "JE VOUS ÉCOUTE, MONSIEUR",
    pillCls: "border-destructive/50 bg-destructive/10 text-destructive",
  },
  transcribing: {
    label: "TRANSCRIPTION",
    headline: "ANALYSE DE LA VOIX…",
    pillCls: "border-gold/50 bg-gold/10 text-gold",
  },
  thinking: {
    label: "TRAITEMENT",
    headline: "TRAITEMENT DES DONNÉES…",
    pillCls: "border-gold/50 bg-gold/10 text-gold",
  },
  speaking: {
    label: "ÉLOCUTION",
    headline: "J.A.R.V.I.S. À VOTRE SERVICE",
    pillCls: "border-primary/50 bg-primary/15 text-primary",
  },
};

// ============================================================
// Aide « micro bloqué » : la raison la plus courante est que la page
// est intégrée dans un panneau d'aperçu (iframe) — les navigateurs
// y interdisent le micro. On explique et on propose la solution.
// ============================================================

const MIC_HELP: Partial<Record<MicFailure, { title: string; hint: string; cta?: boolean }>> = {
  iframe: {
    title: "Micro bloqué par le panneau d'aperçu",
    hint: "Le navigateur interdit le micro dans une page intégrée. Ouvre J.A.R.V.I.S. dans un onglet dédié pour lui parler — ou écris ci-dessous.",
    cta: true,
  },
  denied: {
    title: "Micro refusé",
    hint: "Clique sur le cadenas 🔒 dans la barre d’adresse → Microphone → Autoriser, puis recharge la page.",
  },
  "no-device": {
    title: "Aucun micro détecté",
    hint: "Branche ou active un microphone — ou écris à J.A.R.V.I.S. ci-dessous.",
  },
  busy: {
    title: "Micro occupé",
    hint: "Le micro est utilisé par une autre application. Ferme-la puis réessaie.",
  },
  insecure: {
    title: "Connexion non sécurisée",
    hint: "L’accès au microphone exige une page HTTPS.",
  },
  unknown: {
    title: "Micro indisponible",
    hint: "Écris à J.A.R.V.I.S. ci-dessous — il te répondra à voix haute.",
  },
};

export function NeuralLink({
  open,
  phase,
  micState,
  micSupported,
  micError,
  micAnalyser,
  speakAnalyser,
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
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const signalsRef = React.useRef<NeuralSignals>({
    phase,
    micAnalyser,
    speakAnalyser,
  });
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [value, setValue] = React.useState("");
  const [revealed, setRevealed] = React.useState(0);

  // Signaux toujours à jour pour la boucle de rendu
  React.useEffect(() => {
    signalsRef.current.phase = phase;
  }, [phase]);
  React.useEffect(() => {
    signalsRef.current.micAnalyser = micAnalyser;
  }, [micAnalyser]);
  React.useEffect(() => {
    signalsRef.current.speakAnalyser = speakAnalyser;
  }, [speakAnalyser]);

  // Moteur canvas
  React.useEffect(() => {
    if (!open) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    return startNeuralEngine(canvas, signalsRef);
  }, [open]);

  // ÉCHAP pour fermer
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Machine à écrire : la réponse de JARVIS se révèle pendant l'élocution.
  // PERF : append-only — le texte arrive désormais phrase par phrase (TTS
  // streaming) ; on garde la progression au lieu de re-typer depuis zéro.
  const prevTextRef = React.useRef<string | null>(null);
  React.useEffect(() => {
    const prev = prevTextRef.current;
    prevTextRef.current = responseText;
    if (!responseText) {
      setRevealed(0);
      return;
    }
    const isAppend = !!prev && responseText.startsWith(prev);
    if (!isAppend) setRevealed(0);
    const id = window.setInterval(() => {
      setRevealed((r) => {
        if (r >= responseText.length) {
          window.clearInterval(id);
          return r;
        }
        return r + 3; // ~125 caractères/s : suit le rythme de la voix
      });
    }, 24);
    return () => window.clearInterval(id);
  }, [responseText]);
  // Fin d'élocution → révèle tout
  React.useEffect(() => {
    if (phase !== "speaking" && responseText) {
      setRevealed(responseText.length);
    }
  }, [phase, responseText]);

  // Focus clavier si micro indisponible
  React.useEffect(() => {
    if (open && !micSupported) {
      inputRef.current?.focus();
    }
  }, [open, micSupported]);

  if (!open) return null;

  const meta = PHASE_META[phase];
  const busy = streaming || speaking || micState === "transcribing";
  const micHelp = micError && phase === "idle" && !busy ? (MIC_HELP[micError] ?? MIC_HELP.unknown) : null;

  const submit = () => {
    const text = value.trim();
    if (!text || busy) return;
    onSendText(text);
    setValue("");
  };

  const bodyText = (() => {
    if (phase === "listening") return "● CANAL VOCAL OUVERT — je vous écoute, Monsieur.";
    if (phase === "transcribing") return "Conversion de la parole en texte…";
    if (phase === "thinking") {
      return transcript ? `« ${transcript} »` : (statusText ?? "");
    }
    if (responseText) return responseText.slice(0, revealed);
    if (phase === "idle")
      return micHelp
        ? micHelp.hint
        : "Appuyez sur le micro et parlez — ou écrivez ci-dessous.";
    return "";
  })();

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Lien neural — conversation vocale avec J.A.R.V.I.S."
      className="dark neural-bg animate-neural-in fixed inset-0 z-[70] overflow-hidden"
    >
      {/* Canvas du réseau neuronal */}
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden="true" />

      {/* Fonds holographiques */}
      <div aria-hidden className="hud-grid animate-grid-drift pointer-events-none absolute inset-0 opacity-60" />
      <div aria-hidden className="hud-scanlines pointer-events-none absolute inset-0" />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_46%,color-mix(in_oklch,oklch(0.07_0.04_238)_92%,transparent)_100%)]"
      />

      {/* Coins HUD */}
      <div aria-hidden className="pointer-events-none absolute inset-3 sm:inset-5">
        <span className="hud-corner-tl" />
        <span className="hud-corner-tr" />
        <span className="hud-corner-bl" />
        <span className="hud-corner-br" />
      </div>

      {/* Barre supérieure */}
      <div className="absolute inset-x-0 top-0 flex items-start justify-between gap-3 p-4 pt-[max(1rem,env(safe-area-inset-top))] sm:p-6">
        <div className="animate-neural-rise">
          <p className="glow-text font-hud text-xs font-bold tracking-[0.3em] text-primary sm:text-sm">
            INTERFACE HOLOGRAPHIQUE
          </p>
          <p className="hud-label mt-0.5">J.A.R.V.I.S. CORE — CANAL VOCAL DIRECT</p>
          <span
            role="status"
            className={cn(
              "mt-2 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] font-semibold tracking-[0.14em]",
              meta.pillCls
            )}
          >
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
            {meta.label}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-full border border-primary/25 bg-primary/5 px-2.5 py-1 text-[10px] font-medium text-muted-foreground sm:inline-flex">
            <kbd className="rounded border border-primary/30 bg-primary/10 px-1 py-0.5 font-sans text-[10px] text-primary">
              ÉCHAP
            </kbd>
            quitter le lien
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer le lien neural"
            className="flex h-11 w-11 items-center justify-center rounded-full border border-primary/30 bg-primary/5 text-primary transition-all hover:bg-primary/15 hover:shadow-[0_0_18px_-4px] hover:shadow-primary/60"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Panneau inférieur */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center p-3 pb-[max(0.9rem,env(safe-area-inset-bottom))] sm:p-6">
        <div className="animate-neural-rise pointer-events-auto w-full max-w-2xl">
          <div className="hud-panel rounded-2xl p-3 sm:p-4">
            <p
              className={cn(
                "glow-text font-hud text-sm font-bold tracking-[0.22em] sm:text-base",
                phase === "listening" ? "text-destructive" : phase === "thinking" || phase === "transcribing" ? "text-gold" : "text-primary"
              )}
            >
              {meta.headline}
            </p>

            <div className="mt-2 min-h-20 max-h-44 overflow-y-auto pr-1">
              {phase === "thinking" && transcript ? (
                <p className="font-mono text-xs leading-relaxed text-muted-foreground sm:text-sm">
                  {bodyText}
                  {statusText && (
                    <span className="mt-1 block text-[11px] text-gold/90">
                      <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />
                      {statusText}
                    </span>
                  )}
                </p>
              ) : (
                <p
                  className={cn(
                    "text-sm leading-relaxed sm:text-[15px]",
                    phase === "idle" ? "text-muted-foreground" : "text-foreground/90"
                  )}
                >
                  {bodyText}
                  {phase === "speaking" && revealed < (responseText?.length ?? 0) && (
                    <span className="stream-cursor" />
                  )}
                </p>
              )}
            </div>

            {/* Aide micro bloqué : raison + solution (onglet dédié si aperçu) */}
            {micHelp && (
              <div
                role="alert"
                className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-gold/40 bg-gold/10 p-2.5 sm:gap-3 sm:p-3"
              >
                <span className="font-hud text-[11px] font-bold tracking-[0.18em] text-gold">
                  ⚠ {micHelp.title.toUpperCase()}
                </span>
                {micHelp.cta ? (
                  <button
                    type="button"
                    onClick={openStandalone}
                    className="inline-flex h-9 items-center gap-1.5 rounded-full border border-gold/60 bg-gold/20 px-3 text-xs font-semibold text-gold transition-all hover:bg-gold/30 hover:shadow-[0_0_16px_-4px] hover:shadow-gold/60"
                  >
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                    Ouvrir dans un onglet
                  </button>
                ) : null}
              </div>
            )}

            <div className="mt-3 flex items-center gap-2">
              {/* Micro / stop */}
              {micSupported && (
                <button
                  type="button"
                  onClick={phase === "thinking" || phase === "speaking" ? onStop : onMicToggle}
                  disabled={phase === "transcribing"}
                  aria-label={
                    phase === "listening"
                      ? "Arrêter l'enregistrement et envoyer"
                      : phase === "transcribing"
                        ? "Transcription en cours"
                        : phase === "thinking"
                          ? "Interrompre le traitement"
                          : phase === "speaking"
                            ? "Interrompre la voix"
                            : "Activer le micro"
                  }
                  className={cn(
                    "flex h-12 w-12 shrink-0 items-center justify-center rounded-full border transition-all",
                    phase === "listening"
                      ? "animate-pulse border-destructive/60 bg-destructive/15 text-destructive shadow-[0_0_22px_-4px] shadow-destructive/70"
                      : phase === "transcribing"
                        ? "border-primary/30 bg-primary/5 text-primary/60"
                        : phase === "thinking" || phase === "speaking"
                          ? "border-destructive/60 bg-destructive/15 text-destructive hover:bg-destructive/25"
                          : "border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 hover:shadow-[0_0_24px_-4px] hover:shadow-primary/70"
                  )}
                >
                  {phase === "transcribing" ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : phase === "listening" || phase === "thinking" || phase === "speaking" ? (
                    <Square className="h-4 w-4 fill-current" />
                  ) : (
                    <Mic className="h-5 w-5" />
                  )}
                </button>
              )}

              {/* Saisie clavier de secours */}
              <form
                className="flex min-w-0 flex-1 items-center gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  submit();
                }}
              >
                <label htmlFor="neural-input" className="sr-only">
                  Écrire à J.A.R.V.I.S.
                </label>
                <input
                  id="neural-input"
                  ref={inputRef}
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  disabled={busy}
                  placeholder={
                    micSupported ? "Ou écris à J.A.R.V.I.S…" : "Écris à J.A.R.V.I.S…"
                  }
                  className="h-11 min-w-0 flex-1 rounded-full border border-primary/25 bg-primary/5 px-4 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/60 focus:bg-primary/10 disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!value.trim() || busy}
                  aria-label="Envoyer le message"
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-all hover:brightness-110 disabled:opacity-40"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
            </div>
          </div>
          <p className="hud-label mt-2 text-center">
            {micError
              ? "Le canal vocal est bloqué — J.A.R.V.I.S. reste joignable au clavier."
              : micSupported
                ? "Le réseau réagit à votre voix et à celle de J.A.R.V.I.S."
                : "Micro indisponible — J.A.R.V.I.S. vous répond à voix haute"}
          </p>
        </div>
      </div>
    </div>
  );
}
