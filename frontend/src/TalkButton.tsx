import { useEffect, useRef, useState } from "react";
import Vapi from "@vapi-ai/web";

type CallState = "idle" | "connecting" | "live" | "error";

const PUBLIC_KEY = import.meta.env.VITE_VAPI_PUBLIC_KEY as string | undefined;
const ASSISTANT_ID = import.meta.env.VITE_VAPI_ASSISTANT_ID as string | undefined;

export default function TalkButton() {
  const [state, setState] = useState<CallState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [assistantSpeaking, setAssistantSpeaking] = useState(false);
  const vapiRef = useRef<Vapi | null>(null);

  useEffect(() => {
    if (!PUBLIC_KEY) return;
    const v = new Vapi(PUBLIC_KEY);
    vapiRef.current = v;

    v.on("call-start", () => setState("live"));
    v.on("call-end", () => {
      setState("idle");
      setAssistantSpeaking(false);
    });
    v.on("speech-start", () => setAssistantSpeaking(true));
    v.on("speech-end", () => setAssistantSpeaking(false));
    v.on("error", (e: unknown) => {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg || "errore sconosciuto");
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

  if (!PUBLIC_KEY || !ASSISTANT_ID) {
    return null;
  }

  const start = async () => {
    setError(null);
    setState("connecting");
    try {
      await vapiRef.current!.start(ASSISTANT_ID!);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setState("error");
    }
  };

  const stop = () => {
    vapiRef.current?.stop();
    setState("idle");
  };

  return (
    <div className={`talk talk-${state}`}>
      {state === "idle" && (
        <button className="talk-btn talk-start" onClick={start}>
          <span className="dot-pulse" /> Parla con l'assistente
        </button>
      )}
      {state === "connecting" && (
        <button className="talk-btn talk-connecting" disabled>
          <span className="spinner" /> Connessione…
        </button>
      )}
      {state === "live" && (
        <button className="talk-btn talk-stop" onClick={stop}>
          <span className={`live-dot ${assistantSpeaking ? "active" : ""}`} /> Termina chiamata
        </button>
      )}
      {state === "error" && (
        <>
          <button className="talk-btn talk-error" onClick={start}>
            Riprova
          </button>
          {error && <span className="talk-error-msg">{error}</span>}
        </>
      )}
    </div>
  );
}
