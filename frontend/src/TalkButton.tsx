import { useEffect, useRef, useState } from "react";
import Vapi from "@vapi-ai/web";

type CallState = "idle" | "connecting" | "live" | "error";
type Role = "user" | "assistant";
type Turn = { role: Role; text: string; id: number };

const PUBLIC_KEY = import.meta.env.VITE_VAPI_PUBLIC_KEY as string | undefined;
const ASSISTANT_ID = import.meta.env.VITE_VAPI_ASSISTANT_ID as string | undefined;

export default function TalkButton() {
  const [state, setState] = useState<CallState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [assistantTalking, setAssistantTalking] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [partial, setPartial] = useState<{ role: Role; text: string } | null>(null);
  const [volume, setVolume] = useState(0);
  const vapiRef = useRef<Vapi | null>(null);
  const turnsEndRef = useRef<HTMLDivElement | null>(null);
  const nextIdRef = useRef(0);

  useEffect(() => {
    if (!PUBLIC_KEY) return;
    const v = new Vapi(PUBLIC_KEY);
    vapiRef.current = v;

    v.on("call-start", () => setState("live"));
    v.on("call-end", () => {
      setState("idle");
      setAssistantTalking(false);
      setVolume(0);
      setPartial(null);
    });
    v.on("speech-start", () => setAssistantTalking(true));
    v.on("speech-end", () => setAssistantTalking(false));
    v.on("volume-level", (lvl: number) => setVolume(lvl));

    v.on("message", (msg: any) => {
      if (msg?.type !== "transcript") return;
      const role = msg.role as Role;
      const text = String(msg.transcript || "").trim();
      if (!text) return;
      if (msg.transcriptType === "final") {
        setTurns((prev) => [...prev, { role, text, id: nextIdRef.current++ }]);
        setPartial(null);
      } else {
        setPartial({ role, text });
      }
    });

    v.on("error", (e: any) => {
      const m = e?.message ?? (typeof e === "string" ? e : "errore sconosciuto");
      setError(m);
      setState("error");
    });

    return () => {
      try {
        v.stop();
      } catch {
        /* ignore */
      }
    };
  }, []);

  useEffect(() => {
    turnsEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, partial]);

  if (!PUBLIC_KEY || !ASSISTANT_ID) return null;

  const start = async () => {
    setError(null);
    setTurns([]);
    setPartial(null);
    setState("connecting");
    try {
      await vapiRef.current!.start(ASSISTANT_ID!);
    } catch (e: any) {
      setError(e?.message ?? String(e));
      setState("error");
    }
  };

  const stop = () => {
    try {
      vapiRef.current?.stop();
    } catch {
      /* ignore */
    }
  };

  const inCall = state === "connecting" || state === "live";
  // Map volume (0..1) to a visual scale boost for the orb
  const orbScale = 1 + Math.min(volume, 1) * 0.18;

  return (
    <>
      {/* Header pill — always visible */}
      <div className="talk">
        {!inCall ? (
          <button className="talk-pill" onClick={start} aria-label="Avvia chiamata">
            <span className="dot-pulse" /> Parla con l'assistente
          </button>
        ) : (
          <button className="talk-pill talk-pill-live" onClick={stop}>
            <span className="live-dot active" /> In chiamata
          </button>
        )}
      </div>

      {/* Full-screen call modal */}
      {inCall && (
        <div className="call-overlay" role="dialog" aria-modal="true">
          <div className="call-backdrop" />

          <button className="call-close" onClick={stop} aria-label="Termina">
            ×
          </button>

          <div className="call-header">
            <h2>Comune di Codroipo</h2>
            <p>Assistente vocale</p>
          </div>

          <div
            className={`orb-wrap ${assistantTalking ? "speaking" : ""}`}
            style={{ ["--vol" as any]: volume }}
          >
            <div className="wave wave-1" />
            <div className="wave wave-2" />
            <div className="wave wave-3" />
            <div className="wave wave-4" />
            <div
              className="orb"
              style={{ transform: `translate(-50%, -50%) scale(${orbScale})` }}
            >
              {state === "connecting" ? (
                <div className="spinner-big" />
              ) : (
                <svg viewBox="0 0 24 24" width="56" height="56" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z"
                  />
                </svg>
              )}
            </div>
          </div>

          <div className="call-status">
            {state === "connecting"
              ? "Connessione in corso…"
              : assistantTalking
                ? "L'assistente sta parlando…"
                : "In ascolto"}
          </div>

          <div className="transcript">
            {turns.length === 0 && !partial && state === "live" && (
              <p className="transcript-hint">
                Parli pure — l'assistente la ascolta.
              </p>
            )}
            {turns.map((t) => (
              <div key={t.id} className={`turn turn-${t.role}`}>
                <span className="turn-label">
                  {t.role === "user" ? "Lei" : "Assistente"}
                </span>
                <p>{t.text}</p>
              </div>
            ))}
            {partial && (
              <div className={`turn turn-${partial.role} turn-partial`}>
                <span className="turn-label">
                  {partial.role === "user" ? "Lei" : "Assistente"}
                </span>
                <p>{partial.text}</p>
              </div>
            )}
            <div ref={turnsEndRef} />
          </div>

          <button className="call-end" onClick={stop}>
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path
                fill="currentColor"
                d="M12 9c-1.6 0-3.15.25-4.6.72v3.1c0 .39-.23.74-.56.9-.98.49-1.87 1.12-2.66 1.85-.18.18-.43.28-.7.28-.28 0-.53-.11-.71-.29L.29 13.08a.996.996 0 0 1-.29-.7c0-.28.11-.53.29-.71C3.34 8.78 7.46 7 12 7s8.66 1.78 11.71 4.67c.18.18.29.43.29.71 0 .28-.11.53-.29.71l-2.48 2.48c-.18.18-.43.29-.71.29-.27 0-.52-.1-.7-.28a11.27 11.27 0 0 0-2.67-1.85.996.996 0 0 1-.56-.9v-3.1C15.15 9.25 13.6 9 12 9z"
              />
            </svg>
            Termina chiamata
          </button>
        </div>
      )}

      {/* Error banner — non-modal */}
      {state === "error" && error && (
        <div className="talk-error-toast">⚠ {error}</div>
      )}
    </>
  );
}
