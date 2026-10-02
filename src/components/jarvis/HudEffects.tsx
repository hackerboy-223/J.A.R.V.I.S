"use client";

import * as React from "react";
import type { HudAction } from "@/lib/types";

/**
 * Overlays temporaires plein écran déclenchés par l'agent
 * (outil hud_action) : scan, alert, power_up, celebrate, ping.
 *
 * L'overlay se monte quand `action` change d'objet et se démonte
 * après la durée de l'effet. Les positions des particules sont
 * générées de façon déterministe à partir de `action.id`
 * (aucun Math.random au rendu → pas de mismatch d'hydratation).
 */

const DURATION_MS: Record<HudAction, number> = {
  scan: 1600,
  alert: 2000,
  power_up: 1300,
  celebrate: 1900,
  ping: 1600,
};

const PARTICLE_COUNT = 18;

/** Pseudo-aléatoire déterministe (seed = id de l'action). */
function prand(seed: number, salt: number): number {
  const x = Math.sin(seed * 127.1 + salt * 311.7) * 43758.5453123;
  return x - Math.floor(x);
}

function Ripple({ delay }: { delay: number }): React.JSX.Element {
  return (
    <div
      className="animate-ripple absolute top-1/2 left-1/2 size-24 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 opacity-0"
      style={{
        animationDelay: `${delay}ms`,
        borderColor: "color-mix(in oklch, var(--primary) 75%, transparent)",
        boxShadow: "0 0 20px 3px color-mix(in oklch, var(--primary) 30%, transparent)",
      }}
    />
  );
}

function CelebrateParticles({ seed }: { seed: number }): React.JSX.Element {
  return (
    <>
      {Array.from({ length: PARTICLE_COUNT }, (_, i) => {
        const rLeft = prand(seed, i);
        const rSize = prand(seed, i + 40);
        const rDelay = prand(seed, i + 80);
        const rDur = prand(seed, i + 120);
        const rDrift = prand(seed, i + 160);
        const rRise = prand(seed, i + 200);
        const px = 3 + Math.round(rSize * 1.5); // 3 à 4 px
        return (
          <span
            key={i}
            aria-hidden
            className="animate-rise-particle absolute bottom-0 rounded-full opacity-0"
            style={
              {
                left: `${4 + rLeft * 92}%`,
                width: px,
                height: px,
                backgroundColor:
                  i % 4 === 0 ? "color-mix(in oklch, var(--gold) 55%, white)" : "var(--gold)",
                boxShadow: "0 0 8px 1px color-mix(in oklch, var(--gold) 55%, transparent)",
                animationDelay: `${(rDelay * 0.35).toFixed(2)}s`,
                animationDuration: `${(1 + rDur * 0.55).toFixed(2)}s`,
                "--rise-x": `${Math.round((rDrift - 0.5) * 90)}px`,
                "--rise-y": `-${Math.round(52 + rRise * 40)}vh`,
              } as React.CSSProperties
            }
          />
        );
      })}
    </>
  );
}

export function HudEffects({
  action,
}: {
  action: { id: number; type: HudAction } | null;
}): React.JSX.Element | null {
  const [shown, setShown] = React.useState<{ id: number; type: HudAction } | null>(null);

  React.useEffect(() => {
    if (!action) return;
    setShown(action);
    const t = window.setTimeout(() => setShown(null), DURATION_MS[action.type]);
    return () => window.clearTimeout(t);
  }, [action]);

  if (!shown) return null;

  return (
    <div
      key={shown.id}
      role="presentation"
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[80] overflow-hidden"
    >
      {shown.type === "scan" ? (
        <>
          {/* Voile cyan pendant le scan */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(to bottom, transparent 0%, color-mix(in oklch, var(--primary) 7%, transparent) 30%, color-mix(in oklch, var(--primary) 4%, transparent) 100%)",
            }}
          />
          {/* Ligne de scan descendante */}
          <div
            className="animate-scanline-move absolute inset-x-0 top-0 h-[2px] opacity-0"
            style={{
              background:
                "linear-gradient(90deg, transparent, color-mix(in oklch, var(--primary) 95%, white) 45%, color-mix(in oklch, var(--primary) 95%, white) 55%, transparent)",
              boxShadow:
                "0 0 14px 3px color-mix(in oklch, var(--primary) 70%, transparent), 0 0 48px 10px color-mix(in oklch, var(--primary) 30%, transparent)",
            }}
          />
        </>
      ) : null}

      {shown.type === "alert" ? (
        <div
          className="animate-alert-flash absolute inset-0 opacity-0"
          style={{
            border: "2px solid color-mix(in oklch, var(--destructive) 80%, transparent)",
            boxShadow:
              "inset 0 0 90px 14px color-mix(in oklch, var(--destructive) 32%, transparent), inset 0 0 260px 46px color-mix(in oklch, var(--destructive) 13%, transparent)",
          }}
        />
      ) : null}

      {shown.type === "power_up" ? (
        <div
          className="animate-power-flash absolute inset-0 opacity-0"
          style={{
            background:
              "radial-gradient(circle at 50% 45%, color-mix(in oklch, var(--primary) 85%, white) 0%, color-mix(in oklch, var(--primary) 40%, transparent) 32%, transparent 65%)",
          }}
        />
      ) : null}

      {shown.type === "celebrate" ? <CelebrateParticles seed={shown.id} /> : null}

      {shown.type === "ping" ? (
        <>
          <Ripple delay={0} />
          <Ripple delay={230} />
        </>
      ) : null}
    </div>
  );
}
