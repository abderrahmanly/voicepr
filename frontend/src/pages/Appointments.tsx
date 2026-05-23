import { useEffect, useState } from "react";
import { Appointment, fetchAppointments } from "../api";

const OFFICE_LABELS: Record<string, string> = {
  anagrafe: "Anagrafe",
  stato_civile: "Stato Civile",
  tributi: "Tributi",
  ufficio_tecnico: "Ufficio Tecnico",
  ufficio_elettorale: "Ufficio Elettorale",
  protocollo: "Protocollo",
  servizi_sociali: "Servizi Sociali",
  polizia_locale: "Polizia Locale",
  scuola: "Ufficio Istruzione",
};

function fmt(dt: string) {
  return new Date(dt).toLocaleString("it-IT", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function Appointments() {
  const [items, setItems] = useState<Appointment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      fetchAppointments()
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
        <h1>Appuntamenti prenotati</h1>
        <span className="hint">Aggiornamento ogni 10 secondi</span>
      </div>
      {error && <div className="err">Errore: {error}</div>}
      {!items ? (
        <p className="muted">Caricamento…</p>
      ) : items.length === 0 ? (
        <p className="muted">
          Nessun appuntamento ancora. Effettua una chiamata di prova al voicebot per crearne uno.
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Codice</th>
              <th>Cittadino</th>
              <th>Ufficio</th>
              <th>Quando</th>
              <th>Motivo</th>
              <th>Stato</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.code}>
                <td>
                  <code>{a.code}</code>
                </td>
                <td>{a.citizen_name}</td>
                <td>{OFFICE_LABELS[a.office] ?? a.office}</td>
                <td>{fmt(a.scheduled_at)}</td>
                <td className="reason">{a.reason ?? "—"}</td>
                <td>
                  <span className={`badge badge-${a.status}`}>{a.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
