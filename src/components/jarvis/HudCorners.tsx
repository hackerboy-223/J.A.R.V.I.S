"use client";

import type * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Quatre coins lumineux positionnés en absolu dans le parent relatif.
 * Couleurs : cyan (défaut), or, rouge. Non interactif (aria-hidden).
 */
export function HudCorners({
  className,
  tone = "cyan",
}: {
  className?: string;
  tone?: "cyan" | "gold" | "red";
}): React.JSX.Element {
  const toneCls =
    tone === "gold" ? "hud-corner-gold" : tone === "red" ? "hud-corner-red" : "";
  return (
    <>
      <span aria-hidden className={cn("hud-corner-tl", toneCls, className)} />
      <span aria-hidden className={cn("hud-corner-tr", toneCls, className)} />
      <span aria-hidden className={cn("hud-corner-bl", toneCls, className)} />
      <span aria-hidden className={cn("hud-corner-br", toneCls, className)} />
    </>
  );
}
