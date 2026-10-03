import { NextRequest, NextResponse } from "next/server";
import os from "node:os";
import { requireAuthorized } from "@/lib/server/auth";

export const runtime = "nodejs";

function envEnabled(name: string): boolean {
  return ["1", "true", "yes", "on"].includes(
    (process.env[name] ?? "").trim().toLowerCase()
  );
}

export async function GET(req: NextRequest) {
  const denied = requireAuthorized(req);
  if (denied) return denied;

  const isWindows = process.platform === "win32";

  return NextResponse.json(
    {
      host: {
        hostname: os.hostname(),
        platform: process.platform,
        arch: process.arch,
        nodeVersion: process.version,
      },
      capabilities: {
        systemStatus: true,
        voice: true,
        webSearch: true,
        pcControl: isWindows && envEnabled("JARVIS_ALLOW_PC_CONTROL"),
        runJs: envEnabled("JARVIS_ALLOW_RUN_JS"),
      },
      pcControl: {
        available: isWindows && envEnabled("JARVIS_ALLOW_PC_CONTROL"),
        reason: !isWindows
          ? "Le contrôle PC est disponible uniquement lorsque J.A.R.V.I.S. tourne sur Windows."
          : envEnabled("JARVIS_ALLOW_PC_CONTROL")
            ? null
            : "Active JARVIS_ALLOW_PC_CONTROL=true dans .env pour autoriser les actions locales non destructives.",
        allowedApps: ["calculator", "notepad", "explorer"],
        allowedFolders: ["desktop", "documents", "downloads", "project"],
        allowedProtocols: ["http", "https"],
      },
    },
    { headers: { "Cache-Control": "no-store" } }
  );
}
