const BASE = "/api/alarms";

export interface AlarmStats {
  date: string;
  resolved: number;
  triggered: number;
  first_alarm: string | null;
  last_alarm: string | null;
}

export interface TopAlarm {
  alarmmessage: string;
  trigger_count: number;
  resolve_count: number;
  severityclass: string;
}

export interface AlarmItem {
  time: string;
  alarmmessage: string;
  severityclass: string;
  state: "resolved" | "triggered";
}

export interface AlarmListResponse {
  total: number;
  page: number;
  per_page: number;
  pages: number;
  items: AlarmItem[];
}

export interface TrendPoint {
  date: string;
  triggered: number;
  resolved: number;
}

// signal komt uit useApi: zo kan een unmount/timeout de fetch ook echt afbreken
// (voorheen werd het signal genegeerd en liep het verzoek door).
async function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

export interface OpenAlarm {
  alarmmessage: string;
  severityclass: string;
  last_seen: string;
}

export function fetchOpenAlarms(date: string, signal?: AbortSignal): Promise<OpenAlarm[]> {
  return get(`${BASE}/open?date=${date}`, signal);
}

export function fetchStats(date: string, signal?: AbortSignal): Promise<AlarmStats> {
  return get(`${BASE}/stats?date=${date}`, signal);
}

export function fetchTopAlarms(date: string, limit = 10, signal?: AbortSignal): Promise<TopAlarm[]> {
  return get(`${BASE}/top?date=${date}&limit=${limit}`, signal);
}

export function fetchAlarmList(params: {
  date: string;
  severity?: string;
  search?: string;
  page?: number;
  per_page?: number;
}, signal?: AbortSignal): Promise<AlarmListResponse> {
  const qs = new URLSearchParams({ date: params.date });
  if (params.severity) qs.set("severity", params.severity);
  if (params.search) qs.set("search", params.search);
  if (params.page) qs.set("page", String(params.page));
  if (params.per_page) qs.set("per_page", String(params.per_page));
  return get(`${BASE}/list?${qs}`, signal);
}

export function fetchTrends(from: string, to: string, signal?: AbortSignal): Promise<TrendPoint[]> {
  return get(`${BASE}/trends?from=${from}&to=${to}`, signal);
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sql?: string | null;
  data?: Record<string, unknown>[] | null;
}

export interface ChatApiResponse {
  answer: string;
  sql: string | null;
  data: Record<string, unknown>[] | null;
}

export async function sendChatMessage(
  message: string,
  history: { role: "user" | "assistant"; content: string }[] = [],
): Promise<ChatApiResponse> {
  // Historie (laatste berichten, alleen rol+tekst) geeft de AI context voor
  // vervolgvragen ("en de dag ervoor?"); de backend trimt op aantal en lengte.
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `API error: ${res.status}`);
  }
  return res.json();
}

// ── Productie KPI's ─────────────────────────────────────────────────

export interface ProductionSummary {
  date: string;
  infeed_total: number;
  placed_total: number;
  missed_total: number;
  yield_pct: number | null;
  per_robot: number[];
  downtime_minutes: number[];
  shift_minutes: number;
  data_gap_minutes: number;
  peak_hour: string | null;
  peak_hour_total: number;
  robot_balance: number | null;
  mttr_avg_minutes: number | null;
  mttr_min_minutes: number | null;
  mttr_max_minutes: number | null;
  mttr_resolved: number;
  mttr_unresolved: number;
}

// Productiepunt: instroom + per robot + geplaatst (robot1 + robot2).
export interface FlowPoint {
  robot1: number;
  robot2: number;
  infeed: number;
  placed: number;
}

export interface HourlyProduction extends FlowPoint {
  hour: string;
}

export interface ProductionTrend extends FlowPoint {
  date: string;
}

export interface AlarmImpact {
  date: string;
  avg_during_alarm: number | null;
  avg_without_alarm: number | null;
  alarm_minutes: number;
  normal_minutes: number;
  production_loss_pct: number | null;
  hourly_correlation: { hour: string; production: number; alarms: number }[];
}

export function fetchProductionSummary(date: string, signal?: AbortSignal): Promise<ProductionSummary> {
  return get(`/api/production/summary?date=${date}`, signal);
}

export interface MinutelyProduction extends FlowPoint {
  minute: string;
}

export function fetchHourlyProduction(date: string, signal?: AbortSignal): Promise<HourlyProduction[]> {
  return get(`/api/production/hourly?date=${date}`, signal);
}

export function fetchMinutelyProduction(date: string, hour: number, signal?: AbortSignal): Promise<MinutelyProduction[]> {
  return get(`/api/production/minutely?date=${date}&hour=${hour}`, signal);
}

export function fetchProductionTrends(from: string, to: string, signal?: AbortSignal): Promise<ProductionTrend[]> {
  return get(`/api/production/trends?from=${from}&to=${to}`, signal);
}

export function fetchAlarmImpact(date: string, signal?: AbortSignal): Promise<AlarmImpact> {
  return get(`/api/production/alarm-impact?date=${date}`, signal);
}

export interface OeeRobotData {
  robot: number;
  name: string;
  oee: number;
  availability: number;
  performance: number;
  quality: number;
  downtime_minutes: number;
  speed_loss_minutes: number;
}

export interface OeeLosses {
  planned_time: number;
  downtime_loss: number;
  speed_loss: number;
  quality_loss: number;
  effective_time: number;
}

export interface OeeSixBigLoss {
  category: string;
  type: string;
  events?: number;
  minutes?: number;
}

export interface OeeData {
  date: string;
  oee: number | null;
  availability: number | null;
  performance: number | null;
  quality: number;
  per_robot: OeeRobotData[];
  losses: OeeLosses | null;
  six_big_losses: OeeSixBigLoss[];
  data_gap_minutes: number;
}

export function fetchOee(date: string, signal?: AbortSignal): Promise<OeeData> {
  return get(`/api/production/oee?date=${date}`, signal);
}

// ── Pallet KPI's ────────────────────────────────────────────────────

export interface PalletStation {
  id: string;
  ready_pct: number;
  empty_pct: number;
  none_pct: number;
}

export interface PalletSummary {
  date: string;
  total_readings: number;
  stations: PalletStation[];
}

export interface HourlyPallet {
  hour: string;
  s6000: number;
  s6005: number;
  s6010: number;
  s6015: number;
}

export function fetchPalletSummary(date: string, signal?: AbortSignal): Promise<PalletSummary> {
  return get(`/api/pallets/summary?date=${date}`, signal);
}

export function fetchHourlyPallets(date: string, signal?: AbortSignal): Promise<HourlyPallet[]> {
  return get(`/api/pallets/hourly?date=${date}`, signal);
}
