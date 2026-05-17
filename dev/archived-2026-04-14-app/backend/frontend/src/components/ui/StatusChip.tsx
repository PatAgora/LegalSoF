// CDD-style status chip: coloured dot + uppercase label in a pill.
// Used for verification verdicts and severity badges. Same colour
// palette as <Badge> but with the leading dot and severity-mapping
// helpers baked in.
import { HTMLAttributes } from 'react';

type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
type Verdict = 'Verified' | 'Suspicious' | 'LikelyTampered' | string;

interface StatusChipProps extends HTMLAttributes<HTMLSpanElement> {
  // EITHER pass a verdict (the chip picks colour + label) OR pass a
  // severity. Severity takes precedence when both are set.
  severity?: Severity;
  verdict?: Verdict;
  // Override the label text shown after the dot.
  label?: string;
}

const SEVERITY_STYLE: Record<Severity, { wrap: string; dot: string }> = {
  critical: { wrap: 'bg-red-50    text-red-700    ring-red-200/80',    dot: 'bg-red-500' },
  high:     { wrap: 'bg-amber-50  text-amber-700  ring-amber-200/80',  dot: 'bg-amber-500' },
  medium:   { wrap: 'bg-zinc-50   text-zinc-700   ring-zinc-200/80',   dot: 'bg-zinc-400' },
  low:      { wrap: 'bg-zinc-50   text-zinc-600   ring-zinc-200/80',   dot: 'bg-zinc-300' },
  info:     { wrap: 'bg-blue-50   text-blue-700   ring-blue-200/80',   dot: 'bg-blue-500' },
};

const VERDICT_TO_SEVERITY: Record<string, { severity: Severity; label: string }> = {
  Verified:        { severity: 'info',     label: 'VERIFIED' },
  Suspicious:      { severity: 'high',     label: 'SUSPICIOUS' },
  LikelyTampered:  { severity: 'critical', label: 'LIKELY TAMPERED' },
};

export default function StatusChip({ severity, verdict, label, className = '', ...rest }: StatusChipProps) {
  let style = severity ? SEVERITY_STYLE[severity] : undefined;
  let text = label;

  if (!style && verdict) {
    const mapped = VERDICT_TO_SEVERITY[verdict] || { severity: 'medium' as Severity, label: verdict.toUpperCase() };
    style = SEVERITY_STYLE[mapped.severity];
    text = text ?? mapped.label;
  }
  if (!style) {
    style = SEVERITY_STYLE.medium;
    text = text ?? 'UNKNOWN';
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2.5 py-0.5 text-[11px] font-semibold tracking-[0.06em] ring-1 ring-inset ${style.wrap} ${className}`}
      {...rest}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {text}
    </span>
  );
}
