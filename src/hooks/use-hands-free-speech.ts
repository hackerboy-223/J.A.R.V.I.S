"use client";

import * as React from "react";

interface SpeechAlternativeLike {
  transcript: string;
  confidence: number;
}

interface SpeechResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  readonly 0: SpeechAlternativeLike;
}

interface SpeechResultListLike {
  readonly length: number;
  readonly [index: number]: SpeechResultLike;
}

interface SpeechEventLike extends Event {
  readonly resultIndex: number;
  readonly results: SpeechResultListLike;
}

interface SpeechErrorEventLike extends Event {
  readonly error: string;
  readonly message?: string;
}

interface BrowserSpeechRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onresult: ((event: SpeechEventLike) => void) | null;
  onerror: ((event: SpeechErrorEventLike) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type BrowserSpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

function recognitionConstructor(): BrowserSpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const speechWindow = window as typeof window & {
    SpeechRecognition?: BrowserSpeechRecognitionConstructor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

function cleanJoin(...parts: string[]): string {
  return parts
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

export function useHandsFreeSpeech({
  onUtterance,
  lang = "fr-FR",
  silenceMs = 900,
}: {
  onUtterance: (text: string) => void;
  lang?: string;
  silenceMs?: number;
}) {
  const [supported, setSupported] = React.useState(false);
  const [enabled, setEnabled] = React.useState(false);
  const [listening, setListening] = React.useState(false);
  const [processing, setProcessing] = React.useState(false);
  const [transcript, setTranscript] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const recognitionRef = React.useRef<BrowserSpeechRecognition | null>(null);
  const wantedRef = React.useRef(false);
  const processingRef = React.useRef(false);
  const pausedRef = React.useRef(false);
  const finalRef = React.useRef("");
  const interimRef = React.useRef("");
  const silenceTimerRef = React.useRef<number | null>(null);
  const restartTimerRef = React.useRef<number | null>(null);
  const onUtteranceRef = React.useRef(onUtterance);
  const startRecognitionRef = React.useRef<() => void>(() => {});

  React.useEffect(() => {
    onUtteranceRef.current = onUtterance;
  }, [onUtterance]);

  React.useEffect(() => {
    setSupported(Boolean(recognitionConstructor()));
  }, []);

  const clearTimers = React.useCallback(() => {
    if (silenceTimerRef.current !== null) {
      window.clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (restartTimerRef.current !== null) {
      window.clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
  }, []);

  const commitUtterance = React.useCallback(() => {
    if (processingRef.current) return;

    const text = cleanJoin(finalRef.current, interimRef.current);
    if (!text) return;

    clearTimers();
    processingRef.current = true;
    setProcessing(true);
    setListening(false);
    setTranscript(text);

    try {
      recognitionRef.current?.stop();
    } catch {
      // Le moteur peut déjà être arrêté après une fin de phrase.
    }

    finalRef.current = "";
    interimRef.current = "";
    onUtteranceRef.current(text);
  }, [clearTimers]);

  const ensureRecognition = React.useCallback((): BrowserSpeechRecognition | null => {
    if (recognitionRef.current) return recognitionRef.current;

    const Recognition = recognitionConstructor();
    if (!Recognition) return null;

    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = lang;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      if (!wantedRef.current || processingRef.current || pausedRef.current) {
        try {
          recognition.stop();
        } catch {
          // ignore
        }
        return;
      }
      setListening(true);
      setError(null);
    };

    recognition.onresult = (event) => {
      if (!wantedRef.current || processingRef.current || pausedRef.current) return;

      let interim = "";
       for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result?.[0]?.transcript?.trim() ?? "";
        if (!text) continue;

        if (result.isFinal) {
          finalRef.current = cleanJoin(finalRef.current, text);
        } else {
          interim = cleanJoin(interim, text);
        }
      }

      interimRef.current = interim;
      setTranscript(cleanJoin(finalRef.current, interimRef.current));

      const currentText = cleanJoin(finalRef.current, interimRef.current);
      if (currentText) {
        if (silenceTimerRef.current !== null) {
          window.clearTimeout(silenceTimerRef.current);
        }
        // La période de silence fait office de VAD conversationnel.
        // On accepte aussi la meilleure hypothèse intermédiaire si le navigateur
        // tarde à publier un résultat final.
        silenceTimerRef.current = window.setTimeout(commitUtterance, silenceMs);
      }
    };

    recognition.onerror = (event) => {
      const code = event.error || "unknown";
      if (code === "aborted" || code === "no-speech") return;

      setError(
        code === "not-allowed"
          ? "Permission microphone refusée."
          : code === "audio-capture"
            ? "Aucun microphone disponible."
            : `Reconnaissance vocale indisponible : ${code}`
      );
    };

    recognition.onend = () => {
      setListening(false);

      if (!wantedRef.current || processingRef.current || pausedRef.current) return;

      restartTimerRef.current = window.setTimeout(() => {
        startRecognitionRef.current();
      }, 250);
    };

    recognitionRef.current = recognition;
    return recognition;
  }, [commitUtterance, lang, silenceMs]);

  const startRecognition = React.useCallback(() => {
    if (!wantedRef.current || processingRef.current) return;

    const recognition = ensureRecognition();
    if (!recognition) {
      setSupported(false);
      return;
    }

    try {
      recognition.start();
    } catch (e) {
      const name = e instanceof DOMException ? e.name : "";
      if (name !== "InvalidStateError") {
        setError(e instanceof Error ? e.message : "Impossible de démarrer la reconnaissance vocale.");
      }
    }
  }, [ensureRecognition]);

  React.useEffect(() => {
    startRecognitionRef.current = startRecognition;
  }, [startRecognition]);

  const start = React.useCallback((): boolean => {
    if (!recognitionConstructor()) {
      setSupported(false);
      return false;
    }

    clearTimers();
    wantedRef.current = true;
    processingRef.current = false;
    pausedRef.current = false;
    finalRef.current = "";
    interimRef.current = "";
    setEnabled(true);
    setProcessing(false);
    setTranscript("");
    setError(null);
    startRecognition();
    return true;
  }, [clearTimers, startRecognition]);

  const pause = React.useCallback(() => {
    clearTimers();
    pausedRef.current = true;
    setListening(false);
    try {
      recognitionRef.current?.stop();
    } catch {
      // ignore
    }
  }, [clearTimers]);

  const resume = React.useCallback(() => {
    if (!wantedRef.current) return;

    clearTimers();
    pausedRef.current = false;
    finalRef.current = "";
    interimRef.current = "";
    processingRef.current = false;
    setProcessing(false);
    setTranscript("");
    setError(null);
    startRecognition();
  }, [clearTimers, startRecognition]);

  const stop = React.useCallback(() => {
    clearTimers();
    wantedRef.current = false;
    processingRef.current = false;
    pausedRef.current = false;
    finalRef.current = "";
    interimRef.current = "";
    setEnabled(false);
    setListening(false);
    setProcessing(false);
    setTranscript("");

    try {
      recognitionRef.current?.abort();
    } catch {
      // ignore
    }
  }, [clearTimers]);

  React.useEffect(() => {
    return () => {
      clearTimers();
      wantedRef.current = false;
      try {
        recognitionRef.current?.abort();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    };
  }, [clearTimers]);

  return {
    supported,
    enabled,
    listening,
    processing,
    transcript,
    error,
    start,
    pause,
    resume,
    stop,
  };
}
