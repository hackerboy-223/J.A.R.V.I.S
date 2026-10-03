"use client";

import * as React from "react";
import {
  Bell,
  Calculator,
  CheckCircle2,
  Cpu,
  Download,
  Folder,
  FolderOpen,
  HardDrive,
  Laptop,
  LockKeyhole,
  Mic,
  NotepadText,
  Plus,
  Radio,
  RefreshCw,
  Settings2,
  ShieldCheck,
  TerminalSquare,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import type { SystemStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

type BrowserPermission = "granted" | "denied" | "prompt" | "unsupported" | "unknown";

interface CapabilityResponse {
  host: {
    hostname: string;
    platform: string;
    arch: string;
    nodeVersion: string;
  };
  capabilities: {
    systemStatus: boolean;
    voice: boolean;
    webSearch: boolean;
    pcControl: boolean;
    runJs: boolean;
  };
  pcControl: {
    available: boolean;
    reason: string | null;
    allowedApps: string[];
    allowedFolders: string[];
    allowedProtocols: string[];
  };
}

interface ControlCenterProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  systemStatus: SystemStatus | null;
  onNewConversation: () => void;
  onOpenSettings: () => void;
  voiceMode: boolean;
  onToggleVoice: () => void;
}

function StateBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 border-primary/20 text-[10px] font-semibold",
        ok
          ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-500"
          : "border-muted-foreground/25 bg-muted/30 text-muted-foreground"
      )}
    >
      {ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
      {label}
    </Badge>
  );
}

function PermissionBadge({ value }: { value: BrowserPermission }) {
  const ok = value === "granted";
  const label =
    value === "granted"
      ? "AUTORISÉ"
      : value === "denied"
        ? "BLOQUÉ"
        : value === "prompt"
          ? "À DEMANDER"
          : value === "unsupported"
            ? "INDISPONIBLE"
            : "INCONNU";
  return <StateBadge ok={ok} label={label} />;
}

export function ControlCenter({
  open,
  onOpenChange,
  systemStatus,
  onNewConversation,
  onOpenSettings,
  voiceMode,
  onToggleVoice,
}: ControlCenterProps) {
  const [server, setServer] = React.useState<CapabilityResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [actionStatus, setActionStatus] = React.useState<string | null>(null);
  const [microphone, setMicrophone] = React.useState<BrowserPermission>("unknown");
  const [notifications, setNotifications] = React.useState<BrowserPermission>("unknown");
  const [persistentStorage, setPersistentStorage] = React.useState(false);

  const refreshBrowserPermissions = React.useCallback(async () => {
    if (typeof window === "undefined") return;

    if (!navigator.mediaDevices?.getUserMedia) {
      setMicrophone("unsupported");
    } else {
      // La Permissions API ne normalise pas "microphone" de la même façon
      // dans tous les navigateurs. On demande donc l'accès uniquement sur geste.
      setMicrophone((current) =>
        current === "granted" || current === "denied" ? current : "prompt"
      );
    }

    if (!("Notification" in window)) {
      setNotifications("unsupported");
    } else {
      setNotifications(
        Notification.permission === "default"
          ? "prompt"
          : (Notification.permission as BrowserPermission)
      );
    }

    try {
      setPersistentStorage(Boolean(await navigator.storage?.persisted?.()));
    } catch {
      setPersistentStorage(false);
    }
  }, []);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/capabilities", { cache: "no-store" });
      const data = (await res.json()) as CapabilityResponse & { error?: string };
      if (!res.ok) throw new Error(data.error || "Impossible de lire les capacités");
      setServer(data);
      await refreshBrowserPermissions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible de lire les capacités");
    } finally {
      setLoading(false);
    }
  }, [refreshBrowserPermissions]);

  React.useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  const requestMicrophone = async () => {
    setActionStatus(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicrophone("granted");
      setActionStatus("Microphone autorisé.");
    } catch {
      setMicrophone("denied");
      setActionStatus("Le navigateur a refusé l'accès au microphone.");
    }
  };

  const requestNotifications = async () => {
    if (!("Notification" in window)) return;
    const state = await Notification.requestPermission();
    setNotifications(state as BrowserPermission);
    setActionStatus(
      state === "granted" ? "Notifications autorisées." : "Notifications non autorisées."
    );
  };

  const requestPersistentStorage = async () => {
    try {
      const granted = Boolean(await navigator.storage?.persist?.());
      setPersistentStorage(granted);
      setActionStatus(
        granted
          ? "Le navigateur protège maintenant davantage les données locales de J.A.R.V.I.S."
          : "Le navigateur n'a pas accordé le stockage persistant."
      );
    } catch {
      setActionStatus("Stockage persistant indisponible dans ce navigateur.");
    }
  };

  const pcAction = async (action: "open_app" | "open_folder", target: string, label: string) => {
    setActionStatus(`Ouverture : ${label}…`);
    try {
      const res = await fetch("/api/pc/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, target }),
      });
      const data = (await res.json()) as { error?: string };
      if (!res.ok) throw new Error(data.error || "Action refusée");
      setActionStatus(`${label} ouvert sur la machine hôte.`);
    } catch (e) {
      setActionStatus(e instanceof Error ? e.message : "Action impossible");
    }
  };

  const usedMemory =
    systemStatus && systemStatus.totalMem > 0
      ? Math.round(((systemStatus.totalMem - systemStatus.freeMem) / systemStatus.totalMem) * 100)
      : null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto border-primary/20 bg-background/95 p-0 backdrop-blur-xl sm:max-w-[460px]">
        <SheetHeader className="border-b border-primary/15 px-5 py-5 text-left">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 text-primary">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <SheetTitle className="font-hud text-base tracking-[0.16em]">CONTROL CENTER</SheetTitle>
              <SheetDescription>
                Capacités, permissions et actions locales — visibles et contrôlables.
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="space-y-6 p-5">
          <section>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">Accès rapides</p>
                <p className="text-xs text-muted-foreground">Actions immédiates sans passer par le modèle IA.</p>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => void refresh()} disabled={loading} aria-label="Actualiser">
                <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" className="justify-start gap-2" onClick={onNewConversation}>
                <Plus className="h-4 w-4 text-primary" /> Nouveau chat
              </Button>
              <Button variant="outline" className="justify-start gap-2" onClick={onToggleVoice}>
                <Radio className={cn("h-4 w-4", voiceMode ? "text-gold" : "text-primary")} />
                {voiceMode ? "Couper VOX" : "Activer VOX"}
              </Button>
              <Button variant="outline" className="col-span-2 justify-start gap-2" onClick={onOpenSettings}>
                <Settings2 className="h-4 w-4 text-primary" /> Réglages J.A.R.V.I.S.
              </Button>
            </div>
          </section>

          <Separator />

          <section>
            <div className="mb-3">
              <p className="text-sm font-semibold">Machine hôte</p>
              <p className="text-xs text-muted-foreground">
                Ce sont les capacités du serveur qui exécute J.A.R.V.I.S., pas des pouvoirs simulés.
              </p>
            </div>
            <div className="space-y-2 rounded-xl border border-primary/15 bg-primary/[0.035] p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2 text-sm"><Laptop className="h-4 w-4 text-primary" /> Hôte</span>
                <span className="max-w-56 truncate font-mono text-xs text-muted-foreground">
                  {server?.host.hostname ?? systemStatus?.hostname ?? "—"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2 text-sm"><Cpu className="h-4 w-4 text-primary" /> Système</span>
                <span className="text-right font-mono text-xs text-muted-foreground">
                  {server ? `${server.host.platform} · ${server.host.arch}` : "—"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2 text-sm"><HardDrive className="h-4 w-4 text-primary" /> Mémoire</span>
                <span className="font-mono text-xs text-muted-foreground">{usedMemory === null ? "—" : `${usedMemory}% utilisée`}</span>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-xl border border-border/60 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-xs font-medium">Contrôle PC</span>
                  <StateBadge ok={Boolean(server?.capabilities.pcControl)} label={server?.capabilities.pcControl ? "ACTIF" : "VERROUILLÉ"} />
                </div>
                <p className="text-[11px] leading-relaxed text-muted-foreground">Ouverture limitée d'apps et dossiers autorisés.</p>
              </div>
              <div className="rounded-xl border border-border/60 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-xs font-medium">Sandbox JS</span>
                  <StateBadge ok={Boolean(server?.capabilities.runJs)} label={server?.capabilities.runJs ? "ACTIF" : "VERROUILLÉ"} />
                </div>
                <p className="text-[11px] leading-relaxed text-muted-foreground">Exécution de calculs/script uniquement si opt-in serveur.</p>
              </div>
            </div>
            {server?.pcControl.reason && (
              <p className="mt-2 rounded-lg border border-gold/20 bg-gold/[0.06] px-3 py-2 text-[11px] text-gold">
                {server.pcControl.reason}
              </p>
            )}
          </section>

          <Separator />

          <section>
            <div className="mb-3">
              <p className="text-sm font-semibold">Permissions navigateur</p>
              <p className="text-xs text-muted-foreground">Aucune permission sensible n'est demandée automatiquement.</p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-3 rounded-xl border border-border/60 p-3">
                <Mic className="h-4 w-4 text-primary" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">Microphone</p>
                  <p className="text-[11px] text-muted-foreground">Pour la conversation vocale.</p>
                </div>
                <PermissionBadge value={microphone} />
                {microphone !== "granted" && microphone !== "unsupported" && (
                  <Button size="sm" variant="outline" onClick={() => void requestMicrophone()}>Autoriser</Button>
                )}
              </div>

              <div className="flex items-center gap-3 rounded-xl border border-border/60 p-3">
                <Bell className="h-4 w-4 text-primary" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">Notifications</p>
                  <p className="text-[11px] text-muted-foreground">Pour les alertes locales utiles.</p>
                </div>
                <PermissionBadge value={notifications} />
                {notifications !== "granted" && notifications !== "unsupported" && (
                  <Button size="sm" variant="outline" onClick={() => void requestNotifications()}>Autoriser</Button>
                )}
              </div>

              <div className="flex items-center gap-3 rounded-xl border border-border/60 p-3">
                <LockKeyhole className="h-4 w-4 text-primary" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">Stockage persistant</p>
                  <p className="text-[11px] text-muted-foreground">Réduit le risque d'effacement des données locales par le navigateur.</p>
                </div>
                <StateBadge ok={persistentStorage} label={persistentStorage ? "PROTÉGÉ" : "STANDARD"} />
                {!persistentStorage && (
                  <Button size="sm" variant="outline" onClick={() => void requestPersistentStorage()}>Protéger</Button>
                )}
              </div>
            </div>
          </section>

          <Separator />

          <section>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold">Actions locales autorisées</p>
                <p className="text-xs text-muted-foreground">Liste fermée, réversible, sans shell arbitraire.</p>
              </div>
              <TerminalSquare className="h-4 w-4 text-primary" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" disabled={!server?.pcControl.available} onClick={() => void pcAction("open_app", "calculator", "Calculatrice")} className="justify-start gap-2">
                <Calculator className="h-4 w-4" /> Calculatrice
              </Button>
              <Button variant="outline" disabled={!server?.pcControl.available} onClick={() => void pcAction("open_app", "notepad", "Bloc-notes")} className="justify-start gap-2">
                <NotepadText className="h-4 w-4" /> Bloc-notes
              </Button>
              <Button variant="outline" disabled={!server?.pcControl.available} onClick={() => void pcAction("open_app", "explorer", "Explorateur")} className="justify-start gap-2">
                <FolderOpen className="h-4 w-4" /> Explorateur
              </Button>
              <Button variant="outline" disabled={!server?.pcControl.available} onClick={() => void pcAction("open_folder", "documents", "Documents")} className="justify-start gap-2">
                <Folder className="h-4 w-4" /> Documents
              </Button>
              <Button variant="outline" disabled={!server?.pcControl.available} onClick={() => void pcAction("open_folder", "downloads", "Téléchargements")} className="justify-start gap-2">
                <Download className="h-4 w-4" /> Téléchargements
              </Button>
              <Button variant="outline" disabled={!server?.pcControl.available} onClick={() => void pcAction("open_folder", "project", "Projet J.A.R.V.I.S.")} className="justify-start gap-2">
                <FolderOpen className="h-4 w-4" /> Projet
              </Button>
            </div>
          </section>

          {(actionStatus || error) && (
            <div
              role="status"
              className={cn(
                "rounded-xl border px-3 py-2 text-xs",
                error
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : "border-primary/25 bg-primary/[0.06] text-foreground"
              )}
            >
              {error ?? actionStatus}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
