import { defineConfig, devices } from "@playwright/test";

// Minimal patient smoke suite. Expects a backend on :8124 and serves the
// production frontend build on :3123. Run: npm run test:e2e (builds first).
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3123",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "python -m uvicorn backend.main:app --port 8124",
      cwd: "..",
      env: {
        DATABASE_PATH: "../backend/data/e2e-smoke.db",
        ALLOWED_ORIGINS: "http://127.0.0.1:3123,http://localhost:3123",
        // Deterministic interviewer path for UI assertions: no live LLM keys,
        // so Q&A flows through validator + deterministic fallback. Live-LLM
        // behavior is verified separately (backend stub tests + live script).
        GROQ_API_KEY: "",
        CEREBRAS_API_KEY: "",
        NVIDIA_NIM_API_KEY: "",
        OPENROUTER_API_KEY: "",
        GEMINI_API_KEY: "",
      },
      url: "http://127.0.0.1:8124/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run start -- --port 3123",
      env: { NEXT_PUBLIC_API_URL: "http://127.0.0.1:8124" },
      url: "http://127.0.0.1:3123/",
      reuseExistingServer: true,
      timeout: 90_000,
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
