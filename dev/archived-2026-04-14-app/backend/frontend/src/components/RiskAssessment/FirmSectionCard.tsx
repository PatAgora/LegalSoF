// One editable card per mandatory FWRA risk-factor section
// (MLR 2017 reg 18(2)(a) + reg 18A proliferation financing).
import { FwraSection, ReasoningTextarea } from './shared'

const LEVELS = ['low', 'medium', 'high']

export default function FirmSectionCard({
  label, hint, section, onChange, disabled, minReasoning = 50,
}: {
  label: string
  hint: string
  section: FwraSection
  onChange: (s: FwraSection) => void
  disabled?: boolean
  minReasoning?: number
}) {
  return (
    <div className="bg-white border border-zinc-200 rounded-lg p-5 space-y-4">
      <div>
        <h3 className="font-serif text-lg text-zinc-900">{label}</h3>
        <p className="mt-0.5 text-xs text-zinc-500 leading-snug">{hint}</p>
      </div>

      <div>
        <label className="block text-xs font-semibold text-zinc-600 mb-1">Risk level</label>
        <select
          value={section.risk_level || ''}
          disabled={disabled}
          onChange={(e) => onChange({ ...section, risk_level: e.target.value })}
          className="w-40 border border-zinc-200 rounded px-2.5 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-300 disabled:bg-zinc-50 disabled:text-zinc-500"
        >
          <option value="">Select…</option>
          {LEVELS.map(l => (
            <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>
          ))}
        </select>
      </div>

      <ReasoningTextarea
        label="Reasoning"
        value={section.reasoning || ''}
        minLength={minReasoning}
        rows={4}
        disabled={disabled}
        placeholder="Why this risk level applies to this firm — specific, not templated. The SRA penalises unreasoned assessments."
        onChange={(v) => onChange({ ...section, reasoning: v })}
      />

      <div>
        <label className="block text-xs font-semibold text-zinc-600 mb-1">Mitigations</label>
        <textarea
          value={section.mitigations || ''}
          disabled={disabled}
          onChange={(e) => onChange({ ...section, mitigations: e.target.value })}
          rows={2}
          placeholder="Controls and procedures that mitigate this risk."
          className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300 disabled:bg-zinc-50 disabled:text-zinc-500"
        />
      </div>
    </div>
  )
}
