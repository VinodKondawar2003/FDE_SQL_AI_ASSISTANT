import { useEffect } from "react";
import { Table2, X, KeyRound, ArrowRight, ShieldCheck } from "lucide-react";
import type { Catalog } from "./api";
export default function SchemaDrawer({
  catalog,
  close,
}: {
  catalog: Catalog | null;
  close: () => void;
}) {
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const panel = document.querySelector<HTMLElement>(".schema-panel");
    const items = () =>
      Array.from(
        panel?.querySelectorAll<HTMLElement>('button,summary,[tabindex="0"]') ??
          [],
      );
    items()[0]?.focus();
    function handle(e: KeyboardEvent) {
      if (e.key === "Escape") close();
      if (e.key === "Tab") {
        const a = items(),
          first = a[0],
          last = a.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", handle);
    return () => {
      document.removeEventListener("keydown", handle);
      previous?.focus();
    };
  }, []);
  return (
    <div className="modal-overlay" onClick={close}>
      <section
        className="schema-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="schema-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <div>
            <span className="eyebrow">YOUR DATABASE</span>
            <h2 id="schema-title">Commerce & people</h2>
            <p>Six connected tables. Synthetic data only.</p>
          </div>
          <button
            className="icon-button"
            aria-label="Close schema"
            onClick={close}
          >
            <X size={20} />
          </button>
        </header>
        <div className="schema-tables">
          {catalog &&
            Object.entries(catalog.tables).map(([name, columns]) => (
              <details key={name} open>
                <summary>
                  <Table2 size={15} />
                  {name}
                  <span>{columns.length} columns</span>
                </summary>
                {columns.map((c) => (
                  <div className="schema-column" key={c.name}>
                    <span>
                      {c.primary_key ? (
                        <KeyRound size={12} />
                      ) : (
                        <span className="column-dot" />
                      )}
                      {c.name}
                    </span>
                    <small>
                      {c.type}
                      {c.nullable ? " · nullable" : ""}
                    </small>
                  </div>
                ))}
              </details>
            ))}
          <h3>Relationships</h3>
          {catalog?.relationships.map((r, i) => (
            <p className="relationship" key={i}>
              {r.from_table}.{r.from_column}
              <ArrowRight size={12} />
              {r.to_table}.{r.to_column}
            </p>
          ))}
          <div className="notice">
            <ShieldCheck size={17} />
            Revenue uses historical item prices from paid and shipped orders.
            Currency: USD.
          </div>
        </div>
      </section>
    </div>
  );
}
