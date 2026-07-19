import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // The prepared demo intentionally shares one in-memory workflow state.
  // Serial execution prevents one scenario's reset from interrupting another.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5182",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "laptop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 820, height: 1180 }, hasTouch: true } },
  ],
  webServer: [
    {
      command: "UV_CACHE_DIR=/tmp/workflowtwin-uv-cache uv --directory ../.. run workflowtwin serve --host 127.0.0.1 --port 8012",
      url: "http://127.0.0.1:8012/ready",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "VITE_PROXY_TARGET=http://127.0.0.1:8012 npm run dev -- --port 5182",
      url: "http://127.0.0.1:5182",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
