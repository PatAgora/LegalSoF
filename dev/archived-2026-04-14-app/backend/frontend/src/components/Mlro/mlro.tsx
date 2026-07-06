// Shared types + helpers for the MLRO workbench.
//
// UK legal context encoded here:
//  * POCA 2002 s.330 — anyone may file an internal report; s.333A —
//    after submission the reporter/client team never see its status.
//  * SAR filing is HUMAN-ONLY via the NCA SAR Portal; the platform
//    prepares and records.
//  * DAML: 7 WORKING days notice from filing, 31 CALENDAR days
//    moratorium on refusal.
import { API_BASE_URL, authFetch } from '../../lib/api';

export interface MlroDashboard {
  report_counts: Record<string, number>;
  open_reports: number;
  daml_deadlines_within_7_days: {
    sar_id: number;
    sar_reference: string | null;
    consent_deadline: string | null;
    overdue: boolean;
  }[];
  active_moratoria: {
    sar_id: number;
    sar_reference: string | null;
    moratorium_end: string | null;
    days_remaining: number;
    active: boolean;
  }[];
  overdue_policy_reviews: number;
  training_expiring_within_60_days: number;
}

export interface MlroReportSummary {
  id: number;
  matter_id: number | null;
  matter_reference: string | null;
  reporter_name: string | null;
  subject_summary: string | null;
  status: string;
  submitted_at: string | null;
  decided_at: string | null;
  privilege_considered: boolean;
}

export interface SarInfo {
  id: number;
  internal_report_id: number;
  sar_reference: string | null;
  filed_at: string | null;
  filed_by_name: string | null;
  daml_requested: boolean;
  daml_filed_at: string | null;
  daml_status: string;
  consent_deadline: string | null;
  moratorium_end: string | null;
  notes: string | null;
  matter_id?: number | null;
  matter_reference?: string | null;
}

export interface MlroReportDetail extends MlroReportSummary {
  suspicion_details: string;
  mlro_notes: string | null;
  decision_rationale: string | null;
  decided_by_name: string | null;
  privilege_notes: string | null;
  sars: SarInfo[];
  matter_context: Record<string, unknown[]>;
}

export interface TrainingRecordInfo {
  id: number;
  user_id: number;
  user_name: string | null;
  course_name: string;
  provider: string | null;
  completed_at: string | null;
  expires_at: string | null;
  certificate_note: string | null;
}

export interface PolicyInfo {
  id: number;
  title: string;
  version: string;
  status: string;
  content_note: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  review_due: string | null;
  acknowledged_by_me: boolean;
  acknowledgement_count: number;
  acknowledgements?: { user_id: number; user_name: string | null; acknowledged_at: string | null }[];
  not_acknowledged?: { user_id: number; user_name: string | null }[];
}

export async function mlroGet<T>(path: string): Promise<T> {
  const r = await authFetch(`${API_BASE_URL}/api/v1${path}`);
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(data?.detail || `Request failed (${r.status})`);
  }
  return r.json();
}

export async function mlroSend<T>(path: string, method: string, body?: unknown): Promise<T> {
  const r = await authFetch(`${API_BASE_URL}/api/v1${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    const detail = typeof data?.detail === 'string' ? data.detail : `Request failed (${r.status})`;
    throw new Error(detail);
  }
  return r.json();
}

export function fmtDateTime(s: string | null | undefined): string {
  if (!s) return '—';
  const d = new Date(s);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return '—';
  const d = new Date(s);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

// Working days (weekends only — matches the backend calculator; bank
// holidays are a noted follow-up) remaining until `deadline`.
// Negative when the deadline has passed.
export function workingDaysUntil(deadline: string | null | undefined, from?: Date): number {
  if (!deadline) return 0;
  const end = new Date(deadline);
  if (isNaN(end.getTime())) return 0;
  const start = from ?? new Date();
  const s = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  const e = new Date(end.getFullYear(), end.getMonth(), end.getDate());
  if (e.getTime() === s.getTime()) return 0;
  const step = e > s ? 1 : -1;
  let days = 0;
  const cursor = new Date(s);
  while (cursor.getTime() !== e.getTime()) {
    cursor.setDate(cursor.getDate() + step);
    const dow = cursor.getDay(); // 0 Sun .. 6 Sat
    if (dow !== 0 && dow !== 6) days += step;
  }
  return days;
}

export function calendarDaysUntil(deadline: string | null | undefined, from?: Date): number {
  if (!deadline) return 0;
  const end = new Date(deadline);
  if (isNaN(end.getTime())) return 0;
  const start = from ?? new Date();
  return Math.ceil((end.getTime() - start.getTime()) / 86400000);
}

export const REPORT_STATUS_LABELS: Record<string, { label: string; cls: string; dot: string }> = {
  received: { label: 'Received', cls: 'bg-blue-50 text-blue-700 ring-blue-200', dot: 'bg-blue-500' },
  under_review: { label: 'Under review', cls: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
  sar_filed: { label: 'SAR filed', cls: 'bg-purple-50 text-purple-700 ring-purple-200', dot: 'bg-purple-500' },
  no_sar_decision: { label: 'No SAR (documented)', cls: 'bg-green-50 text-green-700 ring-green-200', dot: 'bg-green-500' },
};

export const DAML_STATUS_LABELS: Record<string, { label: string; cls: string; dot: string }> = {
  none: { label: 'No DAML', cls: 'bg-zinc-50 text-zinc-500 ring-zinc-200', dot: 'bg-zinc-400' },
  awaiting_consent: { label: 'Awaiting consent', cls: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
  consent_granted: { label: 'Consent granted', cls: 'bg-green-50 text-green-700 ring-green-200', dot: 'bg-green-500' },
  consent_refused_moratorium: { label: 'Refused — moratorium', cls: 'bg-red-50 text-red-700 ring-red-200', dot: 'bg-red-500' },
  moratorium_expired: { label: 'Moratorium expired', cls: 'bg-zinc-100 text-zinc-600 ring-zinc-300', dot: 'bg-zinc-500' },
};

export function StatusChip({ status, map }: { status: string; map: Record<string, { label: string; cls: string; dot: string }> }) {
  const c = map[status] || { label: status, cls: 'bg-zinc-50 text-zinc-500 ring-zinc-200', dot: 'bg-zinc-400' };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold ring-1 ring-inset whitespace-nowrap ${c.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}
