import { NextRequest, NextResponse } from "next/server";
import os from "node:os";
import type { SystemStatus } from "@/lib/types";
import { requireAuthorized } from "@/lib/server/auth";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const denied = requireAuthorized(req);
  if (denied) return denied;
  try {
    const totalMem = os.totalmem();
    const freeMem = os.freemem();
    const load = os.loadavg();

    const status: SystemStatus = {
      hostname: os.hostname(),
      platform: `${os.type()} ${os.release()}`,
      arch: os.arch(),
      cpuModel: os.cpus()[0]?.model ?? "Inconnu",
      cpuCount: os.cpus().length,
      loadAvg: [load[0], load[1], load[2]],
      totalMem,
      freeMem,
      usedMemPct: Math.min(100, Math.max(0, ((totalMem - freeMem) / totalMem) * 100)),
      osUptime: os.uptime(),
      processUptime: Math.round(process.uptime()),
      nodeVersion: process.version,
      processMemRss: process.memoryUsage().rss,
      timestamp: new Date().toISOString(),
    };

    return NextResponse.json(status, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : "Erreur inattendue";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
