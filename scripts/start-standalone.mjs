import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const server = join(".next", "standalone", "server.js");

if (!existsSync(server)) {
  console.error("[JARVIS] Production server not found. Run: bun run build");
  process.exit(1);
}

const child = spawn(process.execPath, [server], {
  stdio: "inherit",
  env: {
    ...process.env,
    NODE_ENV: "production",
  },
});

child.on("exit", (code, signal) => {
  if (signal) {
    console.error(`[JARVIS] Server stopped by signal ${signal}`);
    process.exit(1);
  }
  process.exit(code ?? 0);
});

child.on("error", (error) => {
  console.error("[JARVIS] Unable to start production server:", error);
  process.exit(1);
});
