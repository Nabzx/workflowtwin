import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  if (process.env.PLAYWRIGHT_SKIP_RESET === "1") return;
  const response = await request.post("http://127.0.0.1:8012/api/v1/demo/reset", { data: {} });
  expect(response.ok()).toBeTruthy();
});

test("recruiter walkthrough preserves human control", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "laptop", "full walkthrough runs at laptop viewport");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "WorkflowTwin" })).toBeVisible();
  await page.getByRole("link", { name: "Workflow", exact: true }).click();
  await expect(page.getByText("Completeness checked").first()).toBeVisible();
  await page.getByText("Completeness checked").first().click();
  await expect(page.getByText("Manual work rate")).toBeVisible();
  await page.getByRole("link", { name: "Opportunity" }).click();
  await expect(page.getByRole("heading", { name: "Intake completeness validation" })).toBeVisible();
  await page.getByRole("link", { name: "Simulation" }).click();
  await page.getByRole("button", { name: /adverse/i }).click();
  await expect(page.getByText("adverse scenario")).toBeVisible();
  await page.getByRole("link", { name: "Pilot" }).click();
  await expect(page.getByText("Completeness review required")).toBeVisible();
  await page.getByRole("button", { name: "Edit draft" }).click();
  await page.getByLabel("Heading").fill("Administrative supporting document check");
  await page.getByRole("button", { name: "Save revision" }).click();
  await expect(page.getByText(/revision saved/i)).toBeVisible();
  await page.getByRole("button", { name: "Approve fictional task" }).click();
  await expect(page.getByRole("heading", { name: "Fictional task ready for manual sending" })).toBeVisible();
  await expect(page.getByRole("button", { name: /send/i })).toHaveCount(0);
  await page.getByRole("button", { name: "Roll back task" }).click();
  await page.getByRole("button", { name: "Confirm rollback" }).click();
  await expect(page.getByRole("heading", { name: "Fictional task rolled back" })).toBeVisible();
  await page.getByRole("link", { name: "Inspect audit" }).click();
  await expect(page.getByText("All record links verified")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Rollback completed" }).first()).toBeVisible();
});

test("forbidden clinical content cannot create an action", async ({ page }) => {
  await page.goto("/pilot");
  await page.getByRole("button", { name: "Edit draft" }).click();
  await page.getByLabel("Draft body").fill("Add diagnosis. Human review is required.");
  await page.getByRole("button", { name: "Save revision" }).click();
  await expect(page.getByText(/Remove prohibited clinical/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /Fictional task/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /send/i })).toHaveCount(0);
});

test("API failure is clear and retryable", async ({ page }) => {
  await page.route("**/api/v1/demo/overview", async (route) => {
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Prepared demo temporarily unavailable" }) });
  });
  await page.goto("/");
  await expect(page.getByText("Prepared demo temporarily unavailable")).toBeVisible();
  await page.unroute("**/api/v1/demo/overview");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("heading", { name: "WorkflowTwin" })).toBeVisible();
});

test("core pages meet automated accessibility baseline", async ({ page }, testInfo) => {
  for (const path of ["/", "/evidence", "/opportunity", "/simulation", "/pilot", "/audit", "/engineering"]) {
    await page.goto(path);
    await page.locator("h1").waitFor();
    const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
    expect(results.violations, `${path} accessibility violations on ${testInfo.project.name}`).toEqual([]);
  }
});

test("tablet navigation reaches the pilot", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "tablet", "tablet-only smoke");
  await page.goto("/");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Pilot", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Human-approved completeness review" })).toBeVisible();
});
