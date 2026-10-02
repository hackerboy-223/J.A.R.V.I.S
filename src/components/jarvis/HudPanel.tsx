"use client";

import type * as React from "react";
import { cn } from "@/lib/utils";
import { HudCorners } from "./HudCorners";

/**
 * Panneau HUD translucide avec coins lumineux.
 * `title` rend un header `.hud-label` suivi d'un trait décoratif cyan.
 * Contenu avec padding par défaut (p-3) sauf si `noPad`.
 */
export function HudPanel({
  title,
  children,
  className,
  contentClassName,
  noPad,
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  noPad?: boolean;
}): React.JSX.Element {
  return (
    <section className={cn("hud-panel rounded-md", className)}>
      <HudCorners />
      {title ? (
        <header className="flex items-center gap-2 px-3 pt-2.5 pb-1.5">
          <h3 className="hud-label">{title}</h3>
          <span
            aria-hidden
            className="h-px min-w-6 flex-1 bg-gradient-to-r from-primary/55 to-transparent"
          />
        </header>
      ) : null}
      <div className={cn(noPad ? "" : "p-3", title ? "pt-1.5" : "", contentClassName)}>
        {children}
      </div>
    </section>
  );
}
