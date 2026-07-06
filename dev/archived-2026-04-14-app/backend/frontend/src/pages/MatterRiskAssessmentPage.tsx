// Client & Matter Risk Assessment (MLR 2017 reg 28(12)-(13)) for one
// matter. Tabbed client/matter forms: five LSAG factor sets scored 1-3
// with mandatory reasoning, the reg 28(13) considerations, live
// computed overall rating with EDD banner, complete flow and history.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { API_BASE_URL, authFetch } from '../lib/api'
import { showToast } from '../lib/toast'
import { formatDate, formatDateTime } from '../lib/format'
import { ConfirmModal } from '../components/ui/RationaleModal'
import Spinner from '../components/ui/Spinner'
import FactorScoreCard from '../components/RiskAssessment/FactorScoreCard'
import {
  Cmra, CmraFactor, CMRA_FACTOR_LABELS, REG28_LABELS,
  RatingBadge, StatusBadge, EddBanner, previewCmraScoring,
} from '../components/RiskAssessment/shared'

type TabType = 'client' | 'matter'

interface MatterRAState {
  assessments: Cmra[]
  current: Partial<Record<TabType, Cmra>>
  drafts: Partial<Record<TabType, Cmra>>
  cmra_complete: boolean
}

const EMPTY_FACTOR: CmraFactor = { score: null, reasoning: '' }

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

export default function MatterRiskAssessmentPage() {
  const { matterId } = useParams<{ matterId: string }>()
  const [state, setState] = useState<MatterRAState | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [tab, setTab] = useState<TabType>('client')
  const [showComplete, setShowComplete] = useState(false)
  const [problems, setProblems] = useState<string[]>([])

  // Editable copy of the active tab's draft.
  const [factors, setFactors] = useState<Record<string, CmraFactor>>({})
  const [reg28, setReg28] = useState<Record<string, string>>({})
  const [isPep, setIsPep] = useState(false)
  const [countries, setCountries] = useState('')
  const [complexity, setComplexity] = useState(false)

  const base = `${API_BASE_URL}/api/v1/matters/${matterId}/risk-assessments`

  const hydrateDraft = useCallback((draft: Cmra | undefined) => {
    const f: Record<string, CmraFactor> = {}
    for (const { key } of CMRA_FACTOR_LABELS) {
      f[key] = { ...EMPTY_FACTOR, ...(draft?.factors?.[key] || {}) }
    }
    setFactors(f)
    const r: Record<string, string> = {}
    for (const { key } of REG28_LABELS) r[key] = String(draft?.reg28_considerations?.[key] || '')
    setReg28(r)
    setIsPep(Boolean(draft?.context_flags?.client_is_pep))
    setCountries((draft?.context_flags?.geography_countries || []).join(', '))
    setComplexity(Boolean(draft?.context_flags?.unusual_complexity))
    setProblems([])
  }, [])

  const load = useCallback(async (activeTab: TabType) => {
    try {
      const r = await authFetch(base)
      if (!r.ok) throw new Error(await readError(r))
      const data: MatterRAState = await r.json()
      setState(data)
      hydrateDraft(data.drafts?.[activeTab])
    } catch (e: any) {
      showToast(e?.message || 'Could not load risk assessments')
    } finally {
      setLoading(false)
    }
  }, [base, hydrateDraft])

  useEffect(() => { load(tab) }, [load]) // eslint-disable-line react-hooks/exhaustive-deps

  const switchTab = (t: TabType) => {
    setTab(t)
    hydrateDraft(state?.drafts?.[t])
  }

  const contextFlags = useMemo(() => ({
    client_is_pep: isPep,
    geography_countries: countries.split(',').map(c => c.trim()).filter(Boolean),
    unusual_complexity: complexity,
  }), [isPep, countries, complexity])

  // Live preview — mirrors the backend's default weights; the server
  // recomputes authoritatively on every save.
  const preview = useMemo(() => previewCmraScoring(factors, contextFlags), [factors, contextFlags])

  const draft = state?.drafts?.[tab]
  const current = state?.current?.[tab]
  const history = (state?.assessments || []).filter(a => a.assessment_type === tab)

  const startDraft = async () => {
    setSaving(true)
    try {
      const r = await authFetch(base, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          assessment_type: tab,
          factors: current?.factors || {},
          reg28_considerations: current?.reg28_considerations || {},
          context_flags: current?.context_flags || {},
        }),
      })
      if (!r.ok) throw new Error(await readError(r))
      showToast('Draft assessment created', 'success')
      await load(tab)
    } catch (e: any) {
      showToast(e?.message || 'Could not create the draft')
    } finally {
      setSaving(false)
    }
  }

  const buildPayload = () => ({
    factors,
    reg28_considerations: reg28,
    context_flags: contextFlags,
  })

  const saveDraft = async (): Promise<boolean> => {
    if (!draft) return false
    setSaving(true)
    try {
      const r = await authFetch(`${base}/${draft.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      })
      if (!r.ok) throw new Error(await readError(r))
      showToast('Draft saved', 'success')
      await load(tab)
      return true
    } catch (e: any) {
      showToast(e?.message || 'Could not save the draft')
      return false
    } finally {
      setSaving(false)
    }
  }

  const complete = async () => {
    if (!draft) return
    const saved = await saveDraft()
    if (!saved) throw new Error('Draft could not be saved')
    const r = await authFetch(`${base}/${draft.id}/complete`, { method: 'POST' })
    if (!r.ok) {
      try {
        const body = await r.json()
        const probs: string[] = body?.detail?.problems || []
        setProblems(probs)
        throw new Error(probs.length ? 'Completion blocked — see the issues listed on the page.' : await readError(r))
      } finally {
        setShowComplete(false)
      }
    }
    setProblems([])
    setShowComplete(false)
    showToast('Risk assessment completed', 'success')
    await load(tab)
  }

  if (loading) {
    return <div className="flex justify-center py-16"><Spinner /></div>
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <Link
          to={`/matters/${matterId}`}
          className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-700 transition-colors"
        >
          <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to matter
        </Link>
        <h1 className="mt-1 font-serif text-2xl text-zinc-900">Client & Matter Risk Assessment</h1>
        <p className="mt-1 text-sm text-zinc-500">
          MLR 2017 regulation 28(12)-(13) — a written, reasoned assessment at both client and matter level.
        </p>
      </div>

      {!state?.cmra_complete && (
        <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Both a <span className="font-semibold">client</span> and a{' '}
          <span className="font-semibold">matter</span> assessment must be completed before the
          SoF assessment can run on this matter.
        </div>
      )}

      {/* Client / Matter tabs */}
      <div className="border-b border-zinc-200 flex gap-6">
        {(['client', 'matter'] as TabType[]).map(t => (
          <button
            key={t}
            onClick={() => switchTab(t)}
            className={`pb-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? 'border-zinc-900 text-zinc-900'
                : 'border-transparent text-zinc-500 hover:text-zinc-800'
            }`}
          >
            {t === 'client' ? 'Client assessment' : 'Matter assessment'}
            {state?.current?.[t] && <span className="ml-1.5 text-green-600">✓</span>}
          </button>
        ))}
      </div>

      {/* Current completed assessment for this tab */}
      {current && (
        <div className="bg-white border border-zinc-200 rounded-lg p-5">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-zinc-800">Current assessment</span>
              <StatusBadge status={current.status} />
              <RatingBadge rating={current.overall_rating} />
            </div>
            <span className="text-xs text-zinc-500">
              Completed {formatDateTime(current.completed_at)} · Review due {formatDate(current.review_due)}
            </span>
          </div>
          {current.edd_required && (
            <div className="mt-3"><EddBanner triggers={current.edd_triggers || []} /></div>
          )}
        </div>
      )}

      {!draft ? (
        <button
          onClick={startDraft}
          disabled={saving}
          className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-50 transition-colors"
        >
          {current ? 'Start revised assessment' : `Start ${tab} assessment`}
        </button>
      ) : (
        <>
          {problems.length > 0 && (
            <div className="rounded border border-red-200 bg-red-50 px-4 py-3">
              <div className="text-sm font-semibold text-red-800">Completion blocked</div>
              <ul className="mt-1.5 list-disc pl-5 space-y-0.5">
                {problems.map((p, i) => <li key={i} className="text-xs text-red-700">{p}</li>)}
              </ul>
            </div>
          )}

          {/* Factor cards */}
          <div className="space-y-4">
            {CMRA_FACTOR_LABELS.map(({ key, label, hint }) => (
              <FactorScoreCard
                key={`${tab}-${key}`}
                label={label}
                hint={hint}
                factor={factors[key] || EMPTY_FACTOR}
                onChange={(f) => setFactors(prev => ({ ...prev, [key]: f }))}
                disabled={saving}
              />
            ))}
          </div>

          {/* Reg 28(13) mandatory considerations */}
          <div className="bg-white border border-zinc-200 rounded-lg p-5 space-y-4">
            <div>
              <h3 className="font-serif text-lg text-zinc-900">Mandatory considerations</h3>
              <p className="mt-0.5 text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Required by Regulation 28(13)
              </p>
            </div>
            {REG28_LABELS.map(({ key, label }) => (
              <div key={key}>
                <label className="block text-xs font-semibold text-zinc-600 mb-1">{label} (required)</label>
                <textarea
                  value={reg28[key] || ''}
                  onChange={(e) => setReg28(prev => ({ ...prev, [key]: e.target.value }))}
                  rows={2}
                  disabled={saving}
                  className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300 disabled:bg-zinc-50"
                />
              </div>
            ))}
          </div>

          {/* Context flags feeding the EDD auto-triggers */}
          <div className="bg-white border border-zinc-200 rounded-lg p-5 space-y-3">
            <h3 className="font-serif text-lg text-zinc-900">Risk context</h3>
            <label className="flex items-start gap-2 text-sm text-zinc-700">
              <input
                type="checkbox"
                checked={isPep}
                onChange={(e) => setIsPep(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-zinc-300"
              />
              <span>The client (or a beneficial owner) is a <span className="font-semibold">politically exposed person</span>.</span>
            </label>
            <div>
              <label className="block text-xs font-semibold text-zinc-600 mb-1">
                Countries connected to the client, funds or transaction (ISO codes, comma-separated)
              </label>
              <input
                type="text"
                value={countries}
                onChange={(e) => setCountries(e.target.value)}
                placeholder="e.g. GB, FR"
                className="w-full sm:w-80 border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
            </div>
            <label className="flex items-start gap-2 text-sm text-zinc-700">
              <input
                type="checkbox"
                checked={complexity}
                onChange={(e) => setComplexity(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-zinc-300"
              />
              <span>The transaction is <span className="font-semibold">unusually large or complex</span> for this client.</span>
            </label>
          </div>

          {/* Live computed rating + EDD banner */}
          <div className="bg-white border border-zinc-200 rounded-lg p-5 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="font-serif text-lg text-zinc-900">Computed overall rating</h3>
                <p className="mt-0.5 text-xs text-zinc-500">
                  Weighted across the five factor sets; a single high factor forces at least medium.
                  The server recomputes on save.
                </p>
              </div>
              <RatingBadge rating={preview.rating} />
            </div>
            <EddBanner triggers={preview.triggers} />
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
              onClick={() => setShowComplete(true)}
              disabled={saving}
              className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-50 transition-colors"
            >
              Complete assessment
            </button>
          </div>
        </>
      )}

      {/* History for this tab */}
      {history.length > 0 && (
        <div className="bg-white border border-zinc-200 rounded-lg p-5">
          <h3 className="font-serif text-lg text-zinc-900 mb-3">History</h3>
          <div className="divide-y divide-zinc-100">
            {history.map(a => (
              <div key={a.id} className="py-2.5 flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <StatusBadge status={a.status} />
                  <RatingBadge rating={a.overall_rating} />
                  {a.edd_required && (
                    <span className="text-[11px] font-semibold text-red-700">EDD</span>
                  )}
                </div>
                <span className="text-xs text-zinc-500">
                  {a.completed_at
                    ? `Completed ${formatDateTime(a.completed_at)} · Review due ${formatDate(a.review_due)}`
                    : `Created ${formatDateTime(a.created_at)}`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <ConfirmModal
        isOpen={showComplete}
        title={`Complete ${tab} assessment`}
        message={
          <>
            Completing records this as the current written {tab} risk assessment with an overall
            rating of <span className="font-semibold uppercase">{preview.rating}</span>
            {preview.triggers.length > 0 ? ' and EDD required' : ''}. Every factor needs a score and
            written reasoning, and all Regulation 28(13) considerations must be addressed.
          </>
        }
        confirmLabel="Complete"
        onConfirm={complete}
        onClose={() => setShowComplete(false)}
      />
    </div>
  )
}
