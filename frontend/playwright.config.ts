import { defineConfig } from "@playwright/test";

// The browser tests run against the recorded demo, so they need no model key
// and give the same result every time.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5191",
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: 2,
  },
  webServer: [
    {
      command: "uv run uvicorn claimcheck.api:app_factory --factory --host 127.0.0.1 --port 8791",
      cwd: "../backend",
      env: { CLAIMCHECK_MODE: "replay" },
      url: "http://127.0.0.1:8791/api/health",
      reuseExistingServer: true,
    },
    {
      command: "bun run dev",
      url: "http://127.0.0.1:5191",
      reuseExistingServer: true,
    },
  ],
});
