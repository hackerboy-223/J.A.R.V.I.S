"use client";

import * as React from "react";
import {
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { ConversationSummary } from "@/lib/types";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `il y a ${h} h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `il y a ${d} j`;
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

interface SidebarProps {
  conversations: ConversationSummary[];
  currentId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

export function SidebarContent({
  conversations,
  currentId,
  onNew,
  onSelect,
  onDelete,
  onRename,
}: SidebarProps) {
  const [deleteTarget, setDeleteTarget] = React.useState<ConversationSummary | null>(null);
  const [renameTarget, setRenameTarget] = React.useState<ConversationSummary | null>(null);
  const [renameValue, setRenameValue] = React.useState("");
  const [query, setQuery] = React.useState("");

  const filteredConversations = React.useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("fr");
    if (!normalized) return conversations;
    return conversations.filter((conversation) =>
      conversation.title.toLocaleLowerCase("fr").includes(normalized)
    );
  }, [conversations, query]);

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 p-3">
        <Button onClick={onNew} className="w-full gap-2 shadow-sm">
          <Plus className="h-4 w-4" /> Nouvelle conversation
        </Button>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Rechercher…"
            aria-label="Rechercher une conversation"
            className="h-8 border-primary/15 bg-primary/[0.035] pl-8 text-xs"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        <p className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Conversations
        </p>
        {conversations.length === 0 && (
          <p className="px-2 py-4 text-xs text-muted-foreground">
            Aucune conversation pour le moment. Lance-toi ! ✨
          </p>
        )}
        {conversations.length > 0 && filteredConversations.length === 0 && (
          <p className="px-2 py-4 text-xs text-muted-foreground">
            Aucun résultat pour « {query.trim()} ».
          </p>
        )}
        <ul className="space-y-0.5">
          {filteredConversations.map((c) => (
            <li key={c.id}>
              <div
                className={cn(
                  "group flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors",
                  currentId === c.id
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/60"
                )}
              >
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  className="flex min-w-0 flex-1 flex-col items-start gap-0.5"
                >
                  <span className="flex w-full items-center gap-1.5">
                    <MessageSquare
                      className={cn(
                        "h-3.5 w-3.5 shrink-0",
                        currentId === c.id ? "text-primary" : "text-muted-foreground"
                      )}
                    />
                    <span className="truncate text-[13px] font-medium">{c.title}</span>
                  </span>
                  <span className="pl-5 text-[11px] text-muted-foreground">
                    {timeAgo(c.updatedAt)}
                  </span>
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      aria-label="Options de la conversation"
                      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-opacity hover:bg-background/60 hover:text-foreground focus:opacity-100 group-hover:opacity-100"
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-40">
                    <DropdownMenuItem
                      onClick={() => {
                        setRenameTarget(c);
                        setRenameValue(c.title);
                      }}
                    >
                      <Pencil className="mr-2 h-3.5 w-3.5" /> Renommer
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setDeleteTarget(c)}
                      className="text-destructive focus:text-destructive"
                    >
                      <Trash2 className="mr-2 h-3.5 w-3.5" /> Supprimer
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="border-t p-3">
        <Badge variant="outline" className="gap-1.5 border-primary/30 bg-primary/5 py-1.5 text-[11px] text-foreground">
          <Sparkles className="h-3 w-3 text-primary" />
          Propulsé par Hugging Face 🤗
        </Badge>
      </div>

      {/* Confirmation suppression */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette conversation ?</AlertDialogTitle>
            <AlertDialogDescription>
              « {deleteTarget?.title} » et tous ses messages seront définitivement supprimés.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget) onDelete(deleteTarget.id);
                setDeleteTarget(null);
              }}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Renommage */}
      <Dialog open={!!renameTarget} onOpenChange={(o) => !o && setRenameTarget(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Renommer la conversation</DialogTitle>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            placeholder="Nouveau nom"
            maxLength={80}
            onKeyDown={(e) => {
              if (e.key === "Enter" && renameTarget && renameValue.trim()) {
                onRename(renameTarget.id, renameValue.trim());
                setRenameTarget(null);
              }
            }}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameTarget(null)}>
              Annuler
            </Button>
            <Button
              disabled={!renameValue.trim()}
              onClick={() => {
                if (renameTarget && renameValue.trim()) {
                  onRename(renameTarget.id, renameValue.trim());
                  setRenameTarget(null);
                }
              }}
            >
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
