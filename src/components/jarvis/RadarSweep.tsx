"use client";

import type * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Radar de surveillance : anneaux concentriques, croix fine,
 * balayage conique en rotation (4 s) et blips clignotants.
 */
export function RadarSweep({
  size = 96,
  className,
}: {
  size?: number;
  className?: string;
}): React.JSX.Element {
  const blip = Math.max(3, Math.round(size * 0.035));
  return (
    <div
      role="img"
      aria-label="Radar de surveillance"
      className={cn("relative shrink-0", className)}
      style={{ width: size, height: size }}
    >
      {/* Anneaux concentriques */}
      <div aria-hidden className="absolute inset-0 rounded-full border border-primary/25" />
      <div aria-hidden className="absolute rounded-full border border-primary/20" style={{ inset: size * 0.2 }} />
      <div aria-hidden className="absolute rounded-full border border-primary/15" style={{ inset: size * 0.4 }} />

      {/* Croix fine */}
      <div aria-hidden className="absolute top-0 bottom-0 left-1/2 w-px -translate-x-1/2 bg-primary/15" />
      <div aria-hidden className="absolute top-1/2 right-0 left-0 h-px -translate-y-1/2 bg-primary/15" />

      {/* Balayage rotatif */}
      <div aria-hidden className="absolute inset-0 overflow-hidden rounded-full">
        <div
          className="animate-jarvis-spin absolute inset-0"
          style={{
            animationDuration: "4s",
            background:
              "conic-gradient(from 0deg, color-mix(in oklch, var(--primary) 50%, transparent) 0deg, color-mix(in oklch, var(--primary) 14%, transparent) 45deg, transparent 95deg, transparent 360deg)",
          }}
        />
      </div>

      {/* Blips */}
      <span
        aria-hidden
        className="animate-blip absolute rounded-full bg-primary shadow-[0_0_6px_var(--primary)]"
        style={{ width: blip, height: blip, left: "30%", top: "42%", animationDelay: "0.2s" }}
      />
      <span
        aria-hidden
        className="animate-blip absolute rounded-full bg-primary shadow-[0_0_6px_var(--primary)]"
        style={{ width: blip, height: blip, left: "63%", top: "26%", animationDelay: "0.9s" }}
      />
      <span
        aria-hidden
        className="animate-blip absolute rounded-full bg-primary shadow-[0_0_6px_var(--primary)]"
        style={{ width: blip, height: blip, left: "57%", top: "66%", animationDelay: "1.5s" }}
      />
    </div>
  );
}
