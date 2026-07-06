// E-IDV API client + shared types.
//
// provider='complycube' returns 409 with guidance while
// COMPLYCUBE_API_KEY is unset; provider='manual' is always available
// but is the TRADITIONAL route — never DIATF-certified E-IDV.
import { API_BASE_URL, authFetch } from '../../lib/api'

export type EidvSubjectType = 'client' | 'beneficial_owner' | 'giftor'
export type EidvStatus = 'pending' | 'passed' | 'failed' | 'review'

export interface EidvChecklistItem {
  id: string
  label: string
  description: string
  required: boolean
}

export interface EidvCheck {
  id: number
  matter_id: number
  subject_type: EidvSubjectType
  subject_name: string
  subject_dob: string | null
  subject_email: string | null
  provider: 'manual' | 'complycube'
  provider_ref: string | null
  method: string | null
  status: EidvStatus
  diatf_certified: boolean
  checks: Record<string, string> | null
  evidence_notes: string | null
  completed_by_id: number | null
  completed_at: string | null
  created_at: string | null
}

export interface EidvCreateResponse extends EidvCheck {
  client_url?: string | null
  instructions?: { caveat: string; checklist: EidvChecklistItem[] } | null
  caveat?: string
}

export interface EidvListResponse {
  items: EidvCheck[]
  manual_caveat: string
}

export interface ManualResultPayload {
  document_type: string
  document_number: string
  expiry_date: string // ISO YYYY-MM-DD
  likeness_confirmed: boolean
  certified_copy_details?: string
  notes?: string
}

async function parseOrThrow<T>(r: Response): Promise<T> {
  const data = await r.json().catch(() => ({}))
  if (!r.ok) {
    const detail = data?.detail
    const message = Array.isArray(detail)
      ? detail.map((d: any) => d?.msg || JSON.stringify(d)).join('; ')
      : detail || `Request failed (${r.status})`
    throw new Error(message)
  }
  return data as T
}

export async function listEidvChecks(matterId: string | number): Promise<EidvListResponse> {
  const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/eidv`)
  return parseOrThrow<EidvListResponse>(r)
}

export async function createEidvCheck(
  matterId: string | number,
  payload: {
    subject_type: EidvSubjectType
    subject_name: string
    subject_dob?: string
    subject_email?: string
    provider: 'manual' | 'complycube'
  },
): Promise<EidvCreateResponse> {
  const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/eidv`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return parseOrThrow<EidvCreateResponse>(r)
}

export async function submitManualResult(
  matterId: string | number,
  checkId: number,
  payload: ManualResultPayload,
): Promise<EidvCheck & { caveat: string }> {
  const r = await authFetch(
    `${API_BASE_URL}/api/v1/matters/${matterId}/eidv/${checkId}/manual-result`,
    { method: 'PUT', body: JSON.stringify(payload) },
  )
  return parseOrThrow(r)
}

export const SUBJECT_TYPE_LABELS: Record<EidvSubjectType, string> = {
  client: 'Client',
  beneficial_owner: 'Beneficial owner',
  giftor: 'Giftor',
}
