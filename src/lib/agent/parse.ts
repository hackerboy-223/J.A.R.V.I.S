import { isKnownTool } from "./tools";

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
}

/**
 * Extrait un appel d'outil `{"tool": "...", "args": {...}}` depuis le texte du modèle.
 * Tolérant aux blocs ```json, aux variantes "name"/"arguments" et au JSON imbriqué.
 */
export function extractToolCall(text: string): ToolCall | null {
  const direct = text.match(/\{\s*"tool"\s*:/);
  const alt = text.match(/\{\s*"name"\s*:\s*"[a-z_]+"\s*,\s*"(args|arguments|parameters)"/);
  const match = direct ?? alt;
  if (!match || match.index === undefined) return null;
  return parseJsonBlock(text, match.index);
}

function parseJsonBlock(text: string, start: number): ToolCall | null {
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (escape) {
      escape = false;
      continue;
    }
    if (ch === "\\") {
      escape = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        try {
          const obj = JSON.parse(text.slice(start, i + 1)) as Record<string, unknown>;
          const tool =
            typeof obj.tool === "string"
              ? obj.tool
              : typeof obj.name === "string"
                ? obj.name
                : null;
          if (!tool) return null;
          const rawArgs =
            obj.args && typeof obj.args === "object" && !Array.isArray(obj.args)
              ? obj.args
              : obj.arguments && typeof obj.arguments === "object"
                ? obj.arguments
                : obj.parameters && typeof obj.parameters === "object"
                  ? obj.parameters
                  : {};
          return { tool, args: rawArgs as Record<string, unknown> };
        } catch {
          return null;
        }
      }
    }
  }
  return null;
}

export function isValidToolCall(tc: ToolCall | null): boolean {
  return !!tc && isKnownTool(tc.tool);
}

/**
 * Heuristique de streaming : ce buffer pourrait-il être le début d'un appel d'outil ?
 * Si oui, on retient les tokens jusqu'à la fin du stream avant de les émettre.
 */
export function looksLikeToolCallStart(buffer: string): boolean {
  const t = buffer.trimStart();
  if (t.startsWith("{")) return true;
  const m = t.match(/^```([a-zA-Z]*)/);
  if (!m) return false;
  const lang = m[1].toLowerCase();
  if (!"json".startsWith(lang)) return false; // ```ts, ```py … → réponse code classique
  const rest = t.slice(m[0].length);
  return rest.trim() === "" || rest.trimStart().startsWith("{");
}
