import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Sonde de santé publique minimale.
 * Les diagnostics détaillés restent derrière /api/system-status et nécessitent
 * une session J.A.R.V.I.S. valide.
 */
export async function GET() {
  return NextResponse.json(
    {
      system: "J.A.R.V.I.S.",
      status: "online",
      timestamp: new Date().toISOString(),
    },
    { headers: { "cache-control": "no-store" } }
  );
}
