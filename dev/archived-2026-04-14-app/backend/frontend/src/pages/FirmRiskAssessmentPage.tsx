// Firm-Wide Risk Assessment (MLR 2017 reg 18 / 18A) — admin only.
// Sectioned editor for the six mandatory factor sets, dated
// acknowledgements of the SRA sectoral RA and the NRA, approve flow
// with supersession, version history and an overdue-review banner.
import { useCallback, useEffect, useState } from 'react'
import { API_BASE_URL, authFetch } from '../lib/api'
import { showToast } from '../lib/toast'
import { formatDate, formatDateTime } from '../lib/format'
import { ConfirmModal } from '../components/ui/RationaleModal'
import Spinner from '../components/ui/Spinner'
import FirmSectionCard from '../components/RiskAssessment/FirmSectionCard'
import {
  FirmRA, FwraSection, FWRA_SECTION_LABELS, StatusBadge, RatingBadge,
} from '../components/RiskAssessment/shared'

const MIN_REASONING = 50

interface FwraState {
  current: FirmRA | null
  draft: FirmRA | null
  history: FirmRA[]
  review_overdue: boolean
  review_overdue_message: string | null
}

const EMPTY_SECTION: FwraSection = { risk_level: '', reasoning: '', mitigations: '' }

async function readError(r: Response): Promise<string> {
  try {
    const body = await r.json()
    const d = body?.detail
    if (typeof d === 'string') return d
    if (d?.problems?.length) return d.problems.join('\n')
    if (d?.message) return d.message
  } catch { /* fall through */ }
  return `Request failed (${r.status})`
}

export default function FirmRiskAssessmentPage() {
  const [state, setState] = useState<FwraState | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showApprove, setShowApprove] = useState(false)
  const [problems, setProblems] = useState<string[]>([])

  // Local editable copy of the draft.
  const [sections, setSections] = useState<Record<string, FwraSection>>({})
  const [sraAck, setSraAck] = useState(false)
  const [sraDate, setSraDate] = useState('')
  const [nraAck, setNraAck] = useState(false)
  const [nraDate, setNraDate] = useState('')
  const [nextReview, setNextReview] = useState('')

  const hydrate = useCallback((s: FwraState) => {
    setState(s)
    const d = s.draft
    if (d) {
      const secs: Record<string, FwraSection> = {}
      for (const { key } of FWRA_SECTION_LABELS) {
        secs[key] = { ...EMPTY_SECTION, ...(d.sections?.[key] || {}) }
      }
      setSections(secs)
      setSraAck(d.sectoral_ra_acknowledged)
      setSraDate(d.sectoral_ra_date || '')
      setNraAck(d.nra_acknowledged)
      setNraDate(d.nra_date || '')
      setNextReview(d.next_review_due || '')
    }
  }, [])

  const load = useCallback(async () => {
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/firm-risk-assessment`)
      if (!r.ok) throw new Error(await readError(r))
      hydrate(await r.json())
    } catch (e: any) {
      showToast(e?.message || 'Could not load the firm risk assessment')
    } finally {
      setLoading(false)
    }
  }, [hydrate])

  useEffect(() => { load() }, [load])

  const startNewVersion = async () => {
    setSaving(true)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/firm-risk-assessment`, { method: 'POST' })
      if (!r.ok) throw new Error(await readError(r))
      showToast('New draft version created', 'success')
      await load()
    } catch (e: any) {
      showToast(e?.message || 'Could not create a draft')
    } finally {
      setSaving(false)
    }
  }

  const saveDraft = async (): Promise<boolean> => {
    if (!state?.draft) return false
    setSaving(true)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/firm-risk-assessment/${state.draft.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sections,
          sectoral_ra_acknowledged: sraAck,
          sectoral_ra_date: sraDate || null,
          nra_acknowledged: nraAck,
          nra_date: nraDate || null,
          next_review_due: nextReview || null,
        }),
      })
      if (!r.ok) throw new Error(await readError(r))
      showToast('Draft saved', 'success')
      await load()
      return true
    } catch (e: any) {
      showToast(e?.message || 'Could not save the draft')
      return false
    } finally {
      setSaving(false)
    }
  }

  const approve = async () => {
    if (!state?.draft) return
    // Persist the latest edits first so approval validates what's on screen.
    const saved = await saveDraft()
    if (!saved) throw new Error('Draft could not be saved')
    const r = await authFetch(`${API_BASE_URL}/api/v1/firm-risk-assessment/${state.draft.id}/approve`, {
      method: 'POST',
    })
    if (!r.ok) {
      try {
        const body = await r.json()
        const probs: string[] = body?.detail?.problems || []
        setProblems(probs)
        throw new Error(probs.length ? 'Approval blocked — see the issues listed on the page.' : await readError(r))
      } finally {
        setShowApprove(false)
      }
    }
    setProblems([])
    setShowApprove(false)
    showToast('Firm-wide risk assessment approved', 'success')
    await load()
  }

  const exportVersion = async (id: number, version: number) => {
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/firm-risk-assessment/${id}/export`)
      if (!r.ok) throw new Error(await readError(r))
      const data = await r.json()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `firm-risk-assessment-v${version}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      showToast(e?.message || 'Export failed')
    }
  }

  if (loading) {
    return <div className="flex justify-center py-16"><Spinner /></div>
  }

  const draft = state?.draft
  const current = state?.current

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-serif text-2xl text-zinc-900">Firm-Wide Risk Assessment</h1>
          <p className="mt-1 text-sm text-zinc-500">
            MLR 2017 regulation 18 (and 18A) — written, versioned and kept up to date.
          </p>
        </div>
        {!draft && (
          <button
            onClick={startNewVersion}
            disabled={saving}
            className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-50 transition-colors"
          >
            {current ? 'Start new version' : 'Start first assessment'}
          </button>
        )}
      </div>

      {state?.review_overdue && state.review_overdue_message && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 font-medium">
          {state.review_overdue_message}
        </div>
      )}

      {current && !draft && (
        <div className="bg-white border border-zinc-200 rounded-lg p-5">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-serif text-lg text-zinc-900">Version {current.version}</span>
                <StatusBadge status={current.status} />
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                Approved {formatDateTime(current.approved_at)} · Next review due {formatDate(current.next_review_due)}
              </p>
            </div>
            <button
              onClick={() => exportVersion(current.id, current.version)}
              className="px-3 py-1.5 text-xs font-semibold rounded border border-zinc-200 text-zinc-700 hover:bg-zinc-50 transition-colors"
            >
              Export (JSON)
            </button>
          </div>
          <div className="mt-4 divide-y divide-zinc-100">
            {FWRA_SECTION_LABELS.map(({ key, label }) => {
              const s = current.sections?.[key]
              return (
                <div key={key} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-zinc-800">{label}</span>
                    <RatingBadge rating={s?.risk_level} />
                  </div>
                  <p className="mt-1 text-xs text-zinc-600 whitespace-pre-wrap">{s?.reasoning}</p>
                  {s?.mitigations && (
                    <p className="mt-1 text-xs text-zinc-500"><span className="font-semibold">Mitigations:</span> {s.mitigations}</p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {draft && (
        <>
          <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Editing draft <span className="font-semibold">version {draft.version}</span>
            {current ? ` — approving it will supersede version ${current.version}.` : '.'}
          </div>

          {problems.length > 0 && (
            <div className="rounded border border-red-200 bg-red-50 px-4 py-3">
              <div className="text-sm font-semibold text-red-800">Approval blocked</div>
              <ul className="mt-1.5 list-disc pl-5 space-y-0.5">
                {problems.map((p, i) => <li key={i} className="text-xs text-red-700">{p}</li>)}
              </ul>
            </div>
          )}

          <div className="space-y-4">
            {FWRA_SECTION_LABELS.map(({ key, label, hint }) => (
              <FirmSectionCard
                key={key}
                label={label}
                hint={hint}
                minReasoning={MIN_REASONING}
                section={sections[key] || EMPTY_SECTION}
                onChange={(s) => setSections(prev => ({ ...prev, [key]: s }))}
                disabled={saving}
              />
            ))}
          </div>

          {/* Dated acknowledgements — reg 18(6) requires the firm to take
              account of the supervisor's sectoral RA and the NRA. */}
          <div className="bg-white border border-zinc-200 rounded-lg p-5 space-y-4">
            <h3 className="font-serif text-lg text-zinc-900">External risk assessments</h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="flex items-start gap-2 text-sm text-zinc-700">
                  <input
                    type="checkbox"
                    checked={sraAck}
                    onChange={(e) => setSraAck(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-zinc-300"
                  />
                  <span>The <span className="font-semibold">SRA sectoral risk assessment</span> has been reviewed and taken into account.</span>
                </label>
                <input
                  type="date"
                  value={sraDate}
                  onChange={(e) => setSraDate(e.target.value)}
                  className="border border-zinc-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
                />
              </div>
              <div className="space-y-2">
                <label className="flex items-start gap-2 text-sm text-zinc-700">
                  <input
                    type="checkbox"
                    checked={nraAck}
                    onChange={(e) => setNraAck(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-zinc-300"
                  />
                  <span>The <span className="font-semibold">UK national risk assessment</span> has been reviewed and taken into account.</span>
                </label>
                <input
                  type="date"
                  value={nraDate}
                  onChange={(e) => setNraDate(e.target.value)}
                  className="border border-zinc-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-600 mb-1">
                Next review due (defaults to 12 months after approval)
              </label>
              <input
                type="date"
                value={nextReview}
                onChange={(e) => setNextReview(e.target.value)}
                className="border border-zinc-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={saveDraft}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium rounded border border-zinc-200 text-zinc-700 bg-white hover:bg-zinc-50 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving…' : 'Save draft'}
            </button>
            <button
              onClick={() => setShowApprove(true)}
              disabled={saving}
              className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-50 transition-colors"
            >
              Approve version {draft.version}
            </button>
          </div>
        </>
      )}

      {/* Version history */}
      {(state?.history?.length || 0) > 0 && (
        <div className="bg-white border border-zinc-200 rounded-lg p-5">
          <h3 className="font-serif text-lg text-zinc-900 mb-3">Version history</h3>
          <div className="divide-y divide-zinc-100">
            {state!.history.map(v => (
              <div key={v.id} className="py-2.5 flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-zinc-800">Version {v.version}</span>
                  <StatusBadge status={v.status} />
                </div>
                <div className="flex items-center gap-3 text-xs text-zinc-500">
                  <span>
                    {v.approved_at
                      ? `Approved ${formatDateTime(v.approved_at)}`
                      : `Created ${formatDateTime(v.created_at)}`}
                  </span>
                  <button
                    onClick={() => exportVersion(v.id, v.version)}
                    className="font-semibold text-zinc-700 hover:text-zinc-900 underline-offset-2 hover:underline"
                  >
                    Export
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <ConfirmModal
        isOpen={showApprove}
        title="Approve firm-wide risk assessment"
        message={
          <>
            Approving version {draft?.version} makes it the firm's current written risk assessment
            {current ? ` and supersedes version ${current.version}` : ''}. Every section must carry a
            risk level and reasoning of at least {MIN_REASONING} characters, and both external
            assessments must be acknowledged with dates.
          </>
        }
        confirmLabel="Approve"
        onConfirm={approve}
        onClose={() => setShowApprove(false)}
      />
    </div>
  )
}
