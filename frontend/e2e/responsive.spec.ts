import { expect, test } from "@playwright/test";

const ROUTES = ["/", "/dashboard", "/search", "/directives", "/applicability", "/evaluation"];
const WIDTHS = [1440, 1280, 1024, 768, 390];

test.describe("responsive layout", () => {
  for (const width of WIDTHS) {
    test(`no horizontal overflow at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      for (const route of ROUTES) {
        await page.goto(route);
        await page.waitForLoadState("networkidle");
        const { sw, cw } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
        expect(sw, `${route} at ${width}px`).toBeLessThanOrEqual(cw);
      }
    });
  }

  test("keyboard focus is visible on the landing page", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    const outline = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return "none";
      const s = getComputedStyle(el);
      return s.outlineStyle !== "none" && s.outlineWidth !== "0px" ? "outline" : s.boxShadow !== "none" ? "ring" : "none";
    });
    expect(outline).not.toBe("none");
  });
});
