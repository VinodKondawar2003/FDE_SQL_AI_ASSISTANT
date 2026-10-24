import { useState } from "react";
import {
  Check,
  Code2,
  Copy,
  ArrowDownToLine,
  Play,
  ShieldCheck,
  Table2,
  Waypoints,
  Sparkles,
  LoaderCircle,
  Terminal,
  PanelRight,
} from "lucide-react";
import hljs from "highlight.js/lib/core";
import sqlLanguage from "highlight.js/lib/languages/sql";
import {
  api,
  download,
  type TurnResponse,
  type Result,
  type Plan,
} from "./api";
hljs.registerLanguage("sql", sqlLanguage);
export default function OutputPanel({
  response,
  busy,
  onError,
  onToast,
  onBusy,
}: {
  response: TurnResponse | null;
  busy: boolean;
  onError: (s: string) => void;
  onToast: (s: string) => void;
  onBusy: (v: boolean) => void;
}) {
  const [tab, setTab] = useState<"sql" | "results" | "plan">("sql");
  const [result, setResult] = useState<Result | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [executing, setExecuting] = useState(false);
  const query = response?.sql ?? null;
  async function run() {
    if (!query) return;
    setExecuting(true);
    onBusy(true);
    setTab("results");
    try {
      setResult(
        await api<Result>(
          "/queries/" + query.artifact_id + "/execute",
          "POST",
          { request_id: crypto.randomUUID() },
        ),
      );
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setExecuting(false);
      onBusy(false);
    }
  }
  async function showPlan() {
    setTab("plan");
    if (!query || plan) return;
    setExecuting(true);
    onBusy(true);
    try {
      setPlan(await api<Plan>("/queries/" + query.artifact_id + "/plan"));
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setExecuting(false);
      onBusy(false);
    }
  }
  async function copy() {
    if (!query) return;
    try {
      await navigator.clipboard.writeText(query.text);
      onToast("SQL copied to clipboard");
    } catch {
      onError("Clipboard unavailable. Select and copy the SQL.");
    }
  }
  async function save(path: string, name: string) {
    try {
      await download(path, name);
    } catch (e) {
      onError((e as Error).message);
    }
  }
  return (
    <aside className="output-column" aria-label="Query workspace">
      <div className="section-heading">
        <div>
          <span className="section-icon">
            <Terminal size={15} />
          </span>
          <strong>Query workspace</strong>
        </div>
        <PanelRight size={16} className="muted" />
      </div>
      <div
        className="output-tabs"
        role="tablist"
        aria-label="Query output"
        onKeyDown={(e) => {
          if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
            e.preventDefault();
            const tabs = ["sql", "results", "plan"] as const;
            const next =
              tabs[(tabs.indexOf(tab) + (e.key === "ArrowRight" ? 1 : 2)) % 3];
            if (next === "plan") showPlan();
            else setTab(next);
            document.getElementById("tab-" + next)?.focus();
          }
        }}
      >
        {(["sql", "results", "plan"] as const).map((t) => (
          <button
            id={"tab-" + t}
            role="tab"
            aria-selected={tab === t}
            aria-controls={"panel-" + t}
            tabIndex={tab === t ? 0 : -1}
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => (t === "plan" ? showPlan() : setTab(t))}
          >
            {t === "sql" ? (
              <Code2 size={14} />
            ) : t === "results" ? (
              <Table2 size={14} />
            ) : (
              <Waypoints size={14} />
            )}{" "}
            {t === "sql"
              ? "SQL & explanation"
              : t === "results"
                ? "Results"
                : "Query plan"}
            {t === "results" && result && (
              <span className="count">{result.returned_row_count}</span>
            )}
          </button>
        ))}
      </div>
      <div
        className="output-scroll"
        role="tabpanel"
        id={"panel-" + tab}
        aria-labelledby={"tab-" + tab}
      >
        {tab === "sql" &&
          (query ? (
            <div className="sql-content">
              <div className="query-toolbar">
                <span className="validated">
                  <Check size={13} />
                  Validated
                </span>
                <span className="dialect-label">SQLite</span>
                <button
                  className="icon-button"
                  aria-label="Copy SQL"
                  onClick={copy}
                >
                  <Copy size={15} />
                </button>
                <button
                  className="icon-button"
                  aria-label="Download SQL"
                  onClick={() =>
                    save(
                      "/queries/" + query.artifact_id + "/download",
                      "query.sql",
                    )
                  }
                >
                  <ArrowDownToLine size={15} />
                </button>
              </div>
              <div className="code-wrap">
                <div className="code-gutter" aria-hidden="true">
                  {query.text.split("\n").map((_, i) => (
                    <div key={i}>{i + 1}</div>
                  ))}
                </div>
                <pre>
                  <code
                    dangerouslySetInnerHTML={{
                      __html: hljs.highlight(query.text, { language: "sql" })
                        .value,
                    }}
                  />
                </pre>
              </div>
              <div className="run-bar">
                <span>
                  <ShieldCheck size={13} />
                  Schema checked · Read-only
                </span>
                <button
                  className="button primary small"
                  disabled={busy || executing}
                  onClick={run}
                >
                  <Play size={13} />
                  Run query
                </button>
              </div>
              {response?.explanation && (
                <div className="explanation">
                  <h2>
                    <Sparkles size={15} />
                    What this query does
                  </h2>
                  <p>{response.explanation.summary}</p>
                  {response.explanation.steps.length > 0 && (
                    <ol>
                      {response.explanation.steps.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ol>
                  )}
                  {response.explanation.assumptions.length > 0 && (
                    <div className="assumptions">
                      <h3>Assumptions</h3>
                      {response.explanation.assumptions.map((s, i) => (
                        <p key={i}>{s}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {response?.optimization && (
                <details className="optimization">
                  <summary>Readability & performance notes</summary>
                  {[
                    ...response.optimization.changes,
                    ...response.optimization.suggestions,
                    ...response.optimization.index_recommendations,
                  ].map((s, i) => (
                    <p key={i}>{s}</p>
                  ))}
                </details>
              )}
            </div>
          ) : (
            <div className="output-empty">
              <div className="empty-art">
                <div className="empty-code-line" />
                <div className="empty-code-line short" />
                <div className="empty-code-line medium" />
                <span>
                  <Code2 size={24} />
                </span>
              </div>
              <h2>
                {response?.status === "refused"
                  ? "Keeping your workspace focused"
                  : "A question is all it takes"}
              </h2>
              <p>
                {response?.status === "refused"
                  ? "Ask about read-only SQL or the sample database."
                  : "Your validated SQL and a clear explanation will appear here."}
              </p>
              <div className="empty-tags">
                <span>
                  <Check size={12} />
                  Schema-aware
                </span>
                <span>
                  <ShieldCheck size={12} />
                  Read-only
                </span>
              </div>
            </div>
          ))}
        {tab === "results" &&
          (executing ? (
            <div className="output-empty" role="status">
              <LoaderCircle className="spin" size={23} />
              <h2>Running your query</h2>
            </div>
          ) : result ? (
            <div className="results">
              <div className="result-summary">
                <span>
                  <strong>{result.returned_row_count}</strong> rows ·{" "}
                  {result.duration_ms} ms
                </span>
                <button
                  className="button subtle small"
                  onClick={() =>
                    save(
                      "/executions/" + result.execution_id + "/download",
                      "results.csv",
                    )
                  }
                >
                  <ArrowDownToLine size={14} />
                  CSV
                </button>
              </div>
              {result.truncated && (
                <div className="notice">
                  Showing the first {result.limit} rows. CSV contains this same
                  bounded result.
                </div>
              )}
              {result.rows.length === 0 ? (
                <div className="empty-result">
                  No rows match this query. Try a broader filter.
                </div>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        {result.columns.map((c, i) => (
                          <th key={i}>
                            {c.name}
                            <small>{c.type}</small>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.map((row, i) => (
                        <tr key={i}>
                          {row.map((value, j) => (
                            <td key={j}>
                              {value === null ? (
                                <span className="null">NULL</span>
                              ) : (
                                String(value)
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="result-note">
                Synthetic data · Export expires in one hour
              </p>
            </div>
          ) : (
            <div className="output-empty">
              <Table2 size={28} />
              <h2>See the answer in your data</h2>
              <p>Run a validated query to view its results.</p>
              <button
                className="button primary"
                disabled={!query || busy}
                onClick={run}
              >
                <Play size={14} />
                Run query
              </button>
            </div>
          ))}
        {tab === "plan" &&
          (executing ? (
            <div className="output-empty" role="status">
              <LoaderCircle className="spin" size={23} />
              <h2>Reading the query plan</h2>
            </div>
          ) : plan ? (
            <div className="plan">
              <h2>How SQLite reads your data</h2>
              {plan.steps.map((s, i) => (
                <div className="plan-step" key={i}>
                  <span>{i + 1}</span>
                  <code>{s.detail}</code>
                </div>
              ))}
              {plan.observations.map((o, i) => (
                <p className="result-note" key={i}>
                  {o}
                </p>
              ))}
            </div>
          ) : (
            <div className="output-empty">
              <Waypoints size={29} />
              <h2>A look under the hood</h2>
              <p>Generate a query to inspect its SQLite access plan.</p>
            </div>
          ))}
      </div>
      <div className="output-footer">
        <span className="status-dot" />
        <span>6 tables in your workspace</span>
        <span className="output-footer-right">SQLite</span>
      </div>
    </aside>
  );
}
