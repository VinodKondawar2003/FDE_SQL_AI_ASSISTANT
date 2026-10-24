import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUp,
  Check,
  CheckCheck,
  ChevronDown,
  Code2,
  Database,
  History,
  LoaderCircle,
  Menu,
  MessageSquare,
  Moon,
  Plus,
  ShieldCheck,
  Sparkles,
  Sun,
  Table2,
  Trash2,
  X,
  AlertCircle,
  Waypoints,
} from "lucide-react";
import {
  api,
  ApiError,
  setCsrf,
  type Catalog,
  type Conversation,
  type Page,
  type Session,
  type Turn,
  type TurnResponse,
} from "./api";
import OutputPanel from "./OutputPanel";
import SchemaDrawer from "./SchemaDrawer";
const examples = [
  {
    icon: Table2,
    title: "Explore your customers",
    detail: "Find customers in California",
    prompt: "Show all customers from California.",
  },
  {
    icon: Waypoints,
    title: "Understand revenue",
    detail: "See which products bring in revenue",
    prompt: "Show the top 5 products by paid and shipped order revenue in USD.",
  },
  {
    icon: Code2,
    title: "Make your SQL better",
    detail: "Debug, explain, and optimize queries",
    prompt: "Explain how to join customers and orders using this database.",
  },
];
const modes = [
  ["auto", "Auto detect"],
  ["generate", "Generate SQL"],
  ["debug", "Debug SQL"],
  ["optimize", "Optimize SQL"],
  ["explain", "Explain SQL"],
];
type Retry = { cid: string; request_id: string; message: string; mode: string };
const err = (e: unknown) =>
  e instanceof Error ? e.message : "Something went wrong. Please try again.";
export default function App() {
  const [session, setSession] = useState<Session | null>(null),
    [catalog, setCatalog] = useState<Catalog | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]),
    [conversationCursor, setConversationCursor] = useState<number | null>(null);
  const [cid, setCid] = useState<string | null>(null),
    [turns, setTurns] = useState<Turn[]>([]),
    [turnCursor, setTurnCursor] = useState<number | null>(null);
  const [selected, setSelected] = useState<string | null>(null),
    [draft, setDraft] = useState(""),
    [mode, setMode] = useState("auto");
  const [working, setWorking] = useState(false),
    [executing, setExecuting] = useState(false),
    [pendingText, setPendingText] = useState("");
  const [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [drawer, setDrawer] = useState(false),
    [sidebar, setSidebar] = useState(false);
  const [dark, setDark] = useState(
      () => localStorage.getItem("querycraft-theme") === "dark",
    ),
    [retry, setRetry] = useState<Retry | null>(null);
  const composer = useRef<HTMLTextAreaElement>(null),
    scrollEnd = useRef<HTMLDivElement>(null),
    loadSerial = useRef(0);
  const response = turns.find((t) => t.id === selected)?.response ?? null,
    busy = working || executing;
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("querycraft-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    let stopped = false;
    (async () => {
      try {
        const s = await api<Session>("/session", "POST");
        if (stopped) return;
        setCsrf(s.csrf_token);
        setSession(s);
        const [list, schema] = await Promise.all([
          api<Page<Conversation>>("/conversations"),
          api<Catalog>("/schema"),
        ]);
        if (stopped) return;
        setConversations(list.items);
        setConversationCursor(list.next_cursor);
        setCatalog(schema);
        const saved = localStorage.getItem("querycraft-conversation");
        if (saved) {
          try {
            await loadConversation(saved);
          } catch {
            localStorage.removeItem("querycraft-conversation");
          }
        }
      } catch (e) {
        if (!stopped) setError(err(e));
      }
    })();
    return () => {
      stopped = true;
    };
  }, []);
  useEffect(() => {
    scrollEnd.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [turns.length, working]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 2500);
    return () => clearTimeout(t);
  }, [toast]);
  async function refreshList() {
    const list = await api<Page<Conversation>>("/conversations");
    setConversations(list.items);
    setConversationCursor(list.next_cursor);
  }
  async function loadConversation(id: string) {
    const serial = ++loadSerial.current,
      data = await api<Conversation & { turns: Page<Turn> }>(
        "/conversations/" + id,
      );
    if (serial !== loadSerial.current) return;
    setCid(id);
    setTurns(data.turns.items);
    setTurnCursor(data.turns.next_cursor);
    setSelected(data.turns.items.at(-1)?.id ?? null);
    setSidebar(false);
    setRetry(null);
    localStorage.setItem("querycraft-conversation", id);
  }
  function newConversation() {
    ++loadSerial.current;
    setCid(null);
    setTurns([]);
    setSelected(null);
    setTurnCursor(null);
    setDraft("");
    setError("");
    setRetry(null);
    setSidebar(false);
    localStorage.removeItem("querycraft-conversation");
    composer.current?.focus();
  }
  async function send(text = draft, retrying = false) {
    if (working || !text.trim() || !session) return;
    setWorking(true);
    setError("");
    setPendingText(text);
    setDraft("");
    setSelected(null);
    let id = cid,
      request = retrying && retry ? retry : null;
    try {
      if (!id) {
        const created = await api<Conversation>("/conversations", "POST", {});
        id = created.id;
        setCid(id);
        localStorage.setItem("querycraft-conversation", id);
      }
      request = request ?? {
        cid: id,
        request_id: crypto.randomUUID(),
        message: text,
        mode,
      };
      setRetry(request);
      await api<TurnResponse>("/conversations/" + id + "/messages", "POST", {
        request_id: request.request_id,
        message: request.message,
        mode: request.mode,
      });
      await loadConversation(id);
      setRetry(null);
      await refreshList();
    } catch (e) {
      setError(err(e));
      if (e instanceof ApiError && e.body.turn_id && id) {
        await loadConversation(id).catch(() => {});
        await refreshList().catch(() => {});
        setRetry(null);
        setDraft(text);
      } else if (e instanceof ApiError && e.status === 401) setRetry(null);
      else if (request) setRetry(request);
    } finally {
      setWorking(false);
      setPendingText("");
      composer.current?.focus();
    }
  }
  async function removeConversation(id: string) {
    if (!window.confirm("Delete this conversation and its saved results?"))
      return;
    try {
      await api("/conversations/" + id, "DELETE");
      if (cid === id) newConversation();
      await refreshList();
    } catch (e) {
      setError(err(e));
    }
  }
  async function older() {
    if (!cid || turnCursor === null) return;
    try {
      const data = await api<{ turns: Page<Turn> }>(
        "/conversations/" + cid + "?cursor=" + turnCursor,
      );
      setTurns((t) => [...data.turns.items, ...t]);
      setTurnCursor(data.turns.next_cursor);
    } catch (e) {
      setError(err(e));
    }
  }
  return (
    <div className="app-shell">
      {sidebar && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setSidebar(false)}
        />
      )}
      <aside className={"sidebar " + (sidebar ? "is-open" : "")}>
        <a
          className="brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            if (!busy) newConversation();
          }}
        >
          <span className="brand-mark">
            <Database size={20} />
          </span>
          querycraft<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <button className="new-chat" onClick={newConversation} disabled={busy}>
          <Plus size={17} />
          New conversation<span>↵</span>
        </button>
        <div className="history-title">
          <History size={14} />
          Recent conversations
        </div>
        <nav className="history-list" aria-label="Conversation history">
          {conversations.length === 0 && (
            <div className="history-empty">
              A little curiosity goes a long way.
              <br />
              Your conversations will live here.
            </div>
          )}
          {conversations.map((c) => (
            <div
              key={c.id}
              className={"history-item " + (cid === c.id ? "active" : "")}
            >
              <button
                disabled={busy}
                title={c.title}
                onClick={() =>
                  loadConversation(c.id).catch((e) => setError(err(e)))
                }
              >
                <MessageSquare size={15} />
                <span>{c.title}</span>
              </button>
              <button
                className="delete-chat"
                disabled={busy}
                aria-label={"Delete " + c.title}
                onClick={() => removeConversation(c.id)}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
          {conversationCursor !== null && (
            <button
              className="text-button"
              onClick={async () => {
                try {
                  const list = await api<Page<Conversation>>(
                    "/conversations?cursor=" + conversationCursor,
                  );
                  setConversations((c) => [...c, ...list.items]);
                  setConversationCursor(list.next_cursor);
                } catch (e) {
                  setError(err(e));
                }
              }}
            >
              Load more
            </button>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="database-card">
            <span className="database-icon">
              <Database size={17} />
            </span>
            <div>
              <strong>Commerce & people</strong>
              <small>
                <i className="status-dot" />
                SQLite · Synthetic sample
              </small>
            </div>
            <span className="db-version">v1</span>
          </div>
          <button className="schema-link" onClick={() => setDrawer(true)}>
            <Table2 size={15} />
            Explore database schema
            <ArrowRight size={14} />
          </button>
          <div className="sidebar-footer">
            <span className="avatar">Q</span>
            <div>
              <strong>Demo workspace</strong>
              <small>Private conversation history</small>
            </div>
            <button
              className="icon-button"
              aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
              onClick={() => setDark((v) => !v)}
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
          </div>
        </div>
      </aside>
      <main className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setSidebar(true)}
            >
              <Menu size={19} />
            </button>
            <span>Workspace</span>
            <span className="slash">/</span>
            <strong>SQL assistant</strong>
          </div>
          <div className="topbar-actions">
            <span className="safe-badge">
              <ShieldCheck size={13} />
              Read-only by design
            </span>
            <button
              className="button subtle small"
              onClick={() => setDrawer(true)}
            >
              <Database size={14} />
              Schema
            </button>
          </div>
        </header>
        <div className="workspace">
          <section className="chat-column" aria-label="SQL conversation">
            <div className="section-heading">
              <div>
                <span className="section-icon">
                  <Sparkles size={15} />
                </span>
                <strong>Ask your data</strong>
              </div>
              <span className="live-label">
                <i
                  className={
                    "status-dot " +
                    (!session?.model_configured ? "muted-dot" : "")
                  }
                />
                {session?.model_configured ? "AI configured" : "Connecting"}
              </span>
            </div>
            {!session?.model_configured && session && (
              <div className="notice">
                <AlertCircle size={16} />
                <span>
                  The AI connection needs configuration. The schema is available
                  to explore.
                </span>
              </div>
            )}
            <div className="chat-scroll">
              {turns.length === 0 && !working ? (
                <div className="welcome">
                  <div className="eyebrow">
                    <span />A CLEARER WAY TO QUERY
                  </div>
                  <h1>
                    Your data,
                    <br />
                    <span>in plain English.</span>
                  </h1>
                  <p>
                    Ask a question. Get SQL you can understand.
                    <br />
                    Explore your database, one conversation at a time.
                  </p>
                  <div className="example-cards">
                    {examples.map(({ icon: Icon, ...item }) => (
                      <button
                        className="example-card"
                        key={item.title}
                        disabled={!session || busy}
                        onClick={() => send(item.prompt)}
                      >
                        <span className="example-icon">
                          <Icon size={19} />
                        </span>
                        <span>
                          <strong>{item.title}</strong>
                          <small>{item.detail}</small>
                        </span>
                        <ArrowRight size={16} />
                      </button>
                    ))}
                  </div>
                  <div className="welcome-footnote">
                    <ShieldCheck size={14} />
                    Every query is checked before it reaches you.
                  </div>
                </div>
              ) : (
                <div className="messages">
                  {turnCursor !== null && (
                    <button className="text-button" onClick={older}>
                      Load earlier messages
                    </button>
                  )}
                  {turns.map((turn) => (
                    <article className="turn" key={turn.id}>
                      <div className="user-message">
                        <span className="message-avatar user">Y</span>
                        <div>
                          <span className="message-label">You</span>
                          <p>{turn.message}</p>
                        </div>
                      </div>
                      {turn.response && (
                        <div
                          className={
                            "assistant-message " +
                            (selected === turn.id ? "selected" : "")
                          }
                        >
                          <span className="message-avatar assistant">
                            <Sparkles size={15} />
                          </span>
                          <div className="message-body">
                            <span className="message-label">
                              Querycraft
                              <span>
                                {turn.response.status === "completed"
                                  ? "Ready"
                                  : turn.response.status.replaceAll("_", " ")}
                              </span>
                            </span>
                            <p>
                              {turn.response.explanation?.summary ??
                                turn.response.message}
                            </p>
                            {turn.response.sql && (
                              <button
                                className="query-card"
                                onClick={() => setSelected(turn.id)}
                                disabled={busy}
                              >
                                <Code2 size={16} />
                                <span>Validated SQLite query</span>
                                <CheckCheck size={15} />
                                <ArrowRight size={14} />
                              </button>
                            )}
                            {turn.response.clarification && (
                              <div className="clarification-choices">
                                {turn.response.clarification.choices
                                  .filter(Boolean)
                                  .map((choice) => (
                                    <button
                                      className="choice"
                                      key={choice}
                                      disabled={busy}
                                      onClick={() => send(choice)}
                                    >
                                      {choice}
                                    </button>
                                  ))}
                              </div>
                            )}
                            {turn.response.diagnostics.map((d, i) => (
                              <p className="diagnostic" key={i}>
                                {d.message}
                              </p>
                            ))}
                          </div>
                        </div>
                      )}
                    </article>
                  ))}
                  {working && (
                    <>
                      <div className="user-message pending">
                        <span className="message-avatar user">Y</span>
                        <div>
                          <span className="message-label">You</span>
                          <p>{pendingText}</p>
                        </div>
                      </div>
                      <div className="thinking" role="status">
                        <LoaderCircle className="spin" size={17} />
                        Preparing your SQL response…
                      </div>
                    </>
                  )}
                  <div ref={scrollEnd} />
                </div>
              )}
            </div>
            <div className="composer-area">
              {error && (
                <div className="error-banner" role="alert">
                  <AlertCircle size={17} />
                  <span>{error}</span>
                  <button
                    className="icon-button"
                    aria-label="Dismiss error"
                    onClick={() => setError("")}
                  >
                    <X size={15} />
                  </button>
                </div>
              )}
              {retry && !working && (
                <button
                  className="text-button retry"
                  onClick={() => send(retry.message, true)}
                >
                  Retry interrupted request
                </button>
              )}
              <form
                className="composer"
                onSubmit={(e) => {
                  e.preventDefault();
                  send();
                }}
              >
                <label className="sr-only" htmlFor="question">
                  Ask a question or paste a SQL query
                </label>
                <textarea
                  id="question"
                  ref={composer}
                  value={draft}
                  maxLength={8000}
                  disabled={busy}
                  placeholder="Ask a question or paste a SQL query…"
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (
                      e.key === "Enter" &&
                      !e.shiftKey &&
                      !e.nativeEvent.isComposing
                    ) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <div className="composer-toolbar">
                  <label className="mode-select">
                    <Sparkles size={13} />
                    <span className="sr-only">Query mode</span>
                    <select
                      aria-label="Query mode"
                      value={mode}
                      onChange={(e) => setMode(e.target.value)}
                      disabled={busy}
                    >
                      {modes.map(([value, label]) => (
                        <option value={value} key={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={12} />
                  </label>
                  <span className="keyboard-hint">
                    Shift + Enter for a new line
                  </span>
                  <button
                    className="send-button"
                    type="submit"
                    aria-label="Send message"
                    disabled={busy || !draft.trim() || !session}
                  >
                    {working ? (
                      <LoaderCircle className="spin" size={17} />
                    ) : (
                      <ArrowUp size={19} />
                    )}
                  </button>
                </div>
              </form>
              <div className="composer-note">
                Focused on your schema. Always read-only.{" "}
                <span>AI can make mistakes—review your query.</span>
              </div>
            </div>
          </section>
          <OutputPanel
            key={selected ?? "empty"}
            response={response}
            busy={busy}
            onError={setError}
            onToast={setToast}
            onBusy={setExecuting}
          />
        </div>
      </main>
      {toast && (
        <div className="toast" role="status">
          <Check size={15} />
          {toast}
        </div>
      )}
      {drawer && (
        <SchemaDrawer catalog={catalog} close={() => setDrawer(false)} />
      )}
    </div>
  );
}
