"use client";

import * as React from "react";
import dynamicImport from "next/dynamic";
import {
  ArrowDown,
  ChevronDown,
  Loader2,
  Menu,
  Radio,
  Settings2,
  Sparkles,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
} from "@/components/ui/select";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { SidebarContent } from "@/components/chat/sidebar";
import { MessageItem } from "@/components/chat/message-item";
import { Welcome } from "@/components/chat/welcome";
import { Composer } from "@/components/chat/composer";
import { SettingsDialog } from "@/components/chat/settings-dialog";
import { ThemeToggle } from "@/components/chat/theme-toggle";
import { useHuggingAgent } from "@/hooks/use-hugging-agent";
import { useJarvisVoice } from "@/hooks/use-jarvis-voice";
import {
  ArcReactor,
  BootSequence,
  HudEffects,
  TelemetryPanel,
  VoiceWaveform,
  type NeuralPhase,
  type ReactorState,
} from "@/components/jarvis";
import { HF_MODELS, STARK_MODELS, isStarkModel, modelLabel, HUD_EVENT, type HudAction, type SystemStatus, type UpdateSettingsPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

// PERF : le lien neural (gros moteur canvas) est chargé à la demande,
// uniquement quand l'utilisateur veut parler à JARVIS.
const NeuralLink = dynamicImport(
  () => import("@/components/jarvis/NeuralLink").then((m) => ({ default: m.NeuralLink })),
  {
    ssr: false,
    loading: () => <div className="neural-bg fixed inset-0 z-[70]" aria-hidden="true" />,
  }
);

const BOOT_KEY = "jarvis-booted";

/**
 * PERF (voix) : extrait incrémentalement les phrases complètes d'un flux de
 * tokens, pour lancer la synthèse vocale dès la première phrase prête au
 * lieu d'attendre la fin de la génération.
 */
function extractSpeechSentences(
  buffer: string,
  minLen = 14,
  maxLen = 240
): { sentences: string[]; rest: string } {
  const sentences: string[] = [];
  let rest = buffer;
  for (;;) {
    if (!rest) break;
    // cherche une fin de phrase (. ! ? … ou saut de ligne) assez longue
    let cut = -1;
    const re = /[.!?…\n]/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(rest)) !== null) {
      const next = rest[m.index + 1] ?? "";
      if (/[\d]/.test(next)) continue; // décimale type « 3.14 » : pas une fin de phrase
      if (m.index + 1 >= minLen) {
        cut = m.index + 1;
        break;
      }
    }
    if (cut === -1) {
      // pas de ponctuation : coupe au dernier espace si le segment est trop long
      if (rest.length >= maxLen) {
        const lastSpace = rest.lastIndexOf(" ", maxLen);
        cut = lastSpace > minLen ? lastSpace : maxLen;
      } else {
        break;
      }
    }
    const piece = rest.slice(0, cut).trim();
    rest = rest.slice(cut);
    if (piece) sentences.push(piece);
  }
  return { sentences, rest };
}

function EngineBadge({
  hasToken,
  engine,
  model,
  onClick,
}: {
  hasToken: boolean;
  engine: "auto" | "hf" | "demo";
  model: string;
  onClick: () => void;
}) {
  const stark = isStarkModel(model);
  const usingHf = !stark && (engine === "hf" || (engine === "auto" && hasToken));
  return (
    <button
      type="button"
      onClick={onClick}
      title="Ouvrir les réglages"
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold tracking-wide transition-colors",
        usingHf
          ? "border-gold/40 bg-gold/10 text-gold hover:bg-gold/20"
          : "border-primary/40 bg-primary/10 text-primary hover:bg-primary/20"
      )}
    >
      {usingHf ? (
        <>
          <Sparkles className="h-3 w-3" /> HUGGING FACE
        </>
      ) : stark ? (
        <>
          <Zap className="h-3 w-3" /> STARK · {modelLabel(model).toUpperCase()}
        </>
      ) : (
        <>
          <Zap className="h-3 w-3" /> MOTEUR STARK · DÉMO
        </>
      )}
    </button>
  );
}

export default function Page() {
  const agent = useHuggingAgent();
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false);
  const [modelSelectOpen, setModelSelectOpen] = React.useState(false);
  const [booting, setBooting] = React.useState(true);

  // PERF : la séquence de boot (≈ 3,8 s) ne joue qu'une fois par session —
  // les rechargements suivants ouvrent l'interface instantanément.
  React.useEffect(() => {
    try {
      if (sessionStorage.getItem(BOOT_KEY) === "1") {
        setBooting(false);
        return;
      }
      sessionStorage.setItem(BOOT_KEY, "1");
    } catch {
      /* stockage indisponible : boot normal */
    }
  }, []);

  // Garde-fou : l'interface ne doit jamais rester prisonnière de l'écran de boot.
  React.useEffect(() => {
    if (!booting) return;
    const watchdog = window.setTimeout(() => setBooting(false), 6000);
    return () => window.clearTimeout(watchdog);
  }, [booting]);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const atBottomRef = React.useRef(true);
  const [showScrollDown, setShowScrollDown] = React.useState(false);

  // ---- Machine : statut système (télémétrie) ----
  const [systemStatus, setSystemStatus] = React.useState<SystemStatus | null>(null);
  React.useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch("/api/system-status");
        if (res.ok && alive) setSystemStatus((await res.json()) as SystemStatus);
      } catch {
        /* silencieux */
      }
    };
    void load();
    const t = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  // ---- Actions HUD déclenchées par l'agent (outil hud_action) ----
  const [hudAction, setHudAction] = React.useState<{ id: number; type: HudAction } | null>(null);
  React.useEffect(() => {
    const onHud = (e: Event) => {
      const detail = (e as CustomEvent<HudAction>).detail;
      if (detail) setHudAction({ id: Date.now(), type: detail });
    };
    window.addEventListener(HUD_EVENT, onHud);
    return () => window.removeEventListener(HUD_EVENT, onHud);
  }, []);

  // ---- Support micro ----
  const [micSupported, setMicSupported] = React.useState(false);
  // Page intégrée dans un panneau d'aperçu (iframe) : le micro y est
  // bloqué par le navigateur — on le signale AVANT que l'utilisateur clique.
  const [embedded, setEmbedded] = React.useState(false);
  React.useEffect(() => {
    setMicSupported(
      typeof navigator !== "undefined" &&
        !!navigator.mediaDevices?.getUserMedia &&
        typeof MediaRecorder !== "undefined"
    );
    try {
      setEmbedded(window.self !== window.top);
    } catch {
      setEmbedded(true); // accès cross-origin refusé → page intégrée
    }
  }, []);

  // ---- Orchestration vocale J.A.R.V.I.S. ----
  const [voiceMode, setVoiceMode] = React.useState(false);
  const voiceModeRef = React.useRef(voiceMode);
  React.useEffect(() => {
    voiceModeRef.current = voiceMode;
  }, [voiceMode]);

  // ---- Lien neural plein écran (animation réseau de neurones) ----
  const [neuralOpen, setNeuralOpen] = React.useState(false);
  const [spokenText, setSpokenText] = React.useState<string | null>(null);
  const [lastTranscript, setLastTranscript] = React.useState<string | null>(null);
  const suppressRelistenRef = React.useRef(false);
  const settingsRef = React.useRef(agent.settings);
  React.useEffect(() => {
    settingsRef.current = agent.settings;
  }, [agent.settings]);

  // Handler stable passé au hook vocal (via ref pour éviter les closures périmées)
  const runVoiceTurnRef = React.useRef<(text: string) => Promise<void>>(async () => {});
  const voice = useJarvisVoice({
    onTranscript: (text) => {
      void runVoiceTurnRef.current(text);
    },
  });

  const runTurn = React.useCallback(
    async (text: string, spoken: boolean) => {
      setLastTranscript(text);
      setSpokenText(null);
      const st = settingsRef.current;
      const wantVoice = voiceModeRef.current || !!st?.voiceEnabled;

      // PERF (voix) : la synthèse démarre dès la première phrase générée,
      // pendant que le modèle continue d'écrire — la file d'élocution
      // (beginStream/pushStream/endStream) enchaîne les phrases avec préfetch.
      if (wantVoice) {
        voice.beginStream({
          voice: st?.voiceName,
          speed: st?.voiceSpeed,
          engine: st?.voiceEngine ?? "browser",
          browserVoiceUri: st?.browserVoiceUri,
        });
      } else {
        voice.stopSpeaking();
      }
      let speechBuffer = "";
      const onText = wantVoice
        ? (delta: string) => {
            speechBuffer += delta;
            const { sentences, rest } = extractSpeechSentences(speechBuffer);
            speechBuffer = rest;
            if (sentences.length > 0) {
              for (const s of sentences) voice.pushStream(s);
              // texte affiché en direct dans le lien neural (typewriter)
              setSpokenText((prev) => `${prev ?? ""}${sentences.join(" ")} `);
            }
          }
        : undefined;

      const final = await agent.sendMessage(text, { voiceMode: spoken, onText });

      if (wantVoice) {
        const tail = speechBuffer.trim();
        speechBuffer = "";
        if (final && tail) voice.pushStream(tail);
        if (final) setSpokenText(final);
        // attend la fin d'élocution (immédiat si rien n'est en file)
        await voice.endStream();
      }

      if (suppressRelistenRef.current) {
        suppressRelistenRef.current = false;
        return;
      }
      if (voiceModeRef.current && voice.micState === "idle" && !voice.micError) {
        // pas de ré-écoute automatique si le micro vient d'échouer
        // (évite un toast d'erreur après chaque réponse dans un aperçu intégré)
        void voice.startListening();
      }
    },
    [agent, voice]
  );

  React.useEffect(() => {
    runVoiceTurnRef.current = async (text) => {
      await runTurn(text, true);
    };
  }, [runTurn]);

  const handleSend = React.useCallback(
    (text: string) => {
      void runTurn(text, false);
    },
    [runTurn]
  );

  const openNeural = React.useCallback(() => {
    setNeuralOpen(true);
    setVoiceMode(true);
    if (voice.micState === "idle" && !agent.streaming) {
      void voice.startListening();
    }
  }, [voice, agent.streaming]);

  const handleMicToggle = React.useCallback(() => {
    if (voice.micState === "listening") {
      void voice.stopListening();
    } else if (voice.micState === "idle" && !agent.streaming) {
      // Ouvre le lien neural plein écran pour parler à JARVIS
      openNeural();
    }
  }, [voice, agent.streaming, openNeural]);

  const handleVoiceModeChange = React.useCallback(
    (enabled: boolean) => {
      setVoiceMode(enabled);
      if (!enabled) {
        voice.cancelListening();
        voice.stopSpeaking();
      } else if (voice.micState === "idle" && !agent.streaming) {
        void voice.startListening();
      }
    },
    [voice, agent.streaming]
  );

  const handleStop = React.useCallback(() => {
    suppressRelistenRef.current = true;
    agent.stop();
    voice.stopSpeaking();
    voice.cancelListening();
  }, [agent, voice]);

  const closeNeural = React.useCallback(() => {
    setNeuralOpen(false);
    setVoiceMode(false);
    voice.cancelListening();
  }, [voice]);

  const handleNeuralMic = React.useCallback(() => {
    if (voice.micState === "listening") {
      void voice.stopListening();
    } else if (voice.micState === "idle" && !agent.streaming) {
      void voice.startListening();
    }
  }, [voice, agent.streaming]);

  const handleNeuralSend = React.useCallback(
    (text: string) => {
      void runTurn(text, true);
    },
    [runTurn]
  );

  const startVoiceFromWelcome = React.useCallback(() => {
    openNeural();
  }, [openNeural]);

  // ---- État visuel du réacteur / statut ----
  const reactorState: ReactorState = voice.speaking
    ? "speaking"
    : voice.micState === "listening"
      ? "listening"
      : agent.streaming
        ? "thinking"
        : "idle";

  const waveState: "idle" | "listening" | "speaking" = voice.speaking
    ? "speaking"
    : voice.micState === "listening"
      ? "listening"
      : agent.streaming
        ? "speaking"
        : "idle";

  const activeAnalyser =
    voice.micState === "listening" ? voice.micAnalyser : voice.speaking ? voice.speakAnalyser : null;

  const neuralPhase: NeuralPhase = voice.speaking
    ? "speaking"
    : voice.micState === "listening"
      ? "listening"
      : voice.micState === "transcribing"
        ? "transcribing"
        : agent.streaming
          ? "thinking"
          : "idle";

  const statusShort = voice.speaking
    ? "ÉLOCUTION"
    : voice.micState === "listening"
      ? "ÉCOUTE"
      : voice.micState === "transcribing"
        ? "TRANSCRIPTION"
        : agent.streaming
          ? "TRAITEMENT"
          : "EN LIGNE";

  const statusLong = voice.speaking
    ? "À VOTRE SERVICE, MONSIEUR"
    : voice.micState === "listening"
      ? "JE VOUS ÉCOUTE, MONSIEUR"
      : voice.micState === "transcribing"
        ? "ANALYSE DE LA VOIX…"
        : agent.streaming
          ? "ANALYSE MULTI-SYSTÈME EN COURS…"
          : "SYSTÈMES NOMINAUX — EN ATTENTE D’INSTRUCTIONS";

  const messages = agent.messages;
  const lastMessage = messages[messages.length - 1];
  const voiceStripVisible =
    voiceMode || voice.micState !== "idle" || voice.speaking || agent.streaming;

  // Auto-scroll (si l'utilisateur est déjà en bas)
  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el || !atBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, agent.statusText]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    atBottomRef.current = distance < 120;
    setShowScrollDown(distance > 240);
  };

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    atBottomRef.current = true;
  };

  const handleModelChange = async (modelId: string) => {
    if (!agent.settings) return;
    const payload: UpdateSettingsPayload = { model: modelId };
    if (modelId !== "__custom__") payload.customModel = null;
    await agent.saveSettings(payload);
  };

  const currentModel = agent.settings?.model ?? "glm-4.6";
  const modelIsKnown = isStarkModel(currentModel) || HF_MODELS.some((m) => m.id === currentModel);
  const currentModelLabel = modelLabel(currentModel);
  const usingHf =
    !isStarkModel(currentModel) &&
    ((agent.settings?.engine ?? "auto") === "hf" ||
      ((agent.settings?.engine ?? "auto") === "auto" && agent.settings?.hasToken));

  const sidebar = (
    <SidebarContent
      conversations={agent.conversations}
      currentId={agent.currentId}
      onNew={() => {
        agent.newConversation();
        setMobileNavOpen(false);
      }}
      onSelect={(id) => {
        void agent.selectConversation(id);
        setMobileNavOpen(false);
      }}
      onDelete={(id) => void agent.deleteConversation(id)}
      onRename={(id, title) => void agent.renameConversation(id, title)}
    />
  );

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden">
      {/* ---- Fonds holographiques ---- */}
      <div aria-hidden className="hud-grid pointer-events-none fixed inset-0" />
      <div aria-hidden className="hud-scanlines pointer-events-none fixed inset-0 z-[55]" />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[5] bg-[radial-gradient(ellipse_at_center,transparent_58%,color-mix(in_oklch,var(--background)_88%,transparent)_100%)]"
      />

      {/* ---- Séquence de démarrage + effets HUD ---- */}
      {booting && (
        <BootSequence
          onDone={() => setBooting(false)}
          modelLabel={
            isStarkModel(currentModel)
              ? `NOYAU : ${currentModelLabel.toUpperCase()} — MOTEUR STARK INTÉGRÉ`
              : usingHf
                ? `NOYAU : ${currentModelLabel.toUpperCase()} — VIA HUGGING FACE`
                : "MOTEUR STARK DE SECOURS — MODE DÉMO"
          }
        />
      )}
      <HudEffects action={hudAction} />

      <div className="relative z-10 flex min-h-0 flex-1">
        {/* ---- Sidebar conversations (desktop) ---- */}
        <aside className="hidden w-64 shrink-0 border-r border-primary/15 bg-sidebar/60 backdrop-blur md:flex md:flex-col">
          <div className="flex h-14 items-center gap-2.5 border-b border-primary/15 px-4">
            <ArcReactor size={26} state={reactorState} />
            <div className="leading-tight">
              <p className="glow-text text-sm font-bold tracking-[0.18em] text-primary">J.A.R.V.I.S.</p>
              <p className="hud-label">ASSISTANT EMBARQUÉ</p>
            </div>
          </div>
          {sidebar}
        </aside>

        {/* ---- Zone principale ---- */}
        <main className="flex min-w-0 flex-1 flex-col">
          {/* Header */}
          <header className="flex h-14 shrink-0 items-center gap-2 border-b border-primary/15 bg-background/70 px-3 backdrop-blur sm:px-4">
            <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 md:hidden"
                  aria-label="Ouvrir le menu"
                >
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-72 border-primary/20 p-0">
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <div className="flex h-14 items-center gap-2.5 border-b border-primary/15 px-4">
                  <ArcReactor size={26} state={reactorState} />
                  <div className="leading-tight">
                    <p className="glow-text text-sm font-bold tracking-[0.18em] text-primary">J.A.R.V.I.S.</p>
                    <p className="hud-label">ASSISTANT EMBARQUÉ</p>
                  </div>
                </div>
                {sidebar}
              </SheetContent>
            </Sheet>

            <div className="flex items-center gap-2 md:hidden">
              <ArcReactor size={22} state={reactorState} />
              <span className="glow-text text-sm font-bold tracking-[0.18em] text-primary">
                J.A.R.V.I.S.
              </span>
            </div>

            {/* Statut */}
            <div className="hidden items-center gap-2 md:flex">
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] font-semibold tracking-[0.14em]",
                  statusShort === "ÉCOUTE"
                    ? "border-destructive/50 bg-destructive/10 text-destructive"
                    : statusShort === "TRAITEMENT" || statusShort === "TRANSCRIPTION"
                      ? "border-gold/50 bg-gold/10 text-gold"
                      : "border-primary/40 bg-primary/10 text-primary"
                )}
                role="status"
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    statusShort === "EN LIGNE" ? "bg-primary animate-pulse" : "bg-current animate-pulse"
                  )}
                />
                {statusShort}
              </span>
              {(agent.activeEngine || agent.streaming) && (
                <span className="max-w-52 truncate text-xs text-muted-foreground">
                  {agent.activeEngine === "hf" ? "via Inference Providers" : isStarkModel(currentModel) ? `moteur Stark · ${currentModelLabel}` : "moteur Stark local"}
                </span>
              )}
            </div>

            <div className="ml-auto flex items-center gap-1.5">
              {/* Sélecteur de modèle */}
              <div className="flex items-center">
                <Select
                  value={modelIsKnown ? currentModel : "__custom__"}
                  onValueChange={(v) => void handleModelChange(v)}
                  open={modelSelectOpen}
                  onOpenChange={setModelSelectOpen}
                >
                  <SelectTrigger className="h-9 max-w-40 gap-1 border-primary/25 bg-primary/5 px-2.5 text-xs font-medium shadow-none hover:bg-primary/10 sm:max-w-52 sm:text-[13px]">
                    <span className="truncate">{currentModelLabel}</span>
                    <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-60" />
                  </SelectTrigger>
                  <SelectContent align="end" className="max-h-80">
                    <SelectGroup>
                      <SelectLabel className="text-primary">⚡ Moteur Stark — GLM</SelectLabel>
                      {STARK_MODELS.map((m) => (
                        <SelectItem key={m.id} value={m.id} className="py-2">
                          <span className="flex flex-col items-start">
                            <span className="text-[13px] font-medium">{m.label}</span>
                            <span className="text-[11px] text-muted-foreground">
                              {m.id} · {m.size}
                            </span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectGroup>
                    <SelectGroup>
                      <SelectLabel className="text-gold">🤗 Hugging Face (token)</SelectLabel>
                      {HF_MODELS.map((m) => (
                        <SelectItem key={m.id} value={m.id} className="py-2">
                          <span className="flex flex-col items-start">
                            <span className="text-[13px] font-medium">{m.label}</span>
                            <span className="text-[11px] text-muted-foreground">
                              {m.id} · {m.size}
                            </span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectGroup>
                    {!modelIsKnown && (
                      <SelectItem value="__custom__" className="py-2">
                        <span className="flex flex-col items-start">
                          <span className="text-[13px] font-medium">✏️ {currentModel}</span>
                          <span className="text-[11px] text-muted-foreground">modèle personnalisé</span>
                        </span>
                      </SelectItem>
                    )}
                    <SelectItem
                      value="glm-4.6"
                      className="hidden"
                      aria-hidden
                    >
                      placeholder
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 text-primary/80 hover:text-primary"
                aria-label="Réglages"
                onClick={() => setSettingsOpen(true)}
              >
                <Settings2 className="h-4 w-4" />
              </Button>
              <ThemeToggle />
            </div>
          </header>

          {/* Bandeau moteur */}
          {agent.settings && !usingHf && !isStarkModel(currentModel) && agent.settings.engine !== "demo" && (
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              className="flex w-full items-center justify-center gap-2 border-b border-gold/25 bg-gold/10 px-4 py-1.5 text-left text-xs text-gold transition-colors hover:bg-gold/20"
            >
              <Zap className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">
                Ce modèle Hugging Face exige un token — ou choisis un modèle <strong>GLM intégré</strong>, sans configuration, Monsieur.
              </span>
              <span className="shrink-0 font-semibold underline underline-offset-2">Configurer</span>
            </button>
          )}
          {agent.settings?.engine === "demo" && !isStarkModel(currentModel) && (
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              className="flex w-full items-center justify-center gap-2 border-b border-gold/25 bg-gold/10 px-4 py-1.5 text-left text-xs text-gold transition-colors hover:bg-gold/20"
            >
              <Zap className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">
                Moteur <strong>Stark</strong> forcé dans les réglages — clique pour brancher Hugging Face.
              </span>
            </button>
          )}

          {/* Messages */}
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="relative min-h-0 flex-1 overflow-y-auto"
            role="log"
            aria-live="polite"
          >
            {messages.length === 0 && !agent.loadingConversation ? (
              <Welcome
                onPick={handleSend}
                onVoice={startVoiceFromWelcome}
                micSupported={micSupported}
                embedded={embedded}
              />
            ) : (
              <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-3 py-6 sm:px-4">
                {agent.loadingConversation && (
                  <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" /> Chargement des archives…
                  </div>
                )}
                {messages.map((m) => (
                  <MessageItem key={m.id} message={m} />
                ))}
                {agent.streaming && agent.statusText && !lastMessage?.content && (
                  <div className="flex items-center gap-2 pl-1 text-xs text-muted-foreground">
                    <Sparkles className="h-3.5 w-3.5 animate-pulse text-primary" />
                    {agent.statusText}
                  </div>
                )}
                <div className="h-2" />
              </div>
            )}

            {showScrollDown && (
              <button
                type="button"
                onClick={scrollToBottom}
                aria-label="Descendre en bas"
                className="absolute bottom-4 left-1/2 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-primary/40 bg-card/90 text-primary shadow-[0_0_16px_-4px] shadow-primary/60 backdrop-blur transition-transform hover:scale-105"
              >
                <ArrowDown className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* ---- Bandeau vocal J.A.R.V.I.S. ---- */}
          {voiceStripVisible && (
            <div className="shrink-0 border-t border-primary/15 bg-primary/[0.04] px-3 py-2 sm:px-4">
              <div className="mx-auto flex w-full max-w-3xl items-center gap-3 sm:gap-4">
                <ArcReactor size={48} state={reactorState} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="hud-label truncate">{statusLong}</p>
                    {voiceMode && (
                      <span className="inline-flex shrink-0 items-center gap-1 text-[10px] font-semibold tracking-wider text-gold">
                        <Radio className="h-3 w-3" /> VOX
                      </span>
                    )}
                  </div>
                  <VoiceWaveform
                    analyser={activeAnalyser}
                    state={waveState}
                    className="h-10"
                    bars={40}
                  />
                </div>
              </div>
            </div>
          )}

          {/* ---- Footer / Composer — collé en bas ---- */}
          <footer className="mt-auto shrink-0 border-t border-primary/15 bg-background/80 backdrop-blur">
            <div className="mx-auto w-full max-w-3xl px-3 pb-2 pt-3 sm:px-4">
              <Composer
                onSend={handleSend}
                onStop={handleStop}
                busy={agent.streaming}
                micState={voice.micState}
                micSupported={micSupported}
                onMicToggle={handleMicToggle}
                speaking={voice.speaking}
                voiceMode={voiceMode}
                onVoiceModeChange={handleVoiceModeChange}
              />
              <div className="mt-1.5 flex items-center justify-between gap-2">
                <p className="text-[11px] leading-tight text-muted-foreground">
                  J.A.R.V.I.S. peut se tromper — vérifie les informations importantes.
                </p>
                <Badge
                  variant="outline"
                  className="hidden shrink-0 gap-1 border-primary/25 bg-primary/5 text-[10px] text-muted-foreground sm:inline-flex"
                >
                  <Sparkles className="h-3 w-3 text-primary" />
                  {HF_MODELS.some((m) => m.id === currentModel) ? currentModelLabel : currentModel}
                </Badge>
              </div>
            </div>
            <div className="h-[env(safe-area-inset-bottom)]" aria-hidden />
          </footer>
        </main>

        {/* ---- Rail télémétrie (desktop large) ---- */}
        <aside className="hidden w-[228px] shrink-0 border-l border-primary/15 bg-sidebar/40 p-3 backdrop-blur xl:block">
          <div className="mb-3 flex items-center justify-between px-1">
            <span className="hud-label">SYSTÈMES EMBARQUÉS</span>
            <EngineBadge
              hasToken={!!agent.settings?.hasToken}
              engine={agent.settings?.engine ?? "auto"}
              model={currentModel}
              onClick={() => setSettingsOpen(true)}
            />
          </div>
          <TelemetryPanel status={systemStatus} />
        </aside>
      </div>

      {/* Lien neural plein écran — module chargé à la demande (perf) */}
      {neuralOpen && (
        <NeuralLink
          open={neuralOpen}
          phase={neuralPhase}
          micState={voice.micState}
          micSupported={micSupported}
          micError={voice.micError}
          micAnalyser={voice.micAnalyser}
          speakAnalyser={voice.speakAnalyser}
          transcript={lastTranscript}
          responseText={spokenText}
          statusText={agent.statusText}
          streaming={agent.streaming}
          speaking={voice.speaking}
          onClose={closeNeural}
          onMicToggle={handleNeuralMic}
          onSendText={handleNeuralSend}
          onStop={handleStop}
        />
      )}

      {/* Réglages */}
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        settings={agent.settings}
        onSave={agent.saveSettings}
        onTest={agent.testConnection}
      />
    </div>
  );
}
