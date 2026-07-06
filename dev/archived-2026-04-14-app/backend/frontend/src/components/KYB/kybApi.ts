// KYB (Companies House) API client + shared types.
//
// All endpoints can return:
//   409 — COMPANIES_HOUSE_API_KEY not configured (detail carries setup guidance)
//   429 — Companies House rate limit (600 requests / 5 minutes)
// callers surface `detail` verbatim so the guidance reaches the user.
import { API_BASE_URL, authFetch } from '../../lib/api'

export interface CompanySearchItem {
  company_number: string
  title: string
  company_status: string | null
  company_type: string | null
  date_of_creation: string | null
  address_snippet: string | null
}

export interface CompanySearchResponse {
  total_results: number
  items: CompanySearchItem[]
  reg_28_9_note: string
}

export interface KybProfile {
  company_number: string | null
  company_name: string | null
  company_status: string | null
  company_status_detail: string | null
  type: string | null
  jurisdiction: string | null
  date_of_creation: string | null
  date_of_cessation: string | null
  sic_codes: string[]
  registered_office_address: string | null
  registered_office_is_in_dispute: boolean | null
  has_insolvency_history: boolean | null
  has_charges: boolean | null
  undeliverable_registered_office_address: boolean | null
  accounts_overdue: boolean | null
  confirmation_statement_overdue: boolean | null
}

export interface KybOfficer {
  name: string | null
  officer_role: string | null
  appointed_on: string | null
  resigned_on: string | null
  nationality: string | null
  occupation: string | null
  country_of_residence: string | null
  date_of_birth: string | null
  address: string | null
}

export interface KybPsc {
  name: string | null
  kind: string
  is_individual: boolean
  natures_of_control: string[]
  natures_described: string[]
  ownership_band: string | null
  notified_on: string | null
  ceased_on: string | null
  nationality: string | null
  country_of_residence: string | null
  date_of_birth: string | null
  address: string | null
  identification: Record<string, string> | null
  requires_individual_verification: boolean
}

export interface KybCheck {
  id: number
  matter_id: number
  company_number: string
  company_name: string | null
  status: 'pending' | 'complete' | 'discrepancy_reported'
  profile: KybProfile | null
  officers: { active_count: number; resigned_count: number; items: KybOfficer[] } | null
  pscs: { active_count: number; ceased_count: number; items: KybPsc[] } | null
  ownership_notes: string | null
  psc_discrepancy: string | null
  psc_discrepancy_reported_at: string | null
  created_at: string | null
  refreshed_at: string | null
}

export interface KybListResponse {
  items: KybCheck[]
  reg_28_9_note: string
}

async function parseOrThrow<T>(r: Response): Promise<T> {
  const data = await r.json().catch(() => ({}))
  if (!r.ok) {
    throw new Error(data?.detail || `Request failed (${r.status})`)
  }
  return data as T
}

export async function searchCompanies(q: string): Promise<CompanySearchResponse> {
  const r = await authFetch(
    `${API_BASE_URL}/api/v1/kyb/search?q=${encodeURIComponent(q)}`,
  )
  return parseOrThrow<CompanySearchResponse>(r)
}

export async function listKybChecks(matterId: string | number): Promise<KybListResponse> {
  const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/kyb`)
  return parseOrThrow<KybListResponse>(r)
}

export async function createKybCheck(
  matterId: string | number,
  companyNumber: string,
): Promise<KybCheck & { reg_28_9_note: string }> {
  const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/kyb`, {
    method: 'POST',
    body: JSON.stringify({ company_number: companyNumber }),
  })
  return parseOrThrow(r)
}

export async function refreshKybCheck(
  matterId: string | number,
  checkId: number,
): Promise<KybCheck> {
  const r = await authFetch(
    `${API_BASE_URL}/api/v1/matters/${matterId}/kyb/${checkId}/refresh`,
    { method: 'POST' },
  )
  return parseOrThrow<KybCheck>(r)
}

export async function reportPscDiscrepancy(
  matterId: string | number,
  checkId: number,
  details: string,
): Promise<KybCheck & { reg_30a_note: string }> {
  const r = await authFetch(
    `${API_BASE_URL}/api/v1/matters/${matterId}/kyb/${checkId}/psc-discrepancy`,
    { method: 'POST', body: JSON.stringify({ details }) },
  )
  return parseOrThrow(r)
}
