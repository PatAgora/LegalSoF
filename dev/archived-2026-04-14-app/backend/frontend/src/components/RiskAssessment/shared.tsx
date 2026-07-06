// Shared primitives for the Risk Assessment module (FWRA + CMRA).
// Follows the zinc design system and the live-character-counter
// pattern from components/ui/RationaleModal.tsx.

// ---------------------------------------------------------------------------
// Types mirrored from the backend (app/api/v1/endpoints/risk_assessments.py)
// ---------------------------------------------------------------------------

export interface FwraSection {
  risk_level: string
  reasoning: string
  mitigations: string
}

export interface FirmRA {
  id: number
  version: number
  status: string
  sections: Record<string, FwraSection>
  sectoral_ra_acknowledged: boolean
  sectoral_ra_date: string | null
  nra_acknowledged: boolean
  nra_date: string | null
  approved_by_id: number | null
  approved_at: string | null
  next_review_due: string | null
  created_at: string | null
}

export interface CmraFactor {
  score: number | null
  reasoning: string
}

export interface Cmra {
  id: number
  matter_id: number
  assessment_type: string
  factors: Record<string, CmraFactor>
  reg28_considerations: Record<string, string>
  context_flags: { client_is_pep?: boolean; geography_countries?: string[]; unusual_complexity?: boolean }
  overall_rating: string | null
  edd_required: boolean
  edd_triggers: string[]
  status: string
  completed_at: string | null
  review_due: string | null
  created_at: string | null
}

// The six mandatory FWRA sections (MLR 2017 reg 18(2)(a) + reg 18A).
export const FWRA_SECTION_LABELS: { key: string; label: string; hint: string }[] = [
  { key: 'customers', label: 'Customers', hint: 'Client base profile — PEPs, high-net-worth, non-face-to-face, cash-intensive businesses.' },
  { key: 'geography', label: 'Countries & Geographic Areas', hint: 'Jurisdictions the firm and its clients operate in or transact with.' },
  { key: 'products_services', label: 'Products & Services', hint: 'Conveyancing, trust/company formation, client account use and other services offered.' },
  { key: 'transactions', label: 'Transactions', hint: 'Value, volume and nature of transactions the firm handles.' },
  { key: 'delivery_channels', label: 'Delivery Channels', hint: 'How services are delivered — remote onboarding, intermediaries, referrals.' },
  { key: 'proliferation_financing', label: 'Proliferation Financing (Reg 18A)', hint: 'Risk of funds or services contributing to proliferation of weapons of mass destruction.' },
]

// The five LSAG factor sets scored on every client/matter assessment.
export const CMRA_FACTOR_LABELS: { key: string; label: string; hint: string }[] = [
  { key: 'client', label: 'Client', hint: 'Who the client is — identity, transparency, PEP status, behaviour.' },
  { key: 'service_matter', label: 'Service / Matter', hint: 'What the firm is being asked to do and whether it makes commercial sense.' },
  { key: 'geography', label: 'Geography', hint: 'Jurisdictions connected to the client, the funds and the transaction.' },
  { key: 'delivery_channel', label: 'Delivery Channel', hint: 'How the client was met and is dealt with — face-to-face or remote.' },
  { key: 'sector_product', label: 'Sector / Product', hint: 'The sector the client operates in and the products involved.' },
]

export const REG28_LABELS: { key: string; label: string }[] = [
  { key: 'purpose_of_matter', label: 'Purpose of the matter' },
  { key: 'size_of_transaction', label: 'Size of the transaction' },
  { key: 'regularity_duration', label: 'Regularity and duration of the relationship' },
]

// Mirror of the backend defaults (CMRA_CONFIG_DEFAULTS) used only for the
// LIVE preview while typing — the server recomputes authoritatively on save.
export const CMRA_DEFAULT_WEIGHTS: Record<string, number> = {
  client: 0.30,
  service_matter: 0.25,
  geography: 0.20,
  delivery_channel: 0.15,
  sector_product: 0.10,
}
export const CMRA_MEDIUM_THRESHOLD = 1.6
export const CMRA_HIGH_THRESHOLD = 2.4
// FATF call-for-action list, mirrored from the backend module constant.
export const FATF_CALL_FOR_ACTION = ['KP', 'IR', 'MM']

export function previewCmraScoring(
  factors: Record<string, CmraFactor>,
  flags: Cmra['context_flags'],
): { rating: 'low' | 'medium' | 'high'; triggers: string[] } {
  let sum = 0
  let total = 0
  let anyHigh = false
  for (const [key, weight] of Object.entries(CMRA_DEFAULT_WEIGHTS)) {
    const score = factors[key]?.score
    if (score === 1 || score === 2 || score === 3) {
      sum += score * weight
      total += weight
      if (score === 3) anyHigh = true
    }
  }
  const avg = total > 0 ? sum / total : 0
  let rating: 'low' | 'medium' | 'high' =
    avg >= CMRA_HIGH_THRESHOLD ? 'high' : avg >= CMRA_MEDIUM_THRESHOLD ? 'medium' : 'low'
  if (anyHigh && rating === 'low') rating = 'medium'

  const triggers: string[] = []
  if (flags.client_is_pep) triggers.push('Client is a politically exposed person (PEP) — reg 35 EDD applies')
  const hits = (flags.geography_countries || [])
    .map(c => c.trim().toUpperCase())
    .filter(c => FATF_CALL_FOR_ACTION.includes(c))
  if (hits.length) triggers.push(`Geography includes FATF call-for-action jurisdiction(s): ${[...new Set(hits)].join(', ')}`)
  if (flags.unusual_complexity) triggers.push('Transaction flagged as unusually large or complex — reg 33(6)(b)')
  if (rating === 'high') triggers.push('Overall risk rating is HIGH — reg 33(1)(a) EDD applies')
  return { rating, triggers }
}

// ---------------------------------------------------------------------------
// Small presentational pieces
// ---------------------------------------------------------------------------

export function RatingBadge({ rating }: { rating: string | null | undefined }) {
  const map: Record<string, { label: string; cls: string; dot: string }> = {
    low: { label: 'Low', cls: 'bg-green-50 text-green-700 ring-green-200', dot: 'bg-green-500' },
    medium: { label: 'Medium', cls: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
    high: { label: 'High', cls: 'bg-red-50 text-red-700 ring-red-200', dot: 'bg-red-500' },
  }
  const c = map[String(rating || '').toLowerCase()]
  if (!c) return <span className="text-xs text-zinc-400">—</span>
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold ring-1 ring-inset ${c.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    draft: 'bg-zinc-100 text-zinc-600 ring-zinc-200',
    approved: 'bg-green-50 text-green-700 ring-green-200',
    completed: 'bg-green-50 text-green-700 ring-green-200',
    superseded: 'bg-zinc-50 text-zinc-400 ring-zinc-200',
  }
  const cls = map[status] || map.draft
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${cls}`}>
      {status}
    </span>
  )
}

// Textarea with a live character counter — same pattern as the
// rationale box in components/ui/RationaleModal.tsx.
export function ReasoningTextarea({
  label, value, onChange, minLength = 1, rows = 3, placeholder, disabled,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  minLength?: number
  rows?: number
  placeholder?: string
  disabled?: boolean
}) {
  const len = value.trim().length
  const ok = len >= minLength
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <label className="block text-xs font-semibold text-zinc-600">
          {label}{minLength > 1 ? ` (required, min ${minLength} characters)` : ' (required)'}
        </label>
        <span className={`text-[10px] font-medium ${ok ? 'text-green-700' : 'text-zinc-400'}`}>
          {len}{minLength > 1 ? ` / ${minLength} min` : ''}
        </span>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        placeholder={placeholder}
        disabled={disabled}
        className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300 disabled:bg-zinc-50 disabled:text-zinc-500"
      />
    </div>
  )
}

// 1-3 score pill selector for a CMRA factor.
export function ScorePills({ value, onChange, disabled }: {
  value: number | null
  onChange: (v: number) => void
  disabled?: boolean
}) {
  const opts: { score: number; label: string; active: string }[] = [
    { score: 1, label: '1 · Low', active: 'bg-green-600 text-white border-green-600' },
    { score: 2, label: '2 · Medium', active: 'bg-amber-500 text-white border-amber-500' },
    { score: 3, label: '3 · High', active: 'bg-red-600 text-white border-red-600' },
  ]
  return (
    <div className="flex gap-2">
      {opts.map(o => (
        <button
          key={o.score}
          type="button"
          disabled={disabled}
          onClick={() => onChange(o.score)}
          className={`px-3 py-1.5 rounded border text-xs font-semibold transition-colors disabled:opacity-50 ${
            value === o.score
              ? o.active
              : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-400'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// EDD banner listing the triggers that force enhanced due diligence.
export function EddBanner({ triggers }: { triggers: string[] }) {
  if (!triggers.length) return null
  return (
    <div className="rounded border border-red-200 bg-red-50 px-4 py-3">
      <div className="text-sm font-semibold text-red-800">Enhanced Due Diligence required</div>
      <ul className="mt-1.5 list-disc pl-5 space-y-0.5">
        {triggers.map((t, i) => (
          <li key={i} className="text-xs text-red-700">{t}</li>
        ))}
      </ul>
    </div>
  )
}
