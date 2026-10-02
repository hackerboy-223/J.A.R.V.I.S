import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";

function copyIfExists(source, destination) {
  if (!existsSync(source)) {
    console.warn(`[postbuild] Skipped missing path: ${source}`);
    return;
  }

  mkdirSync(dirname(destination), { recursive: true });
  cpSync(source, destination, { recursive: true, force: true });
  console.log(`[postbuild] Copied ${source} -> ${destination}`);
}

const standaloneRoot = join(".next", "standalone");

if (!existsSync(standaloneRoot)) {
  console.warn("[postbuild] .next/standalone not found; nothing to copy.");
  process.exit(0);
}

copyIfExists(join(".next", "static"), join(standaloneRoot, ".next", "static"));
copyIfExists("public", join(standaloneRoot, "public"));
