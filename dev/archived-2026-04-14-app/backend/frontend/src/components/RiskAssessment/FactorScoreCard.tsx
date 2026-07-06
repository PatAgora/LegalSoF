// One card per LSAG factor set on a client/matter risk assessment:
// 1-3 score pills plus mandatory written reasoning (a bare score with
// no narrative is the tick-box approach the SRA penalises).
import { CmraFactor, ReasoningTextarea, ScorePills } from './shared'

export default function FactorScoreCard({
  label, hint, factor, onChange, disabled,
}: {
  label: string
  hint: string
  factor: CmraFactor
  onChange: (f: CmraFactor) => void
  disabled?: boolean
}) {
  return (
    <div className="bg-white border border-zinc-200 rounded-lg p-5 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900">{label}</h3>
          <p className="mt-0.5 text-xs text-zinc-500 leading-snug">{hint}</p>
        </div>
        <ScorePills
          value={factor.score}
          disabled={disabled}
          onChange={(score) => onChange({ ...factor, score })}
        />
      </div>
      <ReasoningTextarea
        label="Reasoning"
        value={factor.reasoning || ''}
        rows={2}
        disabled={disabled}
        placeholder="Why this score applies to this client/matter."
        onChange={(reasoning) => onChange({ ...factor, reasoning })}
      />
    </div>
  )
}
