// Verification results table: status chips, DIATF badge / absence,
// per-check outcomes and audit info.
import { Badge, Button, StatusChip, Table, Tbody, Td, Th, Thead, Tr } from '../ui'
import { EidvCheck, SUBJECT_TYPE_LABELS } from './eidvApi'

interface EidvResultsListProps {
  checks: EidvCheck[]
  onCompleteManual: (check: EidvCheck) => void
}

function fmtDateTime(s: string | null): string {
  if (!s) return '-'
  const d = new Date(s)
  return isNaN(d.getTime())
    ? s
    : d.toLocaleString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
}

const STATUS_SEVERITY: Record<EidvCheck['status'], 'critical' | 'high' | 'medium' | 'info'> = {
  failed: 'critical',
  review: 'high',
  pending: 'medium',
  passed: 'info',
}

function ChecksSummary({ checks }: { checks: Record<string, string> | null }) {
  if (!checks) return <span className="text-xs text-zinc-400">—</span>
  const entries = Object.entries(checks).filter(
    ([, v]) => v !== 'not_applicable' && v !== 'not_checked',
  )
  if (entries.length === 0) return <span className="text-xs text-zinc-400">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {entries.map(([k, v]) => (
        <Badge
          key={k}
          variant={v === 'passed' ? 'success' : v === 'failed' ? 'danger' : v === 'review' ? 'warning' : 'default'}
        >
          {k.replace('_', ' ')}: {v}
        </Badge>
      ))}
    </div>
  )
}

export default function EidvResultsList({ checks, onCompleteManual }: EidvResultsListProps) {
  if (checks.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-zinc-500">
        No identity verifications on this matter yet.
      </p>
    )
  }

  return (
    <Table>
      <Thead>
        <Tr>
          <Th>Subject</Th>
          <Th>Type</Th>
          <Th>Method</Th>
          <Th>Status</Th>
          <Th>Checks</Th>
          <Th>Started / completed</Th>
          <Th className="text-right">Action</Th>
        </Tr>
      </Thead>
      <Tbody>
        {checks.map((check) => (
          <Tr key={check.id}>
            <Td>
              <div className="font-medium text-zinc-900">{check.subject_name}</div>
              {check.subject_dob && (
                <div className="text-xs text-zinc-400">DOB {check.subject_dob}</div>
              )}
            </Td>
            <Td>{SUBJECT_TYPE_LABELS[check.subject_type] || check.subject_type}</Td>
            <Td>
              <div className="flex flex-col items-start gap-1">
                <span className="text-xs">
                  {check.provider === 'manual' ? 'Manual (traditional)' : check.provider}
                </span>
                {check.diatf_certified ? (
                  <Badge variant="success">DIATF-CERTIFIED</Badge>
                ) : (
                  <Badge variant="warning">NOT DIATF-CERTIFIED</Badge>
                )}
              </div>
            </Td>
            <Td>
              <StatusChip
                severity={STATUS_SEVERITY[check.status]}
                label={check.status.toUpperCase()}
              />
            </Td>
            <Td>
              <ChecksSummary checks={check.checks} />
            </Td>
            <Td className="text-xs text-zinc-500">
              <div>Started {fmtDateTime(check.created_at)}</div>
              {check.completed_at && <div>Completed {fmtDateTime(check.completed_at)}</div>}
            </Td>
            <Td className="text-right">
              {check.provider === 'manual' && check.status === 'pending' ? (
                <Button size="sm" variant="secondary" onClick={() => onCompleteManual(check)}>
                  Complete checklist
                </Button>
              ) : (
                <span className="text-xs text-zinc-300">—</span>
              )}
            </Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  )
}
