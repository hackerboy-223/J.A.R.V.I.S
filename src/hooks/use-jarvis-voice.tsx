"use client";

import * as React from "react";
import { toast } from "@/hooks/use-toast";
import { ToastAction } from "@/components/ui/toast";

// ============================================================
// Agent vocal J.A.R.V.I.S.
//  - Écoute : getUserMedia + MediaRecorder + AnalyserNode (visualisation)
//  - Transcription : WAV 16 kHz mono → POST /api/voice/asr
//  - Voix : file d'élocution en STREAMING — chaque phrase est synthétisée
//    et lue dès qu'elle est prête (préfetch de la suivante pendant la
//    lecture), ce qui divise la latence perçue par le nombre de phrases.
//  - Deux moteurs d'élocution : "browser" (voix natives françaises du
//    navigateur, instantanées) ou "stark" (TTS serveur, accent JARVIS).
//    Repli automatique sur le serveur si aucune voix navigateur.
// ============================================================

export type MicState = "idle" | "listening" | "transcribing";
export type VoicePhase = "idle" | "listening" | "transcribing" | "speaking";
export type SpeechEngine = "stark" | "browser";

/** Raison exacte pour laquelle le micro est indisponible (diagnostic vocal). */
export type MicFailure =
  | "iframe" // page intégrée (panneau d'aperçu) : le navigateur interdit le micro
  | "denied" // permission refusée au niveau du site
  | "no-device" // aucun micro détecté
  | "busy" // micro occupé par une autre application
  | "insecure" // contexte non sécurisé (HTTP)
  | "unknown";

/** Ouvre l'app dans un onglet dédié — seul contexte où le micro est autorisé
 *  quand la page est intégrée dans un panneau d'aperçu (iframe). */
export function openStandalone(): void {
  if (typeof window === "undefined") return;
  try {
    window.open(window.location.href, "_blank", "noopener,noreferrer");
  } catch {
    /* ignore */
  }
}

/** Classifie précisément une erreur getUserMedia pour guider l'utilisateur. */
function classifyMicError(e: unknown): MicFailure {
  if (typeof window !== "undefined" && !window.isSecureContext) return "insecure";
  const name = e instanceof DOMException ? e.name : e instanceof Error ? e.name : "";
  const inIframe =
    typeof window !== "undefined" &&
    (() => {
      try {
        return window.self !== window.top;
      } catch {
        return true; // accès cross-origin bloqué → très probablement intégrée
      }
    })();
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
    case "PermissionDeniedError":
      return inIframe ? "iframe" : "denied";
    case "NotFoundError":
    case "OverconstrainedError":
    case "NotSupportedError":
      return "no-device";
    case "NotReadableError":
    case "AbortError":
      return "busy";
    default:
      return "unknown";
  }
}

interface UseJarvisVoiceOptions {
  onTranscript: (text: string) => void;
}

export interface SpeechStreamOptions {
  voice?: string;
  speed?: number;
  engine?: SpeechEngine;
  browserVoiceUri?: string | null;
}

/** Encode un AudioBuffer rendu en Blob WAV (PCM 16 bits) */
function encodeWav(buffer: AudioBuffer): Blob {
  const numChannels = buffer.numberOfChannels;
  const sampleRate = buffer.sampleRate;
  const bytesPerSample = 2;
  const dataSize = buffer.length * numChannels * bytesPerSample;
  const headerSize = 44;
  const arrayBuffer = new ArrayBuffer(headerSize + dataSize);
  const view = new DataView(arrayBuffer);

  const writeString = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // taille fmt
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * numChannels * bytesPerSample, true);
  view.setUint16(32, numChannels * bytesPerSample, true);
  view.setUint16(34, 16, true); // bits
  writeString(36, "data");
  view.setUint32(40, dataSize, true);

  const channels: Float32Array[] = [];
  for (let c = 0; c < numChannels; c++) channels.push(buffer.getChannelData(c));

  let offset = headerSize;
  for (let i = 0; i < buffer.length; i++) {
    for (let c = 0; c < numChannels; c++) {
      let sample = channels[c][i];
      sample = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }
  }
  return new Blob([arrayBuffer], { type: "audio/wav" });
}

/** Ré-échantillonne un AudioBuffer en 16 kHz mono via OfflineAudioContext */
async function resampleTo16k(buffer: AudioBuffer): Promise<AudioBuffer> {
  const targetRate = 16000;
  const length = Math.max(1, Math.ceil((buffer.duration * targetRate) | 0) + 1);
  const offline = new OfflineAudioContext(1, length, targetRate);
  const src = offline.createBufferSource();
  src.buffer = buffer;
  src.connect(offline.destination);
  src.start(0);
  return offline.startRendering();
}

function base64ToUint8(base64: string): Uint8Array<ArrayBuffer> {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export function useJarvisVoice({ onTranscript }: UseJarvisVoiceOptions) {
  const [micState, setMicState] = React.useState<MicState>("idle");
  const [speaking, setSpeaking] = React.useState(false);
  const [micAnalyser, setMicAnalyser] = React.useState<AnalyserNode | null>(null);
  const [speakAnalyser, setSpeakAnalyser] = React.useState<AnalyserNode | null>(null);
  const [micError, setMicError] = React.useState<MicFailure | null>(null);

  const streamRef = React.useRef<MediaStream | null>(null);
  const recorderRef = React.useRef<MediaRecorder | null>(null);
  const chunksRef = React.useRef<Blob[]>([]);
  const audioCtxRef = React.useRef<AudioContext | null>(null);
  const rafRef = React.useRef<number | null>(null);
  const speakingRef = React.useRef(false);
  const currentSourceRef = React.useRef<AudioBufferSourceNode | null>(null);
  const cancelledListenRef = React.useRef(false);

  // ---- File d'élocution en streaming (perf : premier son ASAP) ----
  // levelRef (et non state) : évite 60 re-renders/s de toute la page pendant l'écoute
  const levelRef = React.useRef(0);
  const queueRef = React.useRef<string[]>([]);
  const drainingRef = React.useRef(false);
  const speakGenRef = React.useRef(0); // incrémenté à chaque stop → invalide les lectures en cours
  const drainDoneRef = React.useRef<(() => void) | null>(null);
  const ttsAbortRef = React.useRef<AbortController | null>(null);
  const prefetchRef = React.useRef<{
    text: string;
    promise: Promise<string[]>;
    ctrl: AbortController;
  } | null>(null);
  const streamOptsRef = React.useRef<SpeechStreamOptions>({});

  // ---- Voix natives du navigateur (Web Speech API) ----
  const voicesReadyRef = React.useRef<Promise<void> | null>(null);

  /** Attend le chargement des voix du navigateur (une fois, ≤ 800 ms). */
  const ensureVoicesReady = React.useCallback((): Promise<void> => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      return Promise.resolve();
    }
    if (!voicesReadyRef.current) {
      voicesReadyRef.current = new Promise<void>((resolve) => {
        const synth = window.speechSynthesis;
        if (synth.getVoices().length > 0) return resolve();
        let done = false;
        const finish = () => {
          if (!done) {
            done = true;
            resolve();
          }
        };
        synth.addEventListener("voiceschanged", finish, { once: true });
        setTimeout(finish, 800);
      });
    }
    return voicesReadyRef.current;
  }, []);

  /** Meilleure voix française du navigateur (enregistée > Google > locales). */
  const pickBrowserVoice = React.useCallback((): SpeechSynthesisVoice | null => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) return null;
    const wanted = streamOptsRef.current.browserVoiceUri;
    if (wanted) {
      const saved = voices.find((v) => v.voiceURI === wanted);
      if (saved) return saved;
    }
    const fr = voices.filter((v) => v.lang?.toLowerCase().startsWith("fr"));
    if (!fr.length) return null;
    const score = (v: SpeechSynthesisVoice) =>
      v.name.includes("Google") ? 4 : /am[eé]lie|audrey|thomas|denise|marie|henri|pauline/i.test(v.name) ? 3 : v.lang === "fr-FR" ? 2 : 1;
    return fr.slice().sort((a, b) => score(b) - score(a))[0] ?? null;
  }, []);

  const getCtx = (): AudioContext => {
    if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
      audioCtxRef.current = new AudioContext();
    }
    return audioCtxRef.current;
  };

  // ---- Mesure du niveau micro (pour l'anim du réacteur) ----
  // Stocké dans une ref : la visualisation lit l'AnalyserNode directement
  // via le canvas (VoiceWaveform), aucun re-render React n'est nécessaire.
  const startLevelMeter = (analyser: AnalyserNode) => {
    const data = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteFrequencyData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += data[i];
      levelRef.current = Math.min(1, sum / data.length / 90);
      rafRef.current = requestAnimationFrame(tick);
    };
    tick();
  };

  const stopLevelMeter = () => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    levelRef.current = 0;
  };

  // ---- Écoute ----
  const startListening = React.useCallback(async (): Promise<boolean> => {
    if (micState !== "idle") return false;
    cancelledListenRef.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const ctx = getCtx();
      if (ctx.state === "suspended") await ctx.resume();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.75;
      source.connect(analyser); // pas de destination → aucun écho
      setMicAnalyser(analyser);
      startLevelMeter(analyser);

      const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const mimeType =
        typeof MediaRecorder !== "undefined"
          ? mimeCandidates.find((m) => MediaRecorder.isTypeSupported(m))
          : undefined;

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorderRef.current = recorder;
      recorder.start(250);
      setMicState("listening");
      setMicError(null);
      return true;
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      setMicAnalyser(null);
      stopLevelMeter();

      // Diagnostic précis + action concrète (le message brut du navigateur
      // ne dit jamais à l'utilisateur COMMENT débloquer le micro)
      const failure = classifyMicError(e);
      setMicError(failure);
      switch (failure) {
        case "iframe":
          toast({
            title: "Micro bloqué par le panneau d'aperçu",
            description:
              "Le navigateur interdit le micro dans une page intégrée. Ouvre J.A.R.V.I.S. dans un onglet dédié — le bouton ci-dessous le fait pour toi.",
            variant: "destructive",
            action: (
              <ToastAction altText="Ouvrir J.A.R.V.I.S. dans un onglet dédié" onClick={openStandalone}>
                Ouvrir dans un onglet
              </ToastAction>
            ),
          });
          break;
        case "denied":
          toast({
            title: "Micro refusé",
            description:
              "Clique sur le cadenas 🔒 dans la barre d'adresse → Microphone → Autoriser, puis recharge la page.",
            variant: "destructive",
          });
          break;
        case "no-device":
          toast({
            title: "Aucun micro détecté",
            description: "Branche ou active un microphone — ou écris à J.A.R.V.I.S. au clavier.",
            variant: "destructive",
          });
          break;
        case "busy":
          toast({
            title: "Micro occupé",
            description: "Le micro est utilisé par une autre application. Ferme-la puis réessaie.",
            variant: "destructive",
          });
          break;
        case "insecure":
          toast({
            title: "Connexion non sécurisée",
            description: "L'accès au microphone exige une page HTTPS.",
            variant: "destructive",
          });
          break;
        default:
          toast({ title: "Micro indisponible", description: message, variant: "destructive" });
      }
      setMicState("idle");
      return false;
    }
  }, [micState]);

  const cleanupMic = React.useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    levelRef.current = 0;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    recorderRef.current = null;
    setMicAnalyser(null);
  }, []);

  /** Stop et transcription. Si cancelled → abandon silencieux. */
  const stopListening = React.useCallback(async (): Promise<void> => {
    const recorder = recorderRef.current;
    if (!recorder || micState !== "listening") {
      if (micState === "idle") cleanupMic();
      return;
    }

    const stopped = new Promise<void>((resolve) => {
      if (recorder.state === "inactive") return resolve();
      recorder.onstop = () => resolve();
      try {
        recorder.stop();
      } catch {
        resolve();
      }
    });
    await stopped;
    cleanupMic();

    if (cancelledListenRef.current) {
      cancelledListenRef.current = false;
      setMicState("idle");
      return;
    }

    setMicState("transcribing");
    try {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
      chunksRef.current = [];
      if (blob.size < 1200) {
        toast({ title: "Enregistrement trop court", description: "Maintiens le micro et parle plus longtemps." });
        return;
      }

      const arrayBuffer = await blob.arrayBuffer();
      const ctx = getCtx();
      const decoded = await ctx.decodeAudioData(arrayBuffer.slice(0));
      const mono16 = await resampleTo16k(decoded);
      const wav = encodeWav(mono16);

      const b64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const result = String(reader.result ?? "");
          resolve(result.includes(",") ? result.split(",")[1] : result);
        };
        reader.onerror = () => reject(new Error("Lecture de l'enregistrement impossible"));
        reader.readAsDataURL(wav);
      });

      const res = await fetch("/api/voice/asr", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audio: b64 }),
      });
      const data = (await res.json()) as { text?: string; error?: string };
      if (!res.ok) throw new Error(data.error ?? "Transcription impossible");
      const text = (data.text ?? "").trim();
      if (!text) {
        toast({ title: "Aucune parole détectée", description: "Réessaie en parlant distinctement." });
        return;
      }
      onTranscript(text);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Erreur de transcription";
      toast({ title: "Transcription impossible", description: message, variant: "destructive" });
    } finally {
      setMicState("idle");
    }
  }, [cleanupMic, micState, onTranscript]);

  /** Annule l'écoute en cours sans transcrire */
  const cancelListening = React.useCallback(() => {
    cancelledListenRef.current = true;
    void stopListening();
  }, [stopListening]);

  // ---- Voix (TTS) : file d'élocution en streaming ----

  const stopSpeaking = React.useCallback(() => {
    speakGenRef.current++; // invalide tout ce qui est en vol
    speakingRef.current = false;
    queueRef.current = [];
    try {
      ttsAbortRef.current?.abort();
    } catch {
      /* ignore */
    }
    try {
      prefetchRef.current?.ctrl.abort();
    } catch {
      /* ignore */
    }
    prefetchRef.current = null;
    try {
      currentSourceRef.current?.stop();
    } catch {
      /* déjà arrêté */
    }
    currentSourceRef.current = null;
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        /* ignore */
      }
    }
    setSpeaking(false);
    setSpeakAnalyser(null);
  }, []);

  /** Synthétise un segment de texte → chunks WAV base64 (avec préfetch possible) */
  const synthSegment = React.useCallback((text: string, gen: number, signal: AbortSignal): Promise<string[]> => {
    return fetch("/api/voice/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        voice: streamOptsRef.current.voice,
        speed: streamOptsRef.current.speed,
      }),
      signal,
    })
      .then(async (res) => {
        if (gen !== speakGenRef.current) return [];
        const data = (await res.json()) as { chunks?: string[]; error?: string };
        if (!res.ok || !data.chunks || data.chunks.length === 0) {
          throw new Error(data.error ?? "Synthèse vocale impossible");
        }
        return data.chunks;
      });
  }, []);

  /** Joue un AudioBuffer jusqu'au bout (résout à la fin ou à l'interruption) */
  const playBuffer = (ctx: AudioContext, buffer: AudioBuffer, analyser: AnalyserNode) => {
    return new Promise<void>((resolve) => {
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(analyser);
      currentSourceRef.current = source;
      source.onended = () => {
        if (currentSourceRef.current === source) currentSourceRef.current = null;
        resolve();
      };
      source.start();
    });
  };

  /** Boucle de vidage de la file : synthétise + joue séquentiellement,
   *  avec préfetch de l'élément suivant pendant la lecture courante. */
  const drainQueue = React.useCallback(async () => {
    if (drainingRef.current) return;
    drainingRef.current = true;
    const gen = speakGenRef.current;

    const ctx = getCtx();
    let analyser: AnalyserNode | null = null;
    let failed = false;

    try {
      while (queueRef.current.length > 0 && !failed) {
        if (gen !== speakGenRef.current) return;
        const text = queueRef.current.shift()!;

        // Récupère l'audio (préfetch si disponible, sinon requête directe)
        let chunks: string[];
        const pf = prefetchRef.current;
        if (pf && pf.text === text) {
          prefetchRef.current = null;
          chunks = await pf.promise;
        } else {
          prefetchRef.current = null;
          const ctrl = new AbortController();
          ttsAbortRef.current = ctrl;
          try {
            chunks = await synthSegment(text, gen, ctrl.signal);
          } finally {
            ttsAbortRef.current = null;
          }
        }
        if (gen !== speakGenRef.current) return;

        // Préfetch de la phrase suivante pendant qu'on joue celle-ci
        const next = queueRef.current[0];
        if (next) {
          const ctrl = new AbortController();
          const promise = synthSegment(next, gen, ctrl.signal);
          // évite une rejection « non gérée » si le préfetch n'est jamais consommé
          promise.catch(() => undefined);
          prefetchRef.current = { text: next, promise, ctrl };
        }

        if (chunks.length === 0) continue;

        if (!analyser) {
          if (ctx.state === "suspended") await ctx.resume();
          analyser = ctx.createAnalyser();
          analyser.fftSize = 512;
          analyser.smoothingTimeConstant = 0.7;
          analyser.connect(ctx.destination);
          speakingRef.current = true;
          setSpeaking(true);
          setSpeakAnalyser(analyser);
        }

        for (const chunk of chunks) {
          if (gen !== speakGenRef.current) return;
          const bytes = base64ToUint8(chunk);
          const audioBuffer = await ctx.decodeAudioData(bytes.buffer.slice(0));
          if (gen !== speakGenRef.current) return;
          await playBuffer(ctx, audioBuffer, analyser);
        }
      }
    } catch (e) {
      if (gen === speakGenRef.current) {
        const message = e instanceof Error ? e.message : "Erreur de synthèse vocale";
        if (!message.toLowerCase().includes("aborted")) {
          failed = true;
          toast({ title: "Voix JARVIS indisponible", description: message, variant: "destructive" });
        }
      }
    } finally {
      if (gen === speakGenRef.current && queueRef.current.length === 0) {
        // vidage naturel → plus rien à dire
        if (analyser) analyser.disconnect();
        speakingRef.current = false;
        drainingRef.current = false;
        setSpeaking(false);
        setSpeakAnalyser(null);
        const done = drainDoneRef.current;
        drainDoneRef.current = null;
        done?.();
      } else {
        // interrompu (gen ≠ courant) : la boucle s'arrête, l'état a déjà été
        // réinitialisé par stopSpeaking
        drainingRef.current = false;
        const done = drainDoneRef.current;
        drainDoneRef.current = null;
        done?.();
      }
    }
  }, [synthSegment]);

  /** Ouvre une session d'élocution en streaming (appeler avant les pushStream) */
  const beginStream = React.useCallback(
    (opts?: SpeechStreamOptions) => {
      stopSpeaking();
      streamOptsRef.current = {
        voice: opts?.voice,
        speed: opts?.speed,
        engine: opts?.engine,
        browserVoiceUri: opts?.browserVoiceUri,
      };
    },
    [stopSpeaking]
  );

  // ---- Moteur vocal navigateur : voix françaises natives ----

  /** Énonce un segment via speechSynthesis (résout à la fin ou à l'interruption). */
  const speakBrowserSegment = React.useCallback((text: string, gen: number): Promise<void> => {
    return new Promise<void>((resolve) => {
      const synth = window.speechSynthesis;
      const u = new SpeechSynthesisUtterance(text);
      const voice = pickBrowserVoice();
      if (voice) {
        u.voice = voice;
        u.lang = voice.lang;
      } else {
        u.lang = "fr-FR";
      }
      const speed = streamOptsRef.current.speed;
      if (typeof speed === "number" && speed > 0) u.rate = Math.min(Math.max(speed, 0.5), 2);
      u.pitch = 0.95; // ton légèrement grave, esprit majordome
      u.volume = 1;
      u.onstart = () => {
        if (gen === speakGenRef.current) {
          speakingRef.current = true;
          setSpeaking(true);
        }
      };
      u.onend = () => resolve();
      u.onerror = () => resolve();
      synth.speak(u);
    });
  }, [pickBrowserVoice]);

  /** File d'élocution version navigateur (voix natives, sans AnalyserNode). */
  const drainBrowserQueue = React.useCallback(async () => {
    if (drainingRef.current) return;
    drainingRef.current = true;
    const gen = speakGenRef.current;
    try {
      while (queueRef.current.length > 0) {
        if (gen !== speakGenRef.current) return;
        const text = queueRef.current.shift()!;
        await speakBrowserSegment(text, gen);
      }
    } finally {
      if (gen === speakGenRef.current && queueRef.current.length === 0) {
        speakingRef.current = false;
        drainingRef.current = false;
        setSpeaking(false);
        const done = drainDoneRef.current;
        drainDoneRef.current = null;
        done?.();
      } else {
        drainingRef.current = false;
        const done = drainDoneRef.current;
        drainDoneRef.current = null;
        done?.();
      }
    }
  }, [speakBrowserSegment]);

  /** Enfile un segment de texte (une phrase) — synthétisé/lu dès que possible */
  const pushStream = React.useCallback(
    (text: string) => {
      const clean = text.trim();
      if (!clean) return;
      queueRef.current.push(clean);
      if (streamOptsRef.current.engine === "browser") {
        // voix natives françaises — repli serveur si aucune n'est disponible
        void (async () => {
          await ensureVoicesReady();
          if (pickBrowserVoice()) void drainBrowserQueue();
          else void drainQueue();
        })();
      } else {
        void drainQueue();
      }
    },
    [drainQueue, drainBrowserQueue, ensureVoicesReady, pickBrowserVoice]
  );

  /** Clôt la session : attend que la file soit vide et lue intégralement. */
  const endStream = React.useCallback((): Promise<void> => {
    if (!drainingRef.current && queueRef.current.length === 0) return Promise.resolve();
    return new Promise<void>((resolve) => {
      const prev = drainDoneRef.current;
      drainDoneRef.current = () => {
        prev?.();
        resolve();
      };
    });
  }, []);

  /** Élocution one-shot (test des réglages, réponses hors stream) */
  const speak = React.useCallback(
    async (text: string, opts?: SpeechStreamOptions): Promise<void> => {
      const clean = text.trim();
      if (!clean) return;
      beginStream(opts);
      pushStream(clean);
      await endStream();
    },
    [beginStream, pushStream, endStream]
  );

  // Nettoyage au démontage
  React.useEffect(() => {
    return () => {
      cancelledListenRef.current = true;
      try {
        recorderRef.current?.stop();
      } catch {
        /* ignore */
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      stopLevelMeter();
      speakingRef.current = false;
      try {
        currentSourceRef.current?.stop();
      } catch {
        /* ignore */
      }
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        try {
          window.speechSynthesis.cancel();
        } catch {
          /* ignore */
        }
      }
    };
  }, []);

  const phase: VoicePhase = speaking
    ? "speaking"
    : micState === "listening"
      ? "listening"
      : micState === "transcribing"
        ? "transcribing"
        : "idle";

  return {
    phase,
    micState,
    speaking,
    micError,
    micAnalyser,
    speakAnalyser,
    levelRef,
    startListening,
    stopListening,
    cancelListening,
    beginStream,
    pushStream,
    endStream,
    speak,
    stopSpeaking,
  };
}
