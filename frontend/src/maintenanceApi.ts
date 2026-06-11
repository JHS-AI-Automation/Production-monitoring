// API-laag voor de Maintenance-sectie. Apart gehouden van api.ts zodat de feature
// geïsoleerd blijft. signal komt uit useApi (timeout/abort), net als in api.ts.

async function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

export type MotorStatus = "ok" | "warn" | "alarm" | "unknown";

export interface Motor {
  id: number;
  name: string;
  line: number;
  baseline_a: number | null;
  current_a: number | null;
  increase_pct: number | null;
  status: MotorStatus;
}

export interface MotorsResponse {
  days: number;
  motors: Motor[];
}

export interface HistoryPoint {
  date: string;
  start_a: number;
  peak_a: number;
}

export interface MotorAnalysis {
  baseline_a: number;
  current_a: number;
  recent_a: number;
  increase_pct: number;
  since_days: number;
  status: MotorStatus;
}

export interface MotorHistory {
  motor_id: number;
  days: number;
  analysis: MotorAnalysis | null;
  history: HistoryPoint[];
}

export interface WearSignal {
  motor_id: number;
  motor_name: string;
  line: number | null;
  baseline_a: number;
  current_a: number;
  increase_pct: number;
  since_days: number;
  status: MotorStatus;
  advice: string;
}

export interface SignalsResponse {
  days: number;
  signals: WearSignal[];
}

const BASE = "/api/maintenance";

export function fetchMotors(days = 60, signal?: AbortSignal): Promise<MotorsResponse> {
  return get(`${BASE}/motors?days=${days}`, signal);
}

export function fetchMotorHistory(id: number, days = 60, signal?: AbortSignal): Promise<MotorHistory> {
  return get(`${BASE}/motors/${id}/history?days=${days}`, signal);
}

export function fetchSignals(days = 60, signal?: AbortSignal): Promise<SignalsResponse> {
  return get(`${BASE}/signals?days=${days}`, signal);
}
