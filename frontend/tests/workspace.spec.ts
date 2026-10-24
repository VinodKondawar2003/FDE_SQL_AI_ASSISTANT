import { test, expect } from "@playwright/test";
test("query, execute, follow up, refuse, export and restore", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your data, in plain English." }),
  ).toBeVisible();
  await expect(page.getByText("AI configured")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("workspace.png"),
    fullPage: true,
  });
  await page
    .getByRole("textbox", { name: "Ask a question or paste a SQL query" })
    .fill("Show all customers");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("button", { name: "Copy SQL" })).toBeVisible();
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "customer1@example.test", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("80 rows")).toBeVisible();
  const exported = page.waitForEvent("download");
  await page.getByRole("button", { name: "CSV", exact: true }).click();
  expect((await exported).suggestedFilename()).toBe("results.csv");
  await page.getByRole("textbox").fill("Only California");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("pre")).toContainText("'CA'");
  await page.screenshot({
    path: testInfo.outputPath("query.png"),
    fullPage: true,
  });
  await page.reload();
  await expect(page.locator("pre")).toContainText("'CA'");
  await page.getByRole("textbox").fill("Who won FIFA?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("Keeping your workspace focused")).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy SQL" })).toHaveCount(0);
  await page.getByRole("button", { name: "Switch to dark mode" }).click();
  await expect(page.locator("html")).toHaveClass("dark");
  await page.getByRole("button", { name: "Schema", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("mobile layout and navigation", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Send message" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(
    page.getByRole("button", { name: "New conversation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close navigation" }).click();
  await page.screenshot({
    path: testInfo.outputPath("mobile.png"),
    fullPage: true,
  });
  await page.getByRole("textbox").fill("Show all customers");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("button", { name: "Copy SQL" })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
