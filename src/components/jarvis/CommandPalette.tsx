"use client";

import * as React from "react";
import {
  Command,
  MessageSquarePlus,
  Mic,
  Search,
  Settings2,
  ShieldCheck,
  Square,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNewConversation: () => void;
  onOpenSettings: () => void;
  onOpenControlCenter: () => void;
  onToggleVoice: () => void;
  onStop: () => void;
  busy: boolean;
  voiceMode: boolean;
}

export function CommandPalette({
  open,
  onOpenChange,
  onNewConversation,
  onOpenSettings,
  onOpenControlCenter,
  onToggleVoice,
  onStop,
  busy,
  voiceMode,
}: CommandPaletteProps) {
  const [query, setQuery] = React.useState("");

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onOpenChange, open]);

  React.useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const closeAnd = (fn: () => void) => {
    onOpenChange(false);
    window.setTimeout(fn, 0);
  };

  const actions = [
    {
      id: "new",
      label: "Nouvelle conversation",
      detail: "Ouvrir un espace de travail propre",
      icon: MessageSquarePlus,
      run: onNewConversation,
      keywords: "nouveau chat conversation",
    },
    {
      id: "focus",
      label: "Écrire une instruction",
      detail: "Placer le curseur dans le champ de commande",
      icon: Command,
      run: () => document.getElementById("composer-input")?.focus(),
      keywords: "focus message composer instruction",
    },
    {
      id: "voice",
      label: voiceMode ? "Désactiver le mode vocal" : "Activer le mode vocal",
      detail: "Basculer la conversation mains libres",
      icon: Mic,
      run: onToggleVoice,
      keywords: "voix micro vox vocal",
    },
    {
      id: "control",
      label: "Ouvrir le Control Center",
      detail: "Permissions, machine hôte et actions locales",
      icon: ShieldCheck,
      run: onOpenControlCenter,
      keywords: "permissions controle pc système powers",
    },
    {
      id: "settings",
      label: "Ouvrir les réglages",
      detail: "Voix, moteur et préférences",
      icon: Settings2,
      run: onOpenSettings,
      keywords: "paramètres settings configuration",
    },
    ...(busy
      ? [{
          id: "stop",
          label: "Arrêter l'opération en cours",
          detail: "Interrompre génération, voix et écoute",
          icon: Square,
          run: onStop,
          keywords: "stop arreter interrompre annuler",
        }]
      : []),
  ];

  const normalized = query.trim().toLowerCase();
  const filtered = normalized
    ? actions.filter((action) =>
        `${action.label} ${action.detail} ${action.keywords}`.toLowerCase().includes(normalized)
      )
    : actions;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[18%] max-w-xl translate-y-0 gap-0 overflow-hidden border-primary/25 bg-background/95 p-0 shadow-2xl backdrop-blur-xl sm:rounded-2xl">
        <DialogTitle className="sr-only">Palette de commandes J.A.R.V.I.S.</DialogTitle>
        <DialogDescription className="sr-only">
          Rechercher et exécuter rapidement une action d'interface.
        </DialogDescription>

        <div className="flex items-center gap-2 border-b border-primary/15 px-4">
          <Search className="h-4 w-4 text-primary" />
          <Input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Commande, réglage, permission…"
            className="h-12 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
          />
          <kbd className="hidden rounded-md border border-border/70 bg-muted/50 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:inline">
            ESC
          </kbd>
        </div>

        <div className="max-h-[360px] overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-muted-foreground">
              Aucune commande trouvée.
            </div>
          ) : (
            filtered.map((action, index) => {
              const Icon = action.icon;
              return (
                <Button
                  key={action.id}
                  type="button"
                  variant="ghost"
                  onClick={() => closeAnd(action.run)}
                  className={cn(
                    "mb-1 h-auto w-full justify-start gap-3 rounded-xl px-3 py-3 text-left",
                    index === 0 && "bg-primary/[0.05]"
                  )}
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/[0.06] text-primary">
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">{action.label}</span>
                    <span className="block truncate text-[11px] font-normal text-muted-foreground">{action.detail}</span>
                  </span>
                </Button>
              );
            })
          )}
        </div>

        <div className="flex items-center justify-between border-t border-primary/15 px-4 py-2 text-[10px] text-muted-foreground">
          <span>J.A.R.V.I.S. COMMAND PALETTE</span>
          <span>Ctrl / ⌘ + K</span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
