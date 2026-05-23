export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

export type Appointment = {
  code: string;
  citizen_name: string;
  fiscal_code: string | null;
  phone: string | null;
  office: string;
  reason: string | null;
  scheduled_at: string;
  status: string;
  created_at: string;
};

export type CallLog = {
  call_id: string;
  started_at: string | null;
  ended_at: string | null;
  ended_reason: string | null;
  summary: string | null;
  transcript: string | null;
  recording_url: string | null;
  created_at: string;
};

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const fetchAppointments = () => get<Appointment[]>("/appointments");
export const fetchCallLogs = () => get<CallLog[]>("/calls");
