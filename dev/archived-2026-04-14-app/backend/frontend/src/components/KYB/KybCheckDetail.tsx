// Full view of one KYB check: company profile card, officers table,
// and the PSC / beneficial-owner tree (indented list), with the
// reg 30A "Report discrepancy" action and per-PSC "Verify identity"
// links into E-IDV.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card, RationaleModal, Table, Tbody, Td, Th, Thead, Tr } from '../ui'
import { KybCheck, KybPsc } from './kybApi'

interface KybCheckDetailProps {
  matterId: string
  check: KybCheck
  onRefresh: (checkId: number) => Promise<void>
  onReportDiscrepancy: (checkId: number, details: string) => Promise<void>
  refreshing: boolean
}

function fmtDate(s: string | null): string {
  if (!s) return '-'
  const d = new Date(s)
  return isNaN(d.getTime())
    ? s
    : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function boolFlag(v: boolean | null | undefined, badLabel: string): JSX.Element | null {
  if (!v) return null
  return <Badge variant="danger">{badLabel}</Badge>
}

function PscRow({ psc, matterId }: { psc: KybPsc; matterId: string }) {
  const ceased = Boolean(psc.ceased_on)
  return (
    <li className={`rounded border border-zinc-200 bg-white p-3 ${ceased ? 'opacity-60' : ''}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-zinc-900">{psc.name || 'Unnamed PSC'}</span>
        <Badge variant={psc.is_individual ? 'info' : 'default'}>
          {psc.is_individual ? 'INDIVIDUAL' : 'CORPORATE ENTITY'}
        </Badge>
        {psc.ownership_band && <Badge variant="warning">{psc.ownership_band}</Badge>}
        {ceased && <Badge variant="default">CEASED {fmtDate(psc.ceased_on)}</Badge>}
      </div>

      {/* natures_of_control, human-readable */}
      <ul className="mt-2 ml-4 list-disc space-y-0.5 text-xs text-zinc-600">
        {psc.natures_described.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>

      {/* Corporate PSCs point at another company — the duty flows through */}
      {psc.identification && (
        <div className="mt-2 ml-4 border-l-2 border-zinc-200 pl-3 text-xs text-zinc-500">
          {psc.identification.legal_form && <div>Legal form: {psc.identification.legal_form}</div>}
          {psc.identification.registration_number && (
            <div>Registration no: {psc.identification.registration_number}</div>
          )}
          <div className="mt-0.5 text-zinc-400">
            Corporate PSC — identify and verify the individuals behind this entity.
          </div>
        </div>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-zinc-500">
        {psc.nationality && <span>Nationality: {psc.nationality}</span>}
        {psc.country_of_residence && <span>Resides: {psc.country_of_residence}</span>}
        {psc.date_of_birth && <span>DOB: {psc.date_of_birth}</span>}
        {psc.notified_on && <span>Notified: {fmtDate(psc.notified_on)}</span>}
      </div>

      {psc.requires_individual_verification && (
        <div className="mt-2 flex items-center gap-2 rounded bg-blue-50 px-3 py-2 text-xs text-blue-800">
          <span>
            Beneficial owner — the PSC register is a cross-check only, not verification.
          </span>
          <Link
            to={`/matters/${matterId}/eidv`}
            className="font-semibold underline hover:text-blue-900"
          >
            Verify identity (E-IDV) →
          </Link>
        </div>
      )}
    </li>
  )
}

export default function KybCheckDetail({
  matterId,
  check,
  onRefresh,
  onReportDiscrepancy,
  refreshing,
}: KybCheckDetailProps) {
  const [discrepancyOpen, setDiscrepancyOpen] = useState(false)

  const profile = check.profile
  const officers = check.officers?.items ?? []
  const pscs = check.pscs?.items ?? []

  return (
    <div className="space-y-4">
      {/* ---- Company profile card ---- */}
      <Card>
        <Card.Header>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-zinc-900">
                {check.company_name || check.company_number}
              </h3>
              <span className="font-mono text-xs text-zinc-500">{check.company_number}</span>
              {check.status === 'discrepancy_reported' && (
                <Badge variant="danger">PSC DISCREPANCY REPORTED</Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                loading={refreshing}
                onClick={() => onRefresh(check.id)}
              >
                Refresh from Companies House
              </Button>
              <Button size="sm" variant="danger" onClick={() => setDiscrepancyOpen(true)}>
                Report PSC discrepancy
              </Button>
            </div>
          </div>
        </Card.Header>
        <Card.Body>
          {profile ? (
            <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-400">Status</dt>
                <dd className="mt-0.5 flex items-center gap-2">
                  <Badge variant={profile.company_status === 'active' ? 'success' : 'danger'}>
                    {(profile.company_status || 'unknown').toUpperCase()}
                  </Badge>
                  {boolFlag(profile.has_insolvency_history, 'INSOLVENCY HISTORY')}
                  {boolFlag(profile.has_charges, 'CHARGES REGISTERED')}
                  {boolFlag(profile.registered_office_is_in_dispute, 'OFFICE IN DISPUTE')}
                  {boolFlag(profile.accounts_overdue, 'ACCOUNTS OVERDUE')}
                  {boolFlag(profile.confirmation_statement_overdue, 'CONFIRMATION OVERDUE')}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-400">Type / jurisdiction</dt>
                <dd className="mt-0.5 text-zinc-700">
                  {profile.type || '-'} · {profile.jurisdiction || '-'}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-400">Incorporated</dt>
                <dd className="mt-0.5 text-zinc-700">{fmtDate(profile.date_of_creation)}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-zinc-400">Registered office</dt>
                <dd className="mt-0.5 text-zinc-700">{profile.registered_office_address || '-'}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-400">SIC codes</dt>
                <dd className="mt-0.5 font-mono text-xs text-zinc-700">
                  {profile.sic_codes.length ? profile.sic_codes.join(', ') : '-'}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-zinc-500">No profile data captured.</p>
          )}
          <p className="mt-3 text-xs text-zinc-400">
            Snapshot taken {fmtDate(check.created_at)}
            {check.refreshed_at ? ` · refreshed ${fmtDate(check.refreshed_at)}` : ''}
          </p>
        </Card.Body>
      </Card>

      {/* ---- Recorded discrepancy (reg 30A) ---- */}
      {check.psc_discrepancy && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <div className="font-semibold text-red-900">
            Material PSC discrepancy on record (MLR 2017 reg 30A)
          </div>
          <p className="mt-1 whitespace-pre-wrap">{check.psc_discrepancy}</p>
          <p className="mt-1 text-xs text-red-700">
            Recorded {fmtDate(check.psc_discrepancy_reported_at)}. The firm must report material
            discrepancies to Companies House — this record evidences the finding and the report.
          </p>
        </div>
      )}

      {/* ---- PSC / beneficial owner tree ---- */}
      <Card>
        <Card.Header>
          <h3 className="text-sm font-semibold text-zinc-900">
            Persons with significant control ({check.pscs?.active_count ?? 0} active)
          </h3>
        </Card.Header>
        <Card.Body>
          {pscs.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No PSCs on the register for this company. Establish ownership and control by other
              means and record your findings.
            </p>
          ) : (
            <ul className="space-y-2">
              {pscs.map((psc, i) => (
                <PscRow key={`${psc.name}-${i}`} psc={psc} matterId={matterId} />
              ))}
            </ul>
          )}
        </Card.Body>
      </Card>

      {/* ---- Officers table ---- */}
      <Card>
        <Card.Header>
          <h3 className="text-sm font-semibold text-zinc-900">
            Officers ({check.officers?.active_count ?? 0} active)
          </h3>
        </Card.Header>
        <Card.Body>
          {officers.length === 0 ? (
            <p className="text-sm text-zinc-500">No officers returned.</p>
          ) : (
            <Table>
              <Thead>
                <Tr>
                  <Th>Name</Th>
                  <Th>Role</Th>
                  <Th>Appointed</Th>
                  <Th>Resigned</Th>
                  <Th>Nationality</Th>
                  <Th>DOB</Th>
                </Tr>
              </Thead>
              <Tbody>
                {officers.map((o, i) => (
                  <Tr key={`${o.name}-${i}`} className={o.resigned_on ? 'opacity-60' : ''}>
                    <Td className="font-medium text-zinc-900">{o.name || '-'}</Td>
                    <Td>{o.officer_role || '-'}</Td>
                    <Td>{fmtDate(o.appointed_on)}</Td>
                    <Td>{o.resigned_on ? fmtDate(o.resigned_on) : '-'}</Td>
                    <Td>{o.nationality || '-'}</Td>
                    <Td className="font-mono text-xs">{o.date_of_birth || '-'}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </Card.Body>
      </Card>

      {/* ---- Report discrepancy modal (reg 30A) ---- */}
      <RationaleModal
        isOpen={discrepancyOpen}
        title="Report a material PSC discrepancy (reg 30A)"
        description={
          'Record the material discrepancy between your CDD findings and the Companies House ' +
          'PSC register, and confirm the firm has reported (or will report) it to Companies ' +
          'House. The platform records the discrepancy — the report itself must be made by a ' +
          'person at the firm via the Companies House discrepancy-reporting service.'
        }
        minLength={20}
        confirmLabel="Record discrepancy"
        destructive
        placeholder="What was found, who it concerns, and confirmation of the report to Companies House…"
        onConfirm={async (text) => {
          await onReportDiscrepancy(check.id, text)
          setDiscrepancyOpen(false)
        }}
        onClose={() => setDiscrepancyOpen(false)}
      />
    </div>
  )
}
