import { existsSync, readFileSync, writeFileSync } from "node:fs";

const envPath = ".env";
const databaseLine = 'DATABASE_URL="file:../db/custom.db"';

let current = "";
if (existsSync(envPath)) {
  current = readFileSync(envPath, "utf8");
}

if (!/^\s*DATABASE_URL\s*=/m.test(current)) {
  const prefix = current.trim().length > 0 ? current.trimEnd() + "\n\n" : "";
  writeFileSync(
    envPath,
    `${prefix}# Base de données SQLite locale J.A.R.V.I.S.\n${databaseLine}\n`,
    "utf8"
  );
  console.log("[JARVIS] DATABASE_URL SQLite local configuré dans .env");
} else {
  console.log("[JARVIS] DATABASE_URL déjà configuré.");
}
