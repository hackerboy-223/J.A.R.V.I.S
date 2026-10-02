"use client";

import * as React from "react";
import {
  Activity,
  Calculator,
  Cpu,
  Globe,
  Mic,
  Radar,
  ScanLine,
  ShieldCheck,
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
    title: "Rapport de situation",
    prompt:
      "JARVIS, donne-moi un rapport de situation : diagnostic de la machine, état des ressources et capacités actuellement disponibles. Sois bref et opérationnel.",
    tool: "system_status",
  },
  {
    icon: Globe,
    title: "Scan d'information",
    prompt:
      "JARVIS, lance une recherche web sur les développements récents les plus importants en intelligence artificielle et synthétise uniquement ce qui mérite mon attention.",
    tool: "web_search",
  },
  {
    icon: Cpu,
    title: "Mode ingénierie",
    prompt:
      "JARVIS, passe en mode ingénierie. Aide-moi à analyser un problème technique comme un système embarqué : hypothèses, diagnostic, solution et vérification.",
    tool: "engineering",
  },
  {
    icon: Calculator,
    title: "Analyse de précision",
    prompt:
      "JARVIS, effectue une analyse de précision : calcule ((2^24 + 7 531 234) * 42 - 987) / 13,7, vérifie le résultat et donne-moi la conclusion.",
    tool: "calculator",
  },
];

const SYSTEM_BADGES = [
  { icon: Cpu, label: "NOYAU", value: "EN LIGNE" },
  { icon: Mic, label: "CANAL VOCAL", value: "PRÊT" },
  { icon: Radar, label: "TÉLÉMÉTRIE", value: "ACTIVE" },
  { icon: ShieldCheck, label: "INTÉGRITÉ", value: "NOMINALE" },
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
  embedded?: boolean;
}) {
  return (
    <div className="jarvis-command-stage mx-auto flex w-full max-w-4xl flex-col items-center px-4 py-7 text-center sm:py-10">
      <div className="mb-5 grid w-full max-w-3xl grid-cols-2 gap-2 sm:grid-cols-4">
        {SYSTEM_BADGES.map((item) => (
          <div
            key={item.label}
            className="hud-panel flex items-center gap-2 px-2.5 py-2 text-left"
          >
            <item.icon className="h-3.5 w-3.5 shrink-0 text-primary" />
            <div className="min-w-0">
              <p className="hud-label truncate">{item.label}</p>
              <p className="font-mono text-[10px] font-semibold tracking-[0.14em] text-primary">
                {item.value}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="relative flex items-center justify-center">
        <div aria-hidden className="hud-reticle-ring absolute h-56 w-56 rounded-full sm:h-64 sm:w-64" />
        <div aria-hidden className="absolute h-48 w-48 rounded-full border border-primary/10 sm:h-56 sm:w-56" />
        <ArcReactor size={176} state="idle" label="NOYAU STABLE — SYSTÈMES NOMINAUX" />
      </div>

      <p className="hud-label mt-6 text-gold/90">PERSONAL COMMAND INTELLIGENCE</p>
      <h1 className="glow-text mt-2 text-3xl font-bold tracking-[0.3em] text-primary sm:text-5xl">
        J.A.R.V.I.S.
      </h1>
      <p className="hud-label mt-2">JUST A RATHER VERY INTELLIGENT SYSTEM</p>

      <p className="mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground sm:text-[15px]">
        Interface d&apos;assistance embarquée à votre service,{" "}
        <span className="text-gold">Monsieur</span>. Analyse, diagnostic, recherche,
        ingénierie et contrôle de l&apos;interface sont coordonnés depuis ce centre de commande.
      </p>

      <div className="mt-5 flex flex-wrap items-center justify-center gap-1.5">
        {[
          { icon: ScanLine, label: "Analyse" },
          { icon: Activity, label: "Diagnostic" },
          { icon: Globe, label: "Renseignement web" },
          { icon: Terminal, label: "Ingénierie" },
          { icon: Calculator, label: "Calcul" },
          { icon: Mic, label: "Commande vocale" },
        ].map((b) => (
          <span
            key={b.label}
            className="inline-flex items-center gap-1.5 rounded-sm border border-primary/25 bg-primary/[0.06] px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-primary/90"
          >
            <b.icon className="h-3 w-3" /> {b.label}
          </span>
        ))}
      </div>

      {onVoice && (
        <Button
          type="button"
          onClick={onVoice}
          className="mt-6 h-12 gap-2.5 rounded-sm border border-primary/50 bg-primary/10 px-7 font-mono text-xs font-semibold tracking-[0.18em] text-primary shadow-[0_0_28px_-7px] shadow-primary/60 transition-all hover:bg-primary/20 hover:shadow-primary/50 disabled:opacity-50"
        >
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
          </span>
          <Mic className="h-4 w-4" />
          OUVRIR LE CANAL VOCAL
        </Button>
      )}

      {onVoice && (
        <p className="mt-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          Interface holographique plein écran · réponse vocale synchronisée
          {!micSupported && " · microphone indisponible : clavier actif"}
        </p>
      )}

      {onVoice && embedded && (
        <p className="mx-auto mt-3 flex max-w-lg items-center gap-2 border border-gold/40 bg-gold/10 px-3 py-2 text-left text-[11px] leading-relaxed text-gold">
          <Mic className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            Canal vocal bloqué dans l&apos;aperçu intégré. Ouvrez l&apos;application dans un
            onglet dédié pour autoriser le microphone ; le terminal texte reste opérationnel.
          </span>
        </p>
      )}

      <div className="mt-8 flex w-full items-center gap-3">
        <div className="h-px flex-1 bg-gradient-to-r from-transparent to-primary/30" />
        <span className="hud-label">PROTOCOLES RAPIDES</span>
        <div className="h-px flex-1 bg-gradient-to-l from-transparent to-primary/30" />
      </div>

      <div className="mt-4 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map((s, index) => (
          <button
            key={s.title}
            type="button"
            onClick={() => onPick(s.prompt)}
            className={cn(
              "hud-panel group relative flex min-h-32 flex-col items-start gap-2 overflow-hidden p-4 text-left transition-all",
              "hover:-translate-y-0.5 hover:border-primary/55 hover:shadow-[0_0_30px_-10px] hover:shadow-primary/60"
            )}
          >
            <span className="absolute right-3 top-2 font-mono text-[9px] tracking-[0.18em] text-primary/35">
              P-{String(index + 1).padStart(2, "0")}
            </span>
            <span className="flex items-center gap-2 text-sm font-semibold">
              <span className="flex h-8 w-8 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-primary">
                <s.icon className="h-4 w-4" />
              </span>
              {s.title}
            </span>
            <span className="line-clamp-3 text-xs leading-relaxed text-muted-foreground">
              {s.prompt}
            </span>
            <span className="mt-auto flex items-center gap-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-primary opacity-60 transition-opacity group-hover:opacity-100">
              <Sparkles className="h-3 w-3" /> Initialiser
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
