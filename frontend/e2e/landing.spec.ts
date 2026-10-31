import { expect, test } from "@playwright/test";

test.describe("landing page", () => {
  test("hero copy and calls to action point at real routes", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Aerospace Intelligence. Verified.");
    await expect(page.getByText("AEROSPACE REGULATORY INTELLIGENCE", { exact: true })).toBeVisible();
    await expect(page.getByText("Find, understand, and verify aviation regulatory information with evidence-backed AI.")).toBeVisible();
    const hero = page.locator("#top");
    await expect(hero.getByRole("link", { name: "Explore Directives" })).toHaveAttribute("href", "/directives");
    await expect(hero.getByRole("link", { name: "Open AI Search" })).toHaveAttribute("href", "/search");
    await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Launch Workspace" })).toHaveAttribute("href", "/dashboard");
  });

  test("sections, final CTA and footer disclaimer", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Everything you need to verify regulatory intelligence." })).toBeVisible();
    await expect(page.getByRole("heading", { name: "From complex documents to verifiable answers." })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Every answer, backed by evidence." })).toBeVisible();
    for (const t of ["Intelligent Document Search", "Configuration-Aware Analysis", "Source-Level Traceability", "Revision Intelligence"])
      await expect(page.getByText(t, { exact: true })).toBeVisible();
    for (const t of ["Ask", "Retrieve", "Analyse", "Verify"]) await expect(page.locator("#how-it-works").getByText(t, { exact: true }).first()).toBeVisible();
    const cta = page.getByRole("region", { name: "Regulatory clarity starts with reliable evidence." });
    await expect(cta.getByRole("link", { name: "Launch Regulatory Workspace" })).toHaveAttribute("href", "/search");
    await expect(cta.getByRole("link", { name: "Browse Directives" })).toHaveAttribute("href", "/directives");
    await expect(page.getByText("Decision-support prototype. Not a certified airworthiness or regulatory compliance determination.")).toBeVisible();
  });

  test("no approval language and no fabricated metrics", async ({ page }) => {
    await page.goto("/");
    const text = (await page.locator("body").innerText()).toLowerCase();
    expect(text).not.toMatch(/\bcompliant\b|\bapproved\b|legally safe/);
    expect(text).not.toMatch(/\d+(\.\d+)?\s?ms\b|\d+%/); // no latency or percentage claims on the marketing page
  });

  test("in-page navigation scrolls to sections", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "How It Works" }).click();
    await expect(page).toHaveURL(/#how-it-works$/);
    await expect(page.locator("#how-it-works")).toBeInViewport();
  });

  test("Launch Workspace opens the application", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Launch Workspace" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("navigation").first()).toBeVisible();
  });

  test("reduced motion renders the full headline immediately", async ({ browser }) => {
    const ctx = await browser.newContext({ reducedMotion: "reduce" });
    const page = await ctx.newPage();
    // record whether an Aurora (WebGL) canvas is ever inserted, even for a single render pass
    await page.addInitScript(() => {
      (window as unknown as { auroraSeen: boolean }).auroraSeen = false;
      new MutationObserver(() => {
        if (document.querySelector("canvas.absolute.inset-0.block")) (window as unknown as { auroraSeen: boolean }).auroraSeen = true;
      }).observe(document, { childList: true, subtree: true });
    });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Aerospace Intelligence. Verified.");
    await page.waitForLoadState("networkidle");
    // StarBorder keeps its own 2D canvas but renders it statically; the Aurora canvas must never mount
    expect(await page.evaluate(() => (window as unknown as { auroraSeen: boolean }).auroraSeen)).toBe(false);
    await ctx.close();
  });
});
