// The single matter-status badge, used everywhere a matter status is
// shown (Matters list, Dashboard, matter detail, Compliance views) so
// the status reads identically across the whole app. The status value
// is auto-derived on the backend - see derive_matter_status().

export const MATTER_STATUSES = [
  'Awaiting Review',
  'Under Review',
  'Sent to Compliance',
  'Returned from Compliance',
  'Verified',
] as const;

const STYLES: Record<string, { label: string; cls: string; dot: string }> = {
  'Awaiting Review': { label: 'Awaiting Review', cls: 'bg-zinc-50 text-zinc-600 ring-zinc-200', dot: 'bg-zinc-400' },
  'Under Review': { label: 'Under Review', cls: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
  'Sent to Compliance': { label: 'Sent to Compliance', cls: 'bg-blue-50 text-blue-700 ring-blue-200', dot: 'bg-blue-500' },
  'Returned from Compliance': { label: 'Returned from Compliance', cls: 'bg-red-50 text-red-700 ring-red-200', dot: 'bg-red-500' },
  'Verified': { label: 'Verified', cls: 'bg-green-50 text-green-700 ring-green-200', dot: 'bg-green-500' },
  // Lifecycle statuses that arrive in snake_case from the backend.
  'draft': { label: 'Draft', cls: 'bg-zinc-50 text-zinc-600 ring-zinc-200', dot: 'bg-zinc-400' },
  'awaiting_client': { label: 'Awaiting Client', cls: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
  'client_uploading': { label: 'Client Uploading', cls: 'bg-blue-50 text-blue-700 ring-blue-200', dot: 'bg-blue-500' },
  'queries_raised': { label: 'Queries Raised', cls: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
};

// Present an unrecognised status honestly: title-cased raw value in a
// neutral chip - it must never masquerade as a known workflow state.
function titleCase(s: string): string {
  return s
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function MatterStatusBadge({ status, className = '' }: { status?: string | null; className?: string }) {
  const key = status ?? 'Awaiting Review';
  const s = STYLES[key]
    || STYLES[String(key).toLowerCase()]
    || { label: titleCase(String(key)), cls: 'bg-zinc-50 text-zinc-600 ring-zinc-200', dot: 'bg-zinc-400' };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold ring-1 ring-inset ${s.cls} ${className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden="true" />
      {s.label}
    </span>
  );
}
