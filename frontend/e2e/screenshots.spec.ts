import { expect, test } from "@playwright/test";

// Documentation screenshots of the real app with real data. Opt-in: SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts --project=desktop
// Also refreshes public/landing/workspace.png, the landing page's product preview (a real capture, never a mock).
test.skip(!process.env.SCREENSHOTS, "set SCREENSHOTS=1 to capture screenshots");
test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
test.describe.configure({ mode: "serial" });

const OUT = "../docs/screenshots";
const DEMO = "/search?q=" + encodeURIComponent("Does this proposed AD apply to my airplane?") + "&directive=FAA-2022-0222&model=PA-34-200&serial=34-7250001";

test("workspace with answer and source viewer", async ({ page }) => {
  await page.goto(DEMO);
  await expect(page.getByTestId("status-strip")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "View in source document" }).first().click();
  await expect(page.getByRole("complementary", { name: "Document viewer" }).getByText(/Quote located|Exact highlight unavailable|could not be located/).first()).toBeVisible({ timeout: 30_000 });
  // the citation click scrolls the answer column; reset it (but not the viewer, which is scrolled to the highlight)
  await page.evaluate(() => document.querySelectorAll<HTMLElement>("*").forEach((el) => {
    if (el.scrollTop > 0 && !el.closest('aside[aria-label="Document viewer"]')) el.scrollTop = 0;
  }));
  await page.waitForTimeout(1500); // let pdf.js finish painting the page canvas
  await page.screenshot({ path: `${OUT}/app_search_workspace.png` });
  await page.screenshot({ path: "public/landing/workspace.png" });
});

test("landing", async ({ page }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: `${OUT}/landing_full.png`, fullPage: true });
  await page.screenshot({ path: `${OUT}/landing_hero.png` });
});

for (const [name, path, ready] of [
  ["app_dashboard", "/dashboard", "Corpus"],
  ["app_directives", "/directives", "row"],
  ["app_evaluation", "/evaluation", "line-chart"],
] as const) {
  test(name, async ({ page }) => {
    await page.goto(path);
    if (ready === "row") await expect(page.getByRole("row").nth(2)).toBeVisible();
    else if (ready === "line-chart") await expect(page.getByTestId("line-chart")).toBeVisible();
    else await expect(page.getByRole("region", { name: ready })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${OUT}/${name}.png` });
  });
}

test("applicability", async ({ page }) => {
  await page.goto("/applicability");
  await page.getByLabel("Directive ID (required)").fill("FAA-2022-0222");
  await page.getByLabel("Aircraft model").fill("PA-34-200");
  await page.getByLabel("Serial number").fill("34-7250001");
  await page.getByRole("button", { name: "Check applicability" }).click();
  await expect(page.getByTestId("applicability-result")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(400); // let the submit button finish its colour transition
  await page.screenshot({ path: `${OUT}/app_applicability.png` });
});

test("mobile landing and search", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto("/");
  await page.screenshot({ path: `${OUT}/mobile_landing.png` });
  await page.goto(DEMO);
  await expect(page.getByTestId("status-strip")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/mobile_search.png` });
  await ctx.close();
});
