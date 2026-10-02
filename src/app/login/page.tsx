"use client";

import * as React from "react";
import { LockKeyhole, Loader2, ShieldCheck } from "lucide-react";

type Status = {
  required: boolean;
  configured: boolean;
  authenticated: boolean;
};

export default function LoginPage() {
  const [password, setPassword] = React.useState("");
  const [status, setStatus] = React.useState<Status | null>(null);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    void fetch("/api/auth/status", { cache: "no-store" })
      .then((res) => res.json())
      .then((data: Status) => {
        setStatus(data);
        if (data.authenticated || !data.required) window.location.replace("/");
      })
      .catch(() => setError("Impossible de vérifier l'état de sécurité."));
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!password || loading) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = (await res.json()) as { error?: string };
      if (!res.ok) throw new Error(data.error || "Connexion refusée");
      window.location.replace("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connexion impossible");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-5 text-foreground">
      <div className="w-full max-w-md rounded-2xl border border-primary/20 bg-card/90 p-6 shadow-2xl backdrop-blur-xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-full border border-primary/40 bg-primary/10 text-primary">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              Accès sécurisé
            </p>
            <h1 className="text-xl font-semibold">J.A.R.V.I.S.</h1>
          </div>
        </div>

        {status && !status.configured ? (
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm">
            <p className="font-semibold">Configuration serveur requise</p>
            <p className="mt-2 text-muted-foreground">
              Définis <code>JARVIS_ACCESS_PASSWORD</code> et un
              <code className="ml-1">JARVIS_SESSION_SECRET</code> d'au moins 24 caractères,
              puis redémarre l'application.
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-sm text-muted-foreground">
                Mot de passe d'accès
              </span>
              <div className="flex items-center gap-2 rounded-xl border bg-background/70 px-3">
                <LockKeyhole className="h-4 w-4 text-muted-foreground" />
                <input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="h-12 w-full bg-transparent outline-none"
                  placeholder="••••••••••••"
                />
              </div>
            </label>

            {error ? (
              <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={loading || !password}
              className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 font-semibold text-primary-foreground transition-opacity disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              Autoriser l'accès
            </button>
          </form>
        )}

        <p className="mt-5 text-xs leading-relaxed text-muted-foreground">
          La session est conservée dans un cookie HttpOnly signé : le mot de passe n'est
          jamais stocké dans le navigateur.
        </p>
      </div>
    </main>
  );
}
