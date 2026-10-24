/**
 * Records a four-minute local demonstration against the real configured provider.
 * Run after the benchmark to avoid competing for provider quota.
 * No test adapter or mocked HTTP response is used.
 */
import { chromium, expect } from "@playwright/test";
import { spawn, execFileSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("../..", import.meta.url));
const output = join(root, "docs", "demo");
const origin = "http://localhost:8002";
const python = join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
await mkdir(join(output, "raw"), { recursive: true });
try {
  await fetch(origin + "/api/v1/health/live", { signal: AbortSignal.timeout(1500) });
  throw new Error("Port 8002 is occupied. Stop that server before recording.");
} catch (error) {
  if (error.message.includes("occupied")) throw error;
}
const server = spawn(python, [
  "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1",
  "--port", "8002", "--no-proxy-headers",
], {
  cwd: root, windowsHide: true, stdio: "ignore",
  env: { ...process.env, PUBLIC_ORIGIN: origin, SECURE_COOKIES: "false",
    STATE_DIR: join(root, ".runtime", "demo-" + Date.now()) },
});
let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      ready = (await fetch(origin + "/api/v1/health/ready")).ok;
      if (ready) break;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  if (!ready) throw new Error("The dedicated live demo server did not become ready.");
  browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    recordVideo: { dir: join(output, "raw"), size: { width: 1440, height: 960 } },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(55000);
  const video = page.video();
  const started = Date.now();
  const chapters = [];
  const note = text => {
    const seconds = (Date.now() - started) / 1000;
    chapters.push({ seconds, text });
    console.log(Math.floor(seconds) + "s: " + text);
  };
  const until = async seconds => {
    const remaining = seconds * 1000 - (Date.now() - started);
    if (remaining > 0) await page.waitForTimeout(remaining);
  };
  const send = async (message, status = "completed") => {
    await page.getByRole("textbox", { name: "Ask a question or paste a SQL query" }).fill(message);
    const responsePromise = page.waitForResponse(r =>
      r.url().endsWith("/messages") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Send message" }).click();
    const response = await responsePromise;
    const body = await response.json();
    if (!response.ok() || body.status !== status)
      throw new Error("Demo response failed: " + (body.error?.code ?? body.status));
    await expect(page.getByRole("textbox")).toBeEnabled();
    return body;
  };
  const sessionPromise = page.waitForResponse(r =>
    r.url().endsWith("/session") && r.request().method() === "POST");
  await page.goto(origin);
  const { model } = await (await sessionPromise).json();
  await expect(page.getByText("AI configured")).toBeVisible();
  note("Local Querycraft demo. Real Gemini model: " + model + ". Synthetic SQLite data.");
  await page.getByRole("button", { name: "Schema", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await until(20);
  await page.keyboard.press("Escape");
  await until(25);

  note("Natural-language generation, validated SQL, and a grounded explanation.");
  await send("Return customer_id and first_name for all customers.");
  await expect(page.getByRole("button", { name: "Copy SQL" })).toBeVisible();
  await until(42);
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("80 rows")).toBeVisible();
  await until(60);

  note("Follow-up keeps the selected columns and adds the California filter.");
  await send("Only those from California.");
  await expect(page.locator("pre")).toContainText("'CA'");
  await until(78);
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("40 rows")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "CSV", exact: true }).click();
  await downloadPromise;
  await until(95);

  note("Debugging an explicit SELECT typo returns a validated correction.");
  await send("Debug this SQL: SELEC customer_id FROM customers");
  await expect(page.locator("pre")).toContainText("customer_id");
  await until(120);

  note("Optimization removes an unused unique-parent join while preserving results.");
  const optimized = await send("Optimize this SQL: SELECT o.order_id FROM orders o JOIN customers c ON o.customer_id=c.customer_id");
  if (!optimized.optimization?.rewrite_applied) throw new Error("Expected proven join removal.");
  await page.locator("summary").click();
  await until(140);
  await page.getByRole("tab", { name: "Query plan" }).click();
  await expect(page.getByText("How SQLite reads your data")).toBeVisible();
  await until(155);

  note("Destructive SQL and unrelated questions are refused without a runnable query.");
  await send("DELETE FROM customers", "refused");
  await expect(page.getByRole("button", { name: "Copy SQL" })).toHaveCount(0);
  await until(168);
  await send("Who won FIFA?", "refused");
  await until(185);

  note("An ambiguous date asks for clarification before generating SQL.");
  await send("Employees hired after January 2024", "clarification_required");
  await until(200);
  await send("February 1 inclusive. Return employee_id only.");
  await expect(page.locator("pre")).toContainText("2024-02-01");
  await until(218);

  note("Refresh restores the conversation. Dark mode and history remain usable.");
  await page.reload();
  await expect(page.locator("pre")).toContainText("2024-02-01");
  await page.getByRole("button", { name: "Switch to dark mode" }).click();
  await page.screenshot({ path: join(output, "live-workspace.png"), fullPage: true });
  await until(230);
  note("React and FastAPI; checkpointed LangGraph; independent SQL validation. Public hosting is deferred.");
  await until(242);
  const duration = (Date.now() - started) / 1000;
  await context.close();
  await video.saveAs(join(output, "querycraft-local-demo.webm"));
  const stamp = seconds => {
    const ms = Math.round(seconds * 1000);
    return [Math.floor(ms / 3600000), Math.floor(ms / 60000) % 60, Math.floor(ms / 1000) % 60]
      .map(n => String(n).padStart(2, "0")).join(":") + "." + String(ms % 1000).padStart(3, "0");
  };
  const captions = chapters.map((c, i) =>
    stamp(c.seconds) + " --> " + stamp(chapters[i + 1]?.seconds ?? duration) + "\n" + c.text).join("\n\n");
  await writeFile(join(output, "captions.vtt"), "WEBVTT\n\n" + captions + "\n");
  await writeFile(join(output, "recording.json"), JSON.stringify({
    recorded_at: new Date().toISOString(), origin, model, duration_seconds: duration,
    provider: "real configured Gemini", chapters, all_scenarios_passed: true,
  }, null, 2));
  console.log("Verified local recording saved: docs/demo/querycraft-local-demo.webm");
} finally {
  if (browser) await browser.close();
  if (server.pid && server.exitCode === null) {
    if (process.platform === "win32") {
      try { execFileSync("taskkill", ["/PID", String(server.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" }); } catch {}
    } else {
      server.kill("SIGTERM");
    }
  }
}
