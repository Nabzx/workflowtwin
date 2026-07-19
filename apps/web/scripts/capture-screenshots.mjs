import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

import { chromium } from "playwright";

const baseURL = process.env.WORKFLOWTWIN_SCREENSHOT_URL ?? "http://127.0.0.1:5182";
const output = resolve(process.cwd(), "../../docs/assets/screenshots");
const views = [
  ["overview", "/"],
  ["workflow", "/workflow"],
  ["evidence", "/evidence"],
  ["opportunity", "/opportunity"],
  ["simulation", "/simulation"],
  ["pilot-recommendation", "/pilot"],
  ["audit-and-gates", "/audit"],
];

await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
});

for (const [name, path] of views) {
  await page.goto(`${baseURL}${path}`, { waitUntil: "networkidle", timeout: 90_000 });
  await page.locator("h1").waitFor({ timeout: 30_000 });
  await page.screenshot({ path: resolve(output, `${name}.jpg`), type: "jpeg", quality: 84 });
}

await page.goto(`${baseURL}/pilot`, { waitUntil: "networkidle", timeout: 90_000 });
await page.getByRole("button", { name: "Edit draft" }).click();
await page.getByLabel("Heading").waitFor();
await page.screenshot({ path: resolve(output, "draft-review.jpg"), type: "jpeg", quality: 84 });

await browser.close();
