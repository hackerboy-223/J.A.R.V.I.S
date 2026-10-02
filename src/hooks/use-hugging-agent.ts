"use client";

import * as React from "react";
import { toast } from "@/hooks/use-toast";
import type {
  ActiveEngine,
  ChatSseEvent,
  ConversationDetail,
  ConversationSummary,
  PublicSettings,
  UiMessage,
  UpdateSettingsPayload,
} from "@/lib/types";
import { HUD_ACTIONS, HUD_EVENT, type HudAction } from "@/lib/types";

let localIdCounter = 0;
const nextLocalId = () => `local-${Date.now()}-${localIdCounter++}`;

export function useHuggingAgent() {
  const [conversations, setConversations] = React.useState<ConversationSummary[]>([]);
  const [currentId, setCurrentId] = React.useState<string | null>(null);
  const [messages, setMessages] = React.useState<UiMessage[]>([]);
  const [streaming, setStreaming] = React.useState(false);
  const [statusText, setStatusText] = React.useState<string | null>(null);
  const [activeEngine, setActiveEngine] = React.useState<ActiveEngine | null>(null);
  const [settings, setSettings] = React.useState<PublicSettings | null>(null);
  const [loadingConversation, setLoadingConversation] = React.useState(false);
  const abortRef = React.useRef<AbortController | null>(null);
  const currentIdRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    currentIdRef.current = currentId;
  }, [currentId]);

  // ---- Chargement initial ----
  const refreshConversations = React.useCallback(async () => {
    try {
      const res = await fetch("/api/conversations");
      if (res.ok) {
        const data = (await res.json()) as { conversations: ConversationSummary[] };
        setConversations(data.conversations);
      }
    } catch {
      /* silencieux */
    }
  }, []);

  const loadSettings = React.useCallback(async () => {
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const data = (await res.json()) as PublicSettings;
        setSettings(data);
      }
    } catch {
      /* silencieux */
    }
  }, []);

  React.useEffect(() => {
    void refreshConversations();
    void loadSettings();
  }, [refreshConversations, loadSettings]);

  // ---- Sélection / création / suppression ----
  const selectConversation = React.useCallback(async (id: string) => {
    if (streaming) return;
    setLoadingConversation(true);
    setCurrentId(id);
    try {
      const res = await fetch(`/api/conversations/${id}`);
      if (res.ok) {
        const data = (await res.json()) as ConversationDetail;
        setMessages(data.messages);
        setCurrentId(data.id);
      } else {
        toast({ title: "Impossible de charger la conversation", variant: "destructive" });
      }
    } catch {
      toast({ title: "Erreur réseau", variant: "destructive" });
    } finally {
      setLoadingConversation(false);
    }
  }, [streaming]);

  const newConversation = React.useCallback(() => {
    if (streaming) return;
    setCurrentId(null);
    setMessages([]);
  }, [streaming]);

  const deleteConversation = React.useCallback(
    async (id: string) => {
      try {
        const res = await fetch(`/api/conversations/${id}`, { method: "DELETE" });
        if (res.ok) {
          if (currentIdRef.current === id) {
            setCurrentId(null);
            setMessages([]);
          }
          await refreshConversations();
          toast({ title: "Conversation supprimée" });
        }
      } catch {
        toast({ title: "Erreur lors de la suppression", variant: "destructive" });
      }
    },
    [refreshConversations]
  );

  const renameConversation = React.useCallback(
    async (id: string, title: string) => {
      try {
        const res = await fetch(`/api/conversations/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title }),
        });
        if (res.ok) {
          setConversations((prev) =>
            prev.map((c) => (c.id === id ? { ...c, title } : c))
          );
        }
      } catch {
        toast({ title: "Erreur lors du renommage", variant: "destructive" });
      }
    },
    []
  );

  // ---- Envoi de message avec SSE ----
  // Résout avec le texte final de l'assistant (pour la synthèse vocale), null sinon.
  // opts.onText : callback immédiat sur chaque delta — permet de démarrer la
  // synthèse vocale avant la fin de la génération (latence perçue réduite).
  const sendMessage = React.useCallback(
    async (
      content: string,
      opts?: { voiceMode?: boolean; onText?: (delta: string) => void }
    ): Promise<string | null> => {
      if (streaming) return null;
      const userMsg: UiMessage = { id: nextLocalId(), role: "user", content };
      setMessages((prev) => [...prev, userMsg]);
      setStreaming(true);
      setStatusText("Connexion au noyau J.A.R.V.I.S.…");
      setActiveEngine(null);

      const controller = new AbortController();
      abortRef.current = controller;

      let finalText = "";

      // id du message assistant en cours de stream
      let assistantId: string | null = null;
      const ensureAssistant = (): string => {
        if (!assistantId) {
          const id = nextLocalId();
          assistantId = id;
          setMessages((prev) => [
            ...prev,
            { id, role: "assistant", content: "", pending: true },
          ]);
        }
        return assistantId;
      };

      // ---- Batching des tokens (perf) ----
      // Au lieu d'un setMessages par token (des dizaines de re-renders/s),
      // on accumule les deltas et on ne met à jour l'UI que toutes les 50 ms.
      let batchedText = "";
      let batchedId: string | null = null;
      let flushTimer: ReturnType<typeof setTimeout> | null = null;
      const flushTokens = () => {
        flushTimer = null;
        if (!batchedText || !batchedId) return;
        const id = batchedId;
        const chunk = batchedText;
        batchedText = "";
        setMessages((prev) =>
          prev.map((m) => (m.id === id ? { ...m, content: m.content + chunk } : m))
        );
      };
      const scheduleFlush = (id: string) => {
        batchedId = id;
        if (flushTimer === null) {
          flushTimer = setTimeout(flushTokens, 50);
        }
      };

      const handleEvent = (ev: ChatSseEvent) => {
        switch (ev.type) {
          case "start":
            setCurrentId(ev.conversationId);
            setActiveEngine(ev.engine);
            setStatusText("Réflexion…");
            break;
          case "status":
            setStatusText(ev.status);
            break;
          case "tool_start":
            // flush des tokens en attente avant de réorganiser les messages
            if (flushTimer !== null) {
              clearTimeout(flushTimer);
              flushTokens();
            }
            // Action HUD : JARVIS anime l'interface holographique
            if (ev.tool === "hud_action") {
              const action = ev.args?.action;
              if (typeof action === "string" && HUD_ACTIONS.includes(action as HudAction)) {
                window.dispatchEvent(
                  new CustomEvent<HudAction>(HUD_EVENT, { detail: action as HudAction })
                );
              }
            }
            // finalise la bulle assistant en cours (texte éventuel avant l'appel d'outil)
            assistantId = null;
            setMessages((prev) => {
              const cleaned = prev
                .map((m) =>
                  m.role === "assistant" && m.pending
                    ? { ...m, pending: false }
                    : m
                )
                .filter((m) => m.role !== "assistant" || m.content.trim().length > 0);
              return [
                ...cleaned,
                {
                  id: nextLocalId(),
                  role: "tool" as const,
                  content: "",
                  toolName: ev.tool,
                  toolArgs: JSON.stringify(ev.args, null, 2),
                  step: ev.step,
                  pending: true,
                },
              ];
            });
            setStatusText(`Outil : ${ev.tool}…`);
            break;
          case "tool_result": {
            const step = ev.step;
            setMessages((prev) => {
              // met à jour la carte outil correspondant à cette étape
              const idx = [...prev]
                .reverse()
                .findIndex(
                  (m) => m.role === "tool" && m.step === step && m.toolName === ev.tool
                );
              if (idx === -1) return prev;
              const realIdx = prev.length - 1 - idx;
              const copy = [...prev];
              copy[realIdx] = {
                ...copy[realIdx],
                toolResult: JSON.stringify(ev.result, null, 2),
                durationMs: ev.durationMs,
                pending: false,
                error: ev.isError ? "tool_error" : undefined,
              };
              return copy;
            });
            setStatusText("Analyse des résultats…");
            break;
          }
          case "token": {
            const id = ensureAssistant();
            finalText += ev.text;
            // pipeline vocal : delta immédiat (pas de re-render React ici)
            opts?.onText?.(ev.text);
            // UI : batché à 20 fps max
            batchedText += ev.text;
            scheduleFlush(id);
            setStatusText(null);
            break;
          }
          case "done": {
            if (flushTimer !== null) {
              clearTimeout(flushTimer);
              flushTokens();
            }
            if (assistantId) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, pending: false, id: ev.messageId || m.id }
                    : m
                )
              );
            }
            // refresh unique : le finally s'en charge (évite un doublon de requête)
            setStatusText(null);
            break;
          }
          case "error": {
            if (flushTimer !== null) {
              clearTimeout(flushTimer);
              flushTokens();
            }
            const id = ensureAssistant();
            setMessages((prev) =>
              prev.map((m) => (m.id === id ? { ...m, pending: false, error: ev.message } : m))
            );
            setStatusText(null);
            break;
          }
        }
      };

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversationId: currentIdRef.current,
            content,
            voiceMode: opts?.voiceMode === true,
          }),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          let message = `Erreur serveur (${res.status})`;
          try {
            const data = await res.json();
            if (data?.error) message = data.error;
          } catch {
            /* ignore */
          }
          throw new Error(message);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";
          for (const part of parts) {
            const line = part
              .split("\n")
              .find((l) => l.startsWith("data:"));
            if (!line) continue;
            const payload = line.slice(line.indexOf(":") + 1).trim();
            if (!payload) continue;
            try {
              handleEvent(JSON.parse(payload) as ChatSseEvent);
            } catch {
              /* événement malformé : ignoré */
            }
          }
        }
        return finalText.trim() || null;
      } catch (err) {
        if (flushTimer !== null) {
          clearTimeout(flushTimer);
          flushTokens();
        }
        if ((err as Error).name !== "AbortError") {
          const message =
            err instanceof Error ? err.message : "Une erreur inattendue est survenue";
          setMessages((prev) => {
            const hasPending = prev.some((m) => m.pending);
            if (hasPending) {
              return prev.map((m) =>
                m.pending ? { ...m, pending: false, error: message } : m
              );
            }
            return [
              ...prev,
              {
                id: nextLocalId(),
                role: "assistant",
                content: "",
                error: message,
              },
            ];
          });
          toast({ title: "Erreur de l'agent", description: message, variant: "destructive" });
        } else {
          // arrêt volontaire
          setMessages((prev) =>
            prev.map((m) => {
              if (!m.pending) return m;
              if (m.role === "tool") {
                return { ...m, pending: false, error: "interrompu" };
              }
              return {
                ...m,
                pending: false,
                content: m.content || "_Génération interrompue._",
              };
            })
          );
        }
      } finally {
        if (flushTimer !== null) {
          clearTimeout(flushTimer);
          flushTokens();
        }
        setStreaming(false);
        setStatusText(null);
        abortRef.current = null;
        void refreshConversations();
      }
      return null;
    },
    [streaming, refreshConversations]
  );

  const stop = React.useCallback(() => {
    abortRef.current?.abort();
  }, []);

  // ---- Réglages ----
  const saveSettings = React.useCallback(
    async (payload: UpdateSettingsPayload) => {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = (await res.json()) as PublicSettings;
        setSettings(data);
        toast({ title: "Réglages enregistrés ✅" });
      } else {
        let message = "Échec de l'enregistrement";
        try {
          const data = await res.json();
          if (data?.error) message = data.error;
        } catch {
          /* ignore */
        }
        toast({ title: message, variant: "destructive" });
        throw new Error(message);
      }
    },
    []
  );

  const testConnection = React.useCallback(async (token: string, model: string) => {
    try {
      const res = await fetch("/api/settings/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token || undefined, model }),
      });
      const data = await res.json();
      return {
        ok: res.ok && !!data.ok,
        message: (data.message as string) ?? "Réponse inattendue du serveur",
      };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : "Erreur réseau" };
    }
  }, []);

  return {
    conversations,
    currentId,
    messages,
    streaming,
    statusText,
    activeEngine,
    settings,
    loadingConversation,
    selectConversation,
    newConversation,
    deleteConversation,
    renameConversation,
    sendMessage,
    stop,
    saveSettings,
    testConnection,
  };
}
