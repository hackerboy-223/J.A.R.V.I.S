import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "jarvis_session";

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (
    pathname === "/login" ||
    pathname === "/api" ||
    pathname.startsWith("/api/auth/")
  ) {
    return NextResponse.next();
  }

  const authRequired =
    process.env.NODE_ENV === "production" ||
    Boolean(process.env.JARVIS_ACCESS_PASSWORD?.trim());

  if (!authRequired) return NextResponse.next();

  const configured =
    (process.env.JARVIS_ACCESS_PASSWORD?.trim().length ?? 0) >= 12 &&
    (process.env.JARVIS_SESSION_SECRET?.trim().length ?? 0) >= 32;

  if (!configured) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        { error: "Authentification J.A.R.V.I.S. non configurée côté serveur." },
        { status: 503 }
      );
    }
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("misconfigured", "1");
    return NextResponse.redirect(url);
  }

  if (!req.cookies.has(SESSION_COOKIE)) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Authentification requise" }, { status: 401 });
    }
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
