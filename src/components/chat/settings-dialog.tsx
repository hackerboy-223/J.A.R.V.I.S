"use client";

import * as React from "react";
import {
  CheckCircle2,
  Eye,
  EyeOff,
  Loader2,
  Plug,
  RotateCcw,
  TriangleAlert,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ALL_MODELS,
  DEFAULT_MODEL,
  HF_MODELS,
  STARK_MODELS,
  TTS_VOICES,
  isStarkModel,
  resolveModel,
  type VoiceEngine,
  type VoiceInfo,
} from "@/lib/types";
import type { EngineMode, PublicSettings, UpdateSettingsPayload } from "@/lib/types";
import { Mic, Volume2 } from "lucide-react";

const CUSTOM = "__custom__";

function VoiceSelectItem({ voice }: { voice: VoiceInfo }) {
  return (
    <SelectItem value={voice.name} className="flex flex-col items-start gap-0.5">
      <span className="text-sm font-medium">{voice.label}</span>
      <span className="text-xs text-muted-foreground">{voice.description}</span>
    </SelectItem>
  );
}

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  settings: PublicSettings | null;
  onSave: (payload: UpdateSettingsPayload) => Promise<void>;
  onTest: (token: string, model: string) => Promise<{ ok: boolean; message: string }>;
}

export function SettingsDialog({
  open,
  onOpenChange,
  settings,
  onSave,
  onTest,
}: SettingsDialogProps) {
  const [token, setToken] = React.useState("");
  const [showToken, setShowToken] = React.useState(false);
  const [model, setModel] = React.useState(DEFAULT_MODEL);
  const [customModel, setCustomModel] = React.useState("");
  const [engine, setEngine] = React.useState<EngineMode>("auto");
  const [temperature, setTemperature] = React.useState(0.7);
  const [maxSteps, setMaxSteps] = React.useState(6);
  const [systemPrompt, setSystemPrompt] = React.useState("");
  const [useCustomPrompt, setUseCustomPrompt] = React.useState(false);
  const [voiceEnabled, setVoiceEnabled] = React.useState(false);
  const [voiceEngine, setVoiceEngine] = React.useState<VoiceEngine>("browser");
  const [voiceName, setVoiceName] = React.useState("tongtong");
  const [browserVoiceUri, setBrowserVoiceUri] = React.useState<string>("");
  const [browserVoices, setBrowserVoices] = React.useState<SpeechSynthesisVoice[]>([]);
  const [voiceSpeed, setVoiceSpeed] = React.useState(1);
  const [voiceTesting, setVoiceTesting] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [testing, setTesting] = React.useState(false);
  const [testResult, setTestResult] = React.useState<{ ok: boolean; message: string } | null>(null);

  // Voix françaises natives du navigateur (chargées async)
  React.useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const read = () => {
      const fr = window.speechSynthesis
        .getVoices()
        .filter((v) => v.lang?.toLowerCase().startsWith("fr"));
      setBrowserVoices(fr);
    };
    read();
    window.speechSynthesis.addEventListener("voiceschanged", read);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", read);
  }, []);

  React.useEffect(() => {
    if (open && settings) {
      setToken("");
      setShowToken(false);
      const known = ALL_MODELS.some((m) => m.id === settings.model);
      setModel(known ? settings.model : CUSTOM);
      setCustomModel(known ? settings.customModel ?? "" : settings.model);
      setEngine(settings.engine);
      setTemperature(settings.temperature);
      setMaxSteps(settings.maxSteps);
      setSystemPrompt(settings.systemPrompt ?? "");
      setUseCustomPrompt(!!settings.systemPrompt);
      setVoiceEnabled(settings.voiceEnabled);
      setVoiceEngine(settings.voiceEngine);
      setVoiceName(settings.voiceName);
      setBrowserVoiceUri(settings.browserVoiceUri ?? "");
      setVoiceSpeed(settings.voiceSpeed);
      setTestResult(null);
    }
  }, [open, settings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: UpdateSettingsPayload = {
        model,
        customModel: model === CUSTOM ? customModel : null,
        engine,
        temperature,
        maxSteps,
        systemPrompt: useCustomPrompt && systemPrompt.trim() ? systemPrompt.trim() : null,
        voiceEnabled,
        voiceEngine,
        voiceName,
        browserVoiceUri: voiceEngine === "browser" && browserVoiceUri ? browserVoiceUri : null,
        voiceSpeed,
      };
      // N'envoyer le token que s'il a été modifié ; chaine vide => inchangé
      if (token.trim()) payload.hfToken = token.trim();
      await onSave(payload);
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await onTest(token.trim(), resolveModel(model, customModel));
      setTestResult(result);
    } finally {
      setTesting(false);
    }
  };

  const handleRemoveToken = async () => {
    setSaving(true);
    try {
      await onSave({ hfToken: null });
      setToken("");
      setTestResult(null);
    } finally {
      setSaving(false);
    }
  };

  const handleVoiceTest = async () => {
    setVoiceTesting(true);
    const PHRASE = "Bonjour Monsieur. Synthèse vocale opérationnelle. À votre service.";
    try {
      if (voiceEngine === "browser" && typeof window !== "undefined" && "speechSynthesis" in window) {
        // Voix natives du navigateur — instantané
        await new Promise<void>((resolve) => {
          const u = new SpeechSynthesisUtterance(PHRASE);
          const chosen = browserVoices.find((v) => v.voiceURI === browserVoiceUri) ?? browserVoices[0];
          if (chosen) {
            u.voice = chosen;
            u.lang = chosen.lang;
          } else {
            u.lang = "fr-FR";
          }
          u.rate = Math.min(Math.max(voiceSpeed, 0.5), 2);
          u.pitch = 0.95;
          u.onend = () => resolve();
          u.onerror = () => resolve();
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(u);
          setTimeout(resolve, 12000); // garde-fou
        });
      } else {
        // Moteur Stark (serveur)
        const res = await fetch("/api/voice/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: PHRASE,
            voice: voiceName,
            speed: voiceSpeed,
          }),
        });
        const data = (await res.json()) as { chunks?: string[]; error?: string };
        if (!res.ok || !data.chunks?.length) throw new Error(data.error ?? "Échec de la synthèse");
        const ctx = new AudioContext();
        for (const chunk of data.chunks) {
          const bin = atob(chunk);
          const bytes = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
          const buf = await ctx.decodeAudioData(bytes.buffer);
          const src = ctx.createBufferSource();
          src.buffer = buf;
          src.connect(ctx.destination);
          await new Promise<void>((resolve) => {
            src.onended = () => resolve();
            src.start();
          });
        }
        void ctx.close();
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : "Erreur de synthèse vocale";
      window.alert(`Test vocal échoué : ${message}`);
    } finally {
      setVoiceTesting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Réglages</DialogTitle>
          <DialogDescription>
            Configure le moteur Hugging Face, le modèle et le comportement de l&apos;agent.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-1">
          {/* Modèle */}
          <div className="space-y-2">
            <Label htmlFor="model">Modèle</Label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger id="model">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                <SelectGroup>
                  <SelectLabel className="text-primary">⚡ Moteur Stark intégré — GLM (sans token)</SelectLabel>
                  {STARK_MODELS.map((m) => (
                    <SelectItem key={m.id} value={m.id} className="flex flex-col items-start gap-0.5">
                      <span className="text-sm font-medium">{m.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {m.id} · {m.size}
                      </span>
                    </SelectItem>
                  ))}
                </SelectGroup>
                <SelectGroup>
                  <SelectLabel className="text-gold">🤗 Hugging Face — Inference Providers (token)</SelectLabel>
                  {HF_MODELS.map((m) => (
                    <SelectItem key={m.id} value={m.id} className="flex flex-col items-start gap-0.5">
                      <span className="text-sm font-medium">{m.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {m.id} · {m.size}
                      </span>
                    </SelectItem>
                  ))}
                </SelectGroup>
                <SelectItem value={CUSTOM}>
                  <span className="text-sm font-medium">✏️ Personnalisé…</span>
                </SelectItem>
              </SelectContent>
            </Select>
            {model === CUSTOM && (
              <Input
                placeholder="org/nom-du-modele HF (ex : zai-org/GLM-4.6) ou glm-4.5-flash (intégré)"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                className="font-mono text-xs"
              />
            )}
            <p className="text-xs text-muted-foreground">
              Les modèles GLM du moteur Stark fonctionnent immédiatement, sans token. Les modèles
              Hugging Face nécessitent un token (ci-dessous).
            </p>
          </div>

          {/* Moteur HF */}
          <div className="space-y-2">
            <Label htmlFor="engine">Moteur Hugging Face</Label>
            <Select value={engine} onValueChange={(v) => setEngine(v as EngineMode)}>
              <SelectTrigger id="engine">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">
                  Auto — Hugging Face si un token est défini, sinon moteur Stark
                </SelectItem>
                <SelectItem value="hf">Forcer Hugging Face (token requis)</SelectItem>
                <SelectItem value="demo">Forcer le moteur Stark intégré</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Ne s'applique qu'aux modèles Hugging Face — un modèle GLM (intégré) utilise
              toujours le moteur Stark, sans token.
            </p>
          </div>

          {/* Token */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="hf-token">Token Hugging Face</Label>
              {settings?.hasToken && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleRemoveToken}
                  className="h-7 px-2 text-xs text-destructive hover:text-destructive"
                >
                  <RotateCcw className="mr-1 h-3 w-3" /> Supprimer le token enregistré
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  id="hf-token"
                  type={showToken ? "text" : "password"}
                  placeholder={
                    settings?.hasToken
                      ? `Enregistré (${settings.tokenPreview}) — laisser vide pour conserver`
                      : "hf_xxxxxxxxxxxxxxxxxxxx"
                  }
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  autoComplete="off"
                  className="pr-9 font-mono text-xs"
                />
                <button
                  type="button"
                  onClick={() => setShowToken((s) => !s)}
                  aria-label={showToken ? "Masquer le token" : "Afficher le token"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={handleTest}
                disabled={
                  testing ||
                  (!isStarkModel(resolveModel(model, customModel)) && !token.trim() && !settings?.hasToken)
                }
              >
                {testing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plug className="h-4 w-4" />
                )}
                Tester
              </Button>
            </div>
            {testResult && (
              <p
                className={`flex items-start gap-1.5 rounded-lg border px-2.5 py-2 text-xs leading-relaxed ${
                  testResult.ok
                    ? "border-primary/30 bg-primary/10 text-foreground"
                    : "border-destructive/30 bg-destructive/10 text-destructive"
                }`}
              >
                {testResult.ok ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                ) : (
                  <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                )}
                {testResult.message}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              Crée un token gratuit sur{" "}
              <a
                href="https://huggingface.co/settings/tokens"
                target="_blank"
                rel="noreferrer noopener"
                className="text-primary underline underline-offset-2"
              >
                huggingface.co/settings/tokens
              </a>{" "}
              (droit « Make calls to Inference Providers »). Il est stocké côté serveur uniquement.
            </p>
          </div>

          {/* Modèle — l'ancien bloc modèle a été déplacé en tête */}

          {/* Température */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <Label>Température</Label>
              <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                {temperature.toFixed(1)}
              </span>
            </div>
            <Slider
              value={[temperature]}
              onValueChange={([v]) => setTemperature(v)}
              min={0}
              max={1.5}
              step={0.1}
            />
            <p className="text-xs text-muted-foreground">
              Basse = réponses déterministes · Haute = plus créatif
            </p>
          </div>

          {/* Étapes max */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <Label>Étapes d&apos;agent maximum</Label>
              <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                {maxSteps}
              </span>
            </div>
            <Slider
              value={[maxSteps]}
              onValueChange={([v]) => setMaxSteps(Math.round(v))}
              min={1}
              max={10}
              step={1}
            />
            <p className="text-xs text-muted-foreground">
              Nombre maximal d&apos;appels d&apos;outils enchaînés avant la réponse finale.
            </p>
          </div>

          {/* Prompt système */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="system-prompt">Prompt système personnalisé</Label>
              <Switch checked={useCustomPrompt} onCheckedChange={setUseCustomPrompt} />
            </div>
            {useCustomPrompt && (
              <Textarea
                id="system-prompt"
                placeholder="Ex : Tu es un assistant expert en data science. Réponds de façon concise…"
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="min-h-24 text-sm"
              />
            )}
          </div>

          {/* Voix J.A.R.V.I.S. */}
          <div className="space-y-3 rounded-xl border border-primary/25 bg-primary/5 p-3.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="voice-enabled" className="flex items-center gap-1.5">
                <Mic className="h-3.5 w-3.5 text-primary" /> Voix J.A.R.V.I.S.
              </Label>
              <Switch id="voice-enabled" checked={voiceEnabled} onCheckedChange={setVoiceEnabled} />
            </div>
            <p className="text-xs text-muted-foreground">
              Quand la voix est activée, les réponses de l&apos;agent sont prononcées à voix haute
              (mode clavier inclus).
            </p>

            {/* Moteur vocal */}
            <div className="space-y-2">
              <Label>Moteur de la voix</Label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setVoiceEngine("browser")}
                  className={`rounded-lg border p-2.5 text-left transition-colors ${
                    voiceEngine === "browser"
                      ? "border-primary/60 bg-primary/15"
                      : "border-border hover:bg-muted/60"
                  }`}
                >
                  <span className="block text-sm font-semibold">🇫🇷 Voix française native</span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                    Voix du navigateur — accent français parfait, instantané, hors ligne.
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setVoiceEngine("stark")}
                  className={`rounded-lg border p-2.5 text-left transition-colors ${
                    voiceEngine === "stark"
                      ? "border-primary/60 bg-primary/15"
                      : "border-border hover:bg-muted/60"
                  }`}
                >
                  <span className="block text-sm font-semibold">🎙️ Moteur Stark</span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                    Synthèse serveur — voix JARVIS reconnaissable, streaming par phrases.
                  </span>
                </button>
              </div>
            </div>

            {voiceEngine === "browser" ? (
              <div className="space-y-2">
                <Label htmlFor="browser-voice">Voix française du navigateur</Label>
                {browserVoices.length > 0 ? (
                  <Select value={browserVoiceUri || browserVoices[0]?.voiceURI} onValueChange={setBrowserVoiceUri}>
                    <SelectTrigger id="browser-voice" className="text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="max-h-60">
                      {browserVoices.map((v) => (
                        <SelectItem key={v.voiceURI} value={v.voiceURI}>
                          <span className="text-sm font-medium">{v.name}</span>
                          <span className="ml-2 text-xs text-muted-foreground">{v.lang}</span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="rounded-lg border border-gold/30 bg-gold/10 px-2.5 py-2 text-xs text-gold">
                    Aucune voix française détectée dans ce navigateur — JARVIS utilisera
                    automatiquement le moteur Stark (serveur).
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="voice-name">Voix de synthèse Stark</Label>
                <Select value={voiceName} onValueChange={setVoiceName}>
                  <SelectTrigger id="voice-name" className="text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="max-h-60">
                    <SelectGroup>
                      <SelectLabel>Recommandées en français</SelectLabel>
                      {TTS_VOICES.filter((v) => v.recommended).map((v) => (
                        <VoiceSelectItem key={v.name} voice={v} />
                      ))}
                    </SelectGroup>
                    <SelectGroup>
                      <SelectLabel>Autres voix</SelectLabel>
                      {TTS_VOICES.filter((v) => !v.recommended).map((v) => (
                        <VoiceSelectItem key={v.name} voice={v} />
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Débit de la voix</Label>
                <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                  ×{voiceSpeed.toFixed(1)}
                </span>
              </div>
              <Slider
                value={[voiceSpeed]}
                onValueChange={([v]) => setVoiceSpeed(Math.round(v * 10) / 10)}
                min={0.5}
                max={2}
                step={0.1}
              />
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-full"
              onClick={handleVoiceTest}
              disabled={voiceTesting}
            >
              {voiceTesting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Volume2 className="mr-2 h-4 w-4" />
              )}
              Tester la voix
            </Button>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
