import { NextResponse } from "next/server";
import os from "node:os";

export const dynamic = "force-dynamic";

/**
 * Sonde de santé du système J.A.R.V.I.S.
 * GET /api → statut, uptime et charge réels de la machine hôte.
 */
export async function GET() {
  const cpus = os.cpus();
  return NextResponse.json(
    {
      system: "J.A.R.V.I.S.",
      status: "online",
      host: os.hostname(),
      platform: `${os.type()} ${os.release()} (${os.arch()})`,
      cores: cpus.length,
      loadAvg: Number(os.loadavg()[0].toFixed(2)),
      memoryTotalMb: Math.round(os.totalmem() / 1048576),
      memoryFreeMb: Math.round(os.freemem() / 1048576),
      uptimeSec: Math.round(os.uptime()),
      timestamp: new Date().toISOString(),
    },
    { headers: { "cache-control": "no-store" } }
  );
}
