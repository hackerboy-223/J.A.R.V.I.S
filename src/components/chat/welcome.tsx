"use client";

import * as React from "react";
import {
  Activity,
  BookOpen,
  Calculator,
  Globe,
  Mic,
  Radar,
  Sparkles,
  Terminal,
} from "lucide-react";
import { ArcReactor } from "@/components/jarvis";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const SUGGESTIONS: Array<{
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  prompt: string;
  tool: string;
}> = [
  {
    icon: Activity,
    title: "Diagnostic de la machine",
    prompt:
      "Fais un diagnostic complet de la machine et rapporte-moi l'état des systèmes comme JARVIS le ferait.",
    tool: "system_status",
  },
  {
    icon: Globe,
    title: "Recherche globale",
    prompt:
      "Cherche sur le web les dernières actualités de cette semaine sur l'intelligence artificielle open source, puis fais-moi une synthèse structurée.",
    tool: "web_search",
  },
  {
    icon: Calculator,
    title: "Calcul de précision",
    prompt: "Calcule ((2^24 + 7 531 234) * 42 - 987) / 13,7 avec la calculatrice, puis explique le résultat.",
    tool: "calculator",
  },
  {
    icon: Terminal,
    title: "Exécuter du code",
    prompt:
      "Exécute du code JavaScript pour me dire combien il y a de nombres premiers inférieurs à 100 000, et montre-moi le code utilisé.",
    tool: "run_js",
  },
];

export function Welcome({
  onPick,
  onVoice,
  micSupported,
  embedded,
}: {
  onPick: (prompt: string) => void;
  onVoice?: () => void;
  micSupported?: boolean;
  /** la page est intégrée dans un panneau d'aperçu (iframe) — micro bloqué */
  embedded?: boolean;
}) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-center px-4 py-8 text-center sm:py-12">
      <ArcReactor size={168} state="idle" label="RÉACTEUR STABLE — PUISSANCE NOMINALE" />

      <h1 className="glow-text mt-6 text-3xl font-bold tracking-[0.3em] text-primary sm:text-4xl">
        J.A.R.V.I.S.
      </h1>
      <p className="hud-label mt-2">JUST A RATHER VERY INTELLIGENT SYSTEM</p>
      <p className="mt-4 max-w-md text-sm leading-relaxed text-muted-foreground sm:text-[15px]">
        Assistant IA vocal à votre service, <span className="text-gold">Monsieur</span> — je
        réfléchis, j&apos;agis sur la machine et je réponds, propulsé par les modèles{" "}
        <span className="font-medium text-primary">GLM de Z.ai</span> et{" "}
        <a
          href="https://huggingface.co"
          target="_blank"
          rel="noreferrer noopener"
          className="font-medium text-primary underline underline-offset-2"
        >
          Hugging Face
        </a>
        .
      </p>

      {onVoice && (
        <Button
          type="button"
          onClick={onVoice}
          className="mt-6 h-12 gap-2.5 rounded-full border border-primary/40 bg-primary/10 px-7 text-sm font-semibold tracking-wide text-primary shadow-[0_0_24px_-6px] shadow-primary/50 transition-all hover:bg-primary/20 hover:shadow-primary/40 disabled:opacity-50"
        >
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
          </span>
          <Mic className="h-4 w-4" />
          PARLER À J.A.R.V.I.S.
        </Button>
      )}
      {onVoice && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Lien neural plein écran — le réseau s'anime avec votre voix et celle de JARVIS
          {!micSupported && " · micro indisponible : le clavier reste utilisable"}
        </p>
      )}
      {onVoice && embedded && (
        <p className="mx-auto mt-2 flex max-w-md items-center gap-2 rounded-xl border border-gold/40 bg-gold/10 px-3 py-2 text-left text-[11px] leading-relaxed text-gold">
          <Mic className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            Aperçu intégré détecté : le navigateur y bloque le microphone. Pour parler à
            J.A.R.V.I.S., ouvre l&apos;application dans un onglet dédié — le clavier reste
            utilisable ici.
          </span>
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-center gap-1.5">
        {[
          { icon: Globe, label: "Recherche web" },
          { icon: Activity, label: "Contrôle machine" },
          { icon: Radar, label: "HUD animé" },
          { icon: Mic, label: "Voix" },
          { icon: Terminal, label: "Code" },
          { icon: BookOpen, label: "Lecture web" },
          { icon: Calculator, label: "Calculs" },
        ].map((b) => (
          <span
            key={b.label}
            className="inline-flex items-center gap-1 rounded-full border border-primary/25 bg-primary/5 px-2.5 py-1 text-[11px] font-medium text-primary/90"
          >
            <b.icon className="h-3 w-3" /> {b.label}
          </span>
        ))}
      </div>

      <div className="mt-8 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.title}
            type="button"
            onClick={() => onPick(s.prompt)}
            className={cn(
              "hud-panel group flex flex-col items-start gap-2 p-4 text-left transition-all",
              "hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-[0_0_28px_-10px] hover:shadow-primary/60"
            )}
          >
            <span className="flex items-center gap-2 text-sm font-semibold">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary">
                <s.icon className="h-3.5 w-3.5" />
              </span>
              {s.title}
            </span>
            <span className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
              {s.prompt}
            </span>
            <span className="mt-auto flex items-center gap-1 text-[11px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
              <Sparkles className="h-3 w-3" /> Exécuter
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
