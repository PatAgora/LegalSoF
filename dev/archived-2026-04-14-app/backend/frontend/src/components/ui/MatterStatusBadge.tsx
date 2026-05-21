// The single matter-status badge, used everywhere a matter status is
// shown (Matters list, Dashboard, matter detail, Compliance views) so
// the status reads identically across the whole app. The status value
// is auto-derived on the backend — see derive_matter_status().

export const MATTER_STATUSES = [
  'Draft',
  'Under Review',
  'Sent to Compliance',
  'Returned from Compliance',
  'Verified',
] as const;

const STYLES: Record<string, { cls: string; dot: string }> = {
  'Draft': { cls: 'bg-zinc-50 text-zinc-600 ring-zinc-200', dot: 'bg-zinc-400' },
  'Under Review': { cls: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
  'Sent to Compliance': { cls: 'bg-blue-50 text-blue-700 ring-blue-200', dot: 'bg-blue-500' },
  'Returned from Compliance': { cls: 'bg-red-50 text-red-700 ring-red-200', dot: 'bg-red-500' },
  'Verified': { cls: 'bg-green-50 text-green-700 ring-green-200', dot: 'bg-green-500' },
};

export default function MatterStatusBadge({ status, className = '' }: { status?: string | null; className?: string }) {
  const label = status && STYLES[status] ? status : 'Draft';
  const s = STYLES[label];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold ring-1 ring-inset ${s.cls} ${className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}
