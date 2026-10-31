import { expect, test } from "@playwright/test";

// Runs against the real API (http://127.0.0.1:8000) and the real indexed corpus.
const API = "http://127.0.0.1:8000";

test.describe("application", () => {
  test("sidebar reaches every application route", async ({ page }) => {
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation").first();
    for (const [label, path, heading] of [
      ["AI Search", "/search", "Regulatory Intelligence Workspace"],
      ["Directives", "/directives", "Directives"],
      ["Applicability", "/applicability", "Applicability Checker"],
      ["Evaluation", "/evaluation", /Evaluation/],
      ["Dashboard", "/dashboard", "Dashboard"],
    ] as const) {
      await nav.getByRole("link", { name: label }).click();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      await expect(page.getByRole("heading", { level: 1 })).toContainText(heading);
    }
  });

  test("dashboard corpus numbers come from /health", async ({ page, request }) => {
    const h = await (await request.get(`${API}/health`)).json();
    await page.goto("/dashboard");
    const corpus = page.getByRole("region", { name: "Corpus" });
    await expect(corpus).toContainText(String(h.db.documents_by_source.organiser_sheet));
    await expect(corpus).toContainText(String(h.db.pages));
  });

  test("AI search answers with separate stage and applicability, and opens the cited source", async ({ page }) => {
    await page.goto("/search?q=" + encodeURIComponent("Does this proposed AD apply to my airplane?") +
      "&directive=FAA-2022-0222&model=PA-34-200&serial=34-7250001");
    await expect(page.getByTestId("status-strip")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("thinking-dots")).toHaveCount(0);
    await expect(page.getByTestId("cell-stage")).toContainText("Proposed rule");
    await expect(page.getByTestId("status-strip")).toContainText("Applicable under the proposed rule");
    await expect(page.getByTestId("cell-enforceability")).toBeVisible();
    await page.getByRole("button", { name: "View in source document" }).first().click();
    const viewer = page.getByRole("complementary", { name: "Document viewer" });
    await expect(viewer).toBeVisible();
    await expect(viewer.getByTestId("page-nav")).toBeVisible();
    // either the quote was located and highlighted, or the explicit unavailable notice is shown - never a silent guess
    await expect(viewer.getByText(/Quote located and highlighted|Exact highlight unavailable|could not be located/).first()).toBeVisible({ timeout: 30_000 });
  });

  test("viewer header describes the cited document, not the answer's directive", async ({ page }) => {
    await page.goto("/search?q=" + encodeURIComponent("Does this proposed AD apply to my airplane?") +
      "&directive=FAA-2022-0222&model=PA-34-200&serial=34-7250001");
    const finalCite = page.getByRole("region", { name: "Citations" }).getByRole("listitem").filter({ hasText: "FR Doc. 2022-08852" }).first();
    await finalCite.getByRole("button", { name: "View in source document" }).click({ timeout: 30_000 });
    const viewer = page.getByRole("complementary", { name: "Document viewer" });
    await expect(viewer.getByTestId("stage-pill")).toContainText("Final rule");
    await expect(viewer.getByTestId("stage-pill")).not.toContainText("Proposed");
    await expect(viewer).not.toContainText("Docket FAA-2022-0222");
  });

  test("refusals and metadata-only records are explicit", async ({ page }) => {
    await page.goto("/search?q=" + encodeURIComponent("Which AD is the most dangerous?"));
    await expect(page.getByText(/ABSTAINED/i).first()).toBeVisible({ timeout: 30_000 });
    await page.goto("/search?q=" + encodeURIComponent("What does this directive require?") + "&directive=NPRM-409");
    await expect(page.getByTestId("source-unavailable")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("stage-pill")).toHaveCount(0);
  });

  test("directive explorer search and row navigation", async ({ page }) => {
    await page.goto("/directives");
    await page.getByPlaceholder(/Search/).fill("NPRM-180");
    const row = page.getByRole("row").filter({ hasText: "NPRM-180" });
    await expect(row).toHaveCount(1, { timeout: 15_000 });
    await row.click();
    await expect(page).toHaveURL(/\/directives\/2021-13482$/);
  });

  test("applicability checker uses the API label and never green", async ({ page }) => {
    await page.goto("/applicability");
    await page.getByLabel("Directive ID (required)").fill("FAA-2022-0222");
    await page.getByLabel("Aircraft model").fill("PA-34-200");
    await page.getByLabel("Serial number").fill("34-7250001");
    await page.getByRole("button", { name: "Check applicability" }).click();
    const result = page.getByTestId("applicability-result");
    await expect(result).toContainText("Applicable under the proposed rule", { timeout: 30_000 });
    expect(await result.locator("[class*='green-'], [class*='emerald-']").count()).toBe(0);
    await expect(result.getByTestId("status-strip")).toBeVisible();
    await expect(result.getByTestId("cell-enforceability")).toBeVisible();
    await page.getByLabel("Serial number").fill("");
    await page.getByLabel("Aircraft model").fill("");
    await page.getByRole("button", { name: "Check applicability" }).click();
    await expect(result).toBeVisible({ timeout: 30_000 });
  });

  test("evaluation shows measured values only", async ({ page, request }) => {
    const runs = await (await request.get(`${API}/evaluation/runs`)).json();
    const withF2 = runs.filter((r: { split: string; metrics: Record<string, unknown> }) => r.split === "dev" && r.metrics.F2);
    const last = withF2[withF2.length - 1].metrics.F2.doc_recall_at5 as number;
    await page.goto("/evaluation");
    const card = page.getByTestId("metric-card").filter({ hasText: "Recall@5" });
    await expect(card).toContainText(last.toFixed(2).replace(/0$/, "").replace(/\.$/, ""));
    await expect(page.getByTestId("line-chart")).toBeVisible();
    await expect(page.getByTestId("metric-card").filter({ hasText: /Applicability accuracy/i })).toContainText("Not measured");
  });
});
