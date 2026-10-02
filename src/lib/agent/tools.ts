import vm from "node:vm";
import os from "node:os";
import ZAI from "z-ai-web-dev-sdk";
import { AGENT_TOOLS, HUD_ACTIONS, type HudAction } from "@/lib/types";

export interface ToolContext {
  signal?: AbortSignal;
}

type ToolFn = (args: Record<string, unknown>, ctx: ToolContext) => Promise<unknown>;

// ---------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------

function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timeout : ${label} a dépassé ${ms / 1000}s`)), ms);
    p.then(
      (v) => {
        clearTimeout(timer);
        resolve(v);
      },
      (e) => {
        clearTimeout(timer);
        reject(e);
      }
    );
  });
}

function str(args: Record<string, unknown>, key: string): string {
  const v = args?.[key];
  if (typeof v !== "string" || !v.trim()) {
    throw new Error(`Argument "${key}" manquant ou invalide (chaîne attendue)`);
  }
  return v.trim();
}

async function getZai() {
  return ZAI.create();
}

// ---------------------------------------------------------------
// web_search
// ---------------------------------------------------------------

const webSearch: ToolFn = async (args) => {
  const query = str(args, "query");
  const num = Math.min(Math.max(Number(args.num) || 6, 1), 10);
  const zai = await getZai();
  const results = (await zai.functions.invoke("web_search", {
    query,
    num,
  })) as Array<{
    url?: string;
    name?: string;
    snippet?: string;
    host_name?: string;
    date?: string;
  }>;
  if (!Array.isArray(results)) return { results: [], note: "Aucun résultat" };
  return results.map((r) => ({
    url: r.url ?? "",
    name: r.name ?? "",
    snippet: r.snippet ?? "",
    host: r.host_name ?? "",
    date: r.date ?? "",
  }));
};

// ---------------------------------------------------------------
// read_page
// ---------------------------------------------------------------

function htmlToText(html: string): string {
  return html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<noscript[^>]*>[\s\S]*?<\/noscript>/gi, " ")
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|section|article|li|h[1-6]|tr)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/[ \t]+/g, " ")
    .replace(/\n\s*\n\s*\n+/g, "\n\n")
    .trim();
}

const readPage: ToolFn = async (args) => {
  const url = str(args, "url");
  if (!/^https?:\/\//i.test(url)) {
    throw new Error("L'URL doit commencer par http:// ou https://");
  }
  const zai = await getZai();
  const res = (await zai.functions.invoke("page_reader", { url })) as {
    data?: { title?: string; url?: string; html?: string; publishedTime?: string };
    title?: string;
    url?: string;
    html?: string;
    publishedTime?: string;
  };
  const data = res?.data ?? res ?? {};
  const text = htmlToText(data.html ?? "");
  return {
    title: data.title ?? "",
    url: data.url ?? url,
    publishedTime: data.publishedTime ?? null,
    text: text.length > 12000 ? text.slice(0, 12000) + "\n… [contenu tronqué]" : text,
  };
};

// ---------------------------------------------------------------
// calculator
// ---------------------------------------------------------------

const MATH_ALLOWED = new Set([
  "abs", "ceil", "floor", "round", "sqrt", "cbrt", "pow", "log", "log2", "log10", "exp",
  "sin", "cos", "tan", "atan", "asin", "acos", "min", "max", "sign", "trunc", "hypot",
  "PI", "E",
]);

const MATH_FN_ALIASES =
  "cbrt|ceil|floor|round|sqrt|hypot|log2|log10|log|exp|sign|trunc|atan|asin|acos|sin|cos|tan|min|max|abs|pow";

const calculator: ToolFn = async (args) => {
  const raw = str(args, "expression");
  if (raw.length > 500) throw new Error("Expression trop longue (500 caractères max)");

  let expr = raw.replace(/π/g, "PI").replace(/\^/g, "**");

  // Alias courts -> Math.*
  expr = expr.replace(/(?<![\w.])(PI|pi)(?![\w.])/g, "Math.PI");
  expr = expr.replace(new RegExp(`(?<![\\w.])(${MATH_FN_ALIASES})\\s*\\(`, "g"), "Math.$1(");

  // Vérifie que chaque Math.fn utilisé est autorisé
  const used = expr.match(/Math\.([A-Za-z0-9]+)/g) ?? [];
  for (const u of used) {
    if (!MATH_ALLOWED.has(u.slice(5))) {
      throw new Error(`Fonction non autorisée : ${u}`);
    }
  }

  // Après remplacement, seuls les caractères sûrs et Math.* sont permis
  const residual = expr.replace(/Math\.[A-Za-z0-9]+/g, "").replace(/\*\*/g, "*");
  if (!/^[\d+\-*/%().,\s]*$/.test(residual)) {
    throw new Error("L'expression contient des caractères ou identifiants non autorisés");
  }

  const fn = new Function(
    `"use strict"; const {${[...MATH_ALLOWED].join(",")}} = Math; return (${expr});`
  );
  const result = fn();
  if (typeof result !== "number" || !Number.isFinite(result)) {
    throw new Error("Le résultat n'est pas un nombre fini");
  }
  return { expression: raw, result };
};

// ---------------------------------------------------------------
// run_js — bac à sable node:vm
// ---------------------------------------------------------------

function fmtValue(v: unknown): string {
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v, null, 2) ?? String(v);
  } catch {
    return String(v);
  }
}

const runJs: ToolFn = async (args) => {
  const code = str(args, "code");
  if (code.length > 20000) throw new Error("Code trop long (20 000 caractères max)");
  const logs: string[] = [];
  const push = (...a: unknown[]) => {
    logs.push(a.map(fmtValue).join(" "));
    if (logs.length > 200) logs.length = 200;
  };
  const sandbox: Record<string, unknown> = {
    console: { log: push, info: push, warn: push, error: push, debug: push },
    Math,
    JSON,
    Date,
    Number,
    String,
    Boolean,
    Array,
    Object,
    Map,
    Set,
    Symbol,
    BigInt,
    Promise,
    RegExp,
    Error,
    parseInt,
    parseFloat,
    isNaN,
    isFinite,
    structuredClone,
    TextEncoder,
    TextDecoder,
  };
  sandbox.globalThis = sandbox;
  sandbox.console = sandbox.console;

  let result: unknown;
  try {
    result = vm.runInNewContext(`(async () => { "use strict";\n${code}\n})()`, sandbox, {
      timeout: 3000,
      filename: "agent-sandbox.js",
    });
    // si le code n'est pas async et que runInNewContext a renvoyé une promesse
    result = await Promise.race([
      result,
      new Promise((_, rej) => setTimeout(() => rej(new Error("Timeout : le code a dépassé 3s")), 4000)),
    ]);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    throw new Error(`Erreur d'exécution JS : ${message}`);
  }
  return {
    logs: logs.length ? logs : [],
    result: result === undefined ? null : fmtValue(result).slice(0, 8000),
  };
};

// ---------------------------------------------------------------
// get_datetime
// ---------------------------------------------------------------

const getDatetime: ToolFn = async () => {
  const now = new Date();
  const fmt = (tz: string) =>
    new Intl.DateTimeFormat("fr-FR", {
      timeZone: tz,
      dateStyle: "full",
      timeStyle: "short",
    }).format(now);
  return {
    iso: now.toISOString(),
    utc: now.toUTCString(),
    paris: fmt("Europe/Paris"),
    los_angeles: fmt("America/Los_Angeles"),
    epoch_ms: now.getTime(),
  };
};

// ---------------------------------------------------------------
// system_status — JARVIS surveille la machine hôte
// ---------------------------------------------------------------

const systemStatus: ToolFn = async () => {
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const load = os.loadavg();
  const cpus = os.cpus();
  return {
    hostname: os.hostname(),
    system: `${os.type()} ${os.release()} (${os.arch()})`,
    cpu: {
      model: cpus[0]?.model ?? "Inconnu",
      cores: cpus.length,
      load_average_1min: load[0],
      load_average_5min: load[1],
      load_average_15min: load[2],
    },
    memory: {
      total_gb: +(totalMem / 1024 ** 3).toFixed(2),
      free_gb: +(freeMem / 1024 ** 3).toFixed(2),
      used_percent: +(((totalMem - freeMem) / totalMem) * 100).toFixed(1),
    },
    uptime_os_hours: +(os.uptime() / 3600).toFixed(1),
    uptime_agent_process_minutes: +(process.uptime() / 60).toFixed(1),
    node: process.version,
  };
};

// ---------------------------------------------------------------
// hud_action — JARVIS agit sur l'interface holographique
// ---------------------------------------------------------------

const hudAction: ToolFn = async (args) => {
  const raw = args?.action;
  const action = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (!HUD_ACTIONS.includes(action as HudAction)) {
    throw new Error(
      `Action inconnue « ${action} ». Actions valides : ${HUD_ACTIONS.join(", ")}`
    );
  }
  // L'exécution réelle (animation) se produit côté client (interface holographique).
  // Côté serveur on confirme l'ordre transmis à l'HUD.
  const labels: Record<HudAction, string> = {
    scan: "Balayage holographique en cours…",
    alert: "Mode alerte engagé.",
    power_up: "Montée en puissance du réacteur.",
    celebrate: "Célébration holographique lancée.",
    ping: "Signal holographique émis.",
  };
  return { action: action as HudAction, status: "TRANSMIS À L'INTERFACE", detail: labels[action as HudAction] };
};

// ---------------------------------------------------------------
// Registre
// ---------------------------------------------------------------

export const TOOL_REGISTRY: Record<string, { fn: ToolFn; timeoutMs: number }> = {
  web_search: { fn: webSearch, timeoutMs: 30000 },
  read_page: { fn: readPage, timeoutMs: 35000 },
  calculator: { fn: calculator, timeoutMs: 5000 },
  run_js: { fn: runJs, timeoutMs: 8000 },
  get_datetime: { fn: getDatetime, timeoutMs: 3000 },
  system_status: { fn: systemStatus, timeoutMs: 3000 },
  hud_action: { fn: hudAction, timeoutMs: 2000 },
};

export function isKnownTool(name: string): boolean {
  return Object.prototype.hasOwnProperty.call(TOOL_REGISTRY, name);
}

export async function executeTool(
  name: string,
  args: Record<string, unknown>,
  ctx: ToolContext = {}
): Promise<{ ok: true; data: unknown } | { ok: false; error: string }> {
  const entry = TOOL_REGISTRY[name];
  if (!entry) {
    return { ok: false, error: `Outil inconnu : ${name}` };
  }
  try {
    const data = await withTimeout(
      entry.fn(args && typeof args === "object" ? args : {}, ctx),
      entry.timeoutMs,
      name
    );
    return { ok: true, data };
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error(`[tool:${name}]`, message);
    return { ok: false, error: message };
  }
}
