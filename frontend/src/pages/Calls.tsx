import { useEffect, useState } from "react";
import { CallLog, fetchCallLogs } from "../api";

function fmt(dt: string | null) {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("it-IT", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function duration(a: string | null, b: string | null) {
  if (!a || !b) return "—";
  const secs = Math.max(0, (new Date(b).getTime() - new Date(a).getTime()) / 1000);
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return `${m}m ${s}s`;
}

export default function Calls() {
  const [items, setItems] = useState<CallLog[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      fetchCallLogs()
        .then((data) => alive && setItems(data))
        .catch((e) => alive && setError(String(e)));
    };
    load();
    const id = setInterval(load, 10000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <section>
      <div className="page-head">
        <h1>Chiamate</h1>
        <span className="hint">Log dei report end-of-call ricevuti da Vapi</span>
      </div>
      {error && <div className="err">Errore: {error}</div>}
      {!items ? (
        <p className="muted">Caricamento…</p>
      ) : items.length === 0 ? (
        <p className="muted">
          Nessuna chiamata ancora registrata. Configura il webhook in Vapi per ricevere i report.
        </p>
      ) : (
        <ul className="calls">
          {items.map((c) => {
            const open = openId === c.call_id;
            return (
              <li key={c.call_id} className={open ? "open" : ""}>
                <header onClick={() => setOpenId(open ? null : c.call_id)}>
                  <code>{c.call_id.slice(0, 8)}…</code>
                  <span>{fmt(c.started_at)}</span>
                  <span className="dur">{duration(c.started_at, c.ended_at)}</span>
                  <span className="reason">{c.ended_reason ?? "—"}</span>
                </header>
                {open && (
                  <div className="call-body">
                    {c.summary && (
                      <>
                        <h4>Riassunto</h4>
                        <p>{c.summary}</p>
                      </>
                    )}
                    {c.transcript && (
                      <>
                        <h4>Trascrizione</h4>
                        <pre>{c.transcript}</pre>
                      </>
                    )}
                    {c.recording_url && (
                      <>
                        <h4>Registrazione</h4>
                        <audio controls src={c.recording_url} />
                      </>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
