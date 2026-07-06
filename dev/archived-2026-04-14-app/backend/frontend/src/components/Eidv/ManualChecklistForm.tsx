// Manual verification checklist — completed by the solicitor for a
// pending manual E-IDV check. Displays the "traditional verification —
// not certified digital ID" caveat prominently.
import { FormEvent, useState } from 'react'
import { Button, Modal } from '../ui'
import { EidvCheck, ManualResultPayload } from './eidvApi'

interface ManualChecklistFormProps {
  check: EidvCheck | null // the pending manual check being completed
  caveat: string
  onSubmit: (checkId: number, payload: ManualResultPayload) => Promise<void>
  onClose: () => void
}

export default function ManualChecklistForm({
  check,
  caveat,
  onSubmit,
  onClose,
}: ManualChecklistFormProps) {
  const [documentType, setDocumentType] = useState('passport')
  const [documentNumber, setDocumentNumber] = useState('')
  const [expiryDate, setExpiryDate] = useState('')
  const [likenessConfirmed, setLikenessConfirmed] = useState(false)
  const [certifiedCopy, setCertifiedCopy] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const inputCls =
    'w-full rounded border border-zinc-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400'

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!check) return
    if (!documentNumber.trim() || !expiryDate) {
      setError('Document number and expiry date are required.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await onSubmit(check.id, {
        document_type: documentType,
        document_number: documentNumber.trim(),
        expiry_date: expiryDate,
        likeness_confirmed: likenessConfirmed,
        certified_copy_details: certifiedCopy.trim() || undefined,
        notes: notes.trim() || undefined,
      })
    } catch (err: any) {
      setError(err?.message || 'Could not record the result.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      isOpen={check !== null}
      onClose={onClose}
      title={`Manual verification — ${check?.subject_name ?? ''}`}
      size="lg"
    >
      {/* Traditional-route caveat, always visible */}
      <div className="mb-4 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
        <span className="font-semibold">Traditional verification — not certified digital ID. </span>
        {caveat}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
              Document type
            </span>
            <select
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              className={inputCls}
            >
              <option value="passport">Passport</option>
              <option value="driving_licence">Photocard driving licence</option>
              <option value="national_identity_card">National identity card</option>
              <option value="biometric_residence_permit">Biometric residence permit</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
              Document number
            </span>
            <input
              type="text"
              value={documentNumber}
              onChange={(e) => setDocumentNumber(e.target.value)}
              className={inputCls}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
              Expiry date
            </span>
            <input
              type="date"
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
              className={inputCls}
            />
            <span className="mt-1 block text-[11px] text-zinc-400">
              An expired document sends the check to review rather than pass.
            </span>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
              Certified copy details (if not seen in person)
            </span>
            <input
              type="text"
              value={certifiedCopy}
              onChange={(e) => setCertifiedCopy(e.target.value)}
              placeholder="Who certified it, capacity, date"
              className={inputCls}
            />
          </label>
        </div>

        <label className="flex items-start gap-2 text-sm text-zinc-700">
          <input
            type="checkbox"
            checked={likenessConfirmed}
            onChange={(e) => setLikenessConfirmed(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            I confirm the photograph is a true likeness of the subject, checked in person or over
            live video. <span className="text-zinc-400">(Unticked records a failed check.)</span>
          </span>
        </label>

        <label className="block text-sm">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            Notes
          </span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Name discrepancies, prior names, further observations…"
            className={inputCls}
          />
        </label>

        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            Record result
          </Button>
        </div>
      </form>
    </Modal>
  )
}
