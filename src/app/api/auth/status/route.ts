import { NextRequest, NextResponse } from "next/server";
import {
  isAuthConfigured,
  isAuthRequired,
  isAuthorized,
} from "@/lib/server/auth";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  return NextResponse.json({
    required: isAuthRequired(),
    configured: isAuthConfigured(),
    authenticated: isAuthorized(req),
  });
}
