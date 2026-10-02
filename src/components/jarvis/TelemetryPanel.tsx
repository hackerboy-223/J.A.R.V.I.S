"use client";

import * as React from "react";
import type { SystemStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { HudPanel } from "./HudPanel";
import { RadarSweep } from "./RadarSweep";

const timeFmt = new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const dateFmt = new Intl.DateTimeFormat("fr-FR", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

function formatUptime(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d} j ${h} h`;
  if (h > 0) return `${h} h ${m} min`;
  return `${m} min`;
}

const SHIMMER_STYLE: React.CSSProperties = {
  background:
    "linear-gradient(100deg, transparent 25%, rgba(255, 255, 255, 0.4) 50%, transparent 75%)",
  backgroundSize: "200% 100%",
};

function Meter({ label, pct }: { label: string; pct: number }): React.JSX.Element {
  const hot = pct > 80;
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className="hud-label">{label}</span>
        <span className={cn("font-mono text-[10px] tabular-nums", hot ? "text-gold" : "text-primary")}>
          {pct} % · {hot ? "ÉLEVÉ" : "NOMINAL"}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-primary/10">
        <div
          className={cn("relative h-full rounded-full", hot ? "bg-gold/85" : "bg-primary/85")}
          style={{ width: `${pct}%` }}
        >
          <span aria-hidden className="animate-shimmer absolute inset-0 rounded-full" style={SHIMMER_STYLE} />
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, active }: { label: string; value: string; active?: boolean }): React.JSX.Element {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="hud-label shrink-0">{label}</span>
      <span
        className={cn(
          "truncate font-mono text-[10px] font-medium",
          active ? "text-primary" : "text-foreground/80"
        )}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

export function TelemetryPanel({
  status,
  className,
}: {
  status: SystemStatus | null;
  className?: string;
}): React.JSX.Element {
  const [now, setNow] = React.useState<Date | null>(null);
  const [online, setOnline] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  React.useEffect(() => {
    const sync = () => setOnline(navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  const memPct = status ? Math.max(0, Math.min(100, Math.round(status.usedMemPct))) : 0;
  const cpuPct =
    status && status.cpuCount > 0
      ? Math.max(0, Math.min(100, Math.round((status.loadAvg[0] / status.cpuCount) * 100)))
      : 0;

  const dateStr = now ? dateFmt.format(now) : "—";
  const dateLabel = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);

  return (
    <div className={cn("flex w-[218px] shrink-0 flex-col gap-3 text-[11px]", className)}>
      <HudPanel title="NOYAU J.A.R.V.I.S.">
        <div className="space-y-2">
          <Row label="COGNITION" value="OPÉRATIONNEL" active />
          <Row label="INTERFACE HUD" value="ACTIVE" active />
          <Row label="TÉLÉMÉTRIE" value={status ? "SYNCHRONISÉE" : "ACQUISITION"} active={!!status} />
          <Row
            label="LIAISON RÉSEAU"
            value={online === null ? "ACQUISITION" : online ? "ÉTABLIE" : "HORS LIGNE"}
            active={online === true}
          />
        </div>
      </HudPanel>

      <HudPanel title="CHRONOMÉTRIE">
        <div className="flex flex-col items-center gap-0.5">
          <div className="glow-text font-mono text-xl tabular-nums text-primary">
            {now ? timeFmt.format(now) : "--:--:--"}
          </div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {dateLabel}
          </div>
        </div>
      </HudPanel>

      <HudPanel title="SYSTÈME HÔTE">
        {status ? (
          <div className="space-y-2.5">
            <Meter label="MÉMOIRE" pct={memPct} />
            <Meter label="CHARGE CPU" pct={cpuPct} />
            <Row label="UPTIME" value={formatUptime(status.osUptime)} />
            <Row label="HOST" value={status.hostname} />
            <Row label="PLATEFORME" value={`${status.platform} · ${status.arch}`} />
            <Row label="RUNTIME" value={status.nodeVersion} />
          </div>
        ) : (
          <div className="flex items-center gap-2 py-2">
            <span className="dot-pulse inline-block size-1.5 rounded-full bg-primary" />
            <span className="hud-label">ACQUISITION DES DONNÉES…</span>
          </div>
        )}
      </HudPanel>

      <HudPanel title="CAPTEURS LOGICIELS">
        <div className="flex flex-col items-center gap-2.5 py-1">
          <RadarSweep size={84} />
          <Row label="SCAN INTERFACE" value="ACTIF" active />
          <Row
            label="RÉSEAU"
            value={online === null ? "…" : online ? "EN LIGNE" : "HORS LIGNE"}
            active={online === true}
          />
        </div>
      </HudPanel>
    </div>
  );
}
