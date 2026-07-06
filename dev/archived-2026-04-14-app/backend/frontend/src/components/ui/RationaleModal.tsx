// RationaleModal - replaces window.prompt() for compliance-grade
// rationale capture. Textarea with a live character counter (same
// pattern as the admin-override rationale box), minimum-length
// validation, and inline error display that NEVER discards the typed
// text on failure.
//
// ConfirmModal - replaces window.confirm() for confirmations, with an
// optional typed-confirmation mode (the user must type a word, e.g.
// ARCHIVE, before the destructive action is enabled).
import { useEffect, useState } from 'react';
import Modal from './Modal';

interface RationaleModalProps {
  isOpen: boolean;
  title: string;
  description?: string;
  minLength?: number;
  confirmLabel: string;
  destructive?: boolean;
  placeholder?: string;
  // May throw / reject - the message is shown inline and the typed
  // text is preserved. The caller closes the modal on success.
  onConfirm: (text: string) => Promise<void> | void;
  onClose: () => void;
}

export function RationaleModal({
  isOpen,
  title,
  description,
  minLength = 10,
  confirmLabel,
  destructive,
  placeholder,
  onConfirm,
  onClose,
}: RationaleModalProps) {
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Reset when the modal is (re)opened for a fresh action.
  useEffect(() => {
    if (isOpen) {
      setText('');
      setError(null);
      setSubmitting(false);
    }
  }, [isOpen]);

  const handleConfirm = async () => {
    const trimmed = text.trim();
    if (trimmed.length < minLength) {
      setError(`Please enter at least ${minLength} characters.`);
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await onConfirm(trimmed);
    } catch (e: any) {
      setError(e?.message || 'The request failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={submitting ? () => {} : onClose}
      title={title}
      size="lg"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-zinc-600 bg-white border border-zinc-200 rounded hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting || text.trim().length < minLength}
            className={`px-4 py-2 text-sm font-semibold rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${
              destructive
                ? 'bg-red-700 text-white hover:bg-red-800'
                : 'bg-zinc-900 text-white hover:bg-zinc-800'
            }`}
          >
            {submitting ? 'Saving…' : confirmLabel}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        {description && <p className="text-sm text-zinc-600 leading-snug">{description}</p>}
        <div>
          <div className="flex items-baseline justify-between mb-1">
            <label className="block text-xs font-semibold text-zinc-600">
              Rationale (required, min {minLength} characters)
            </label>
            <span
              className={`text-[10px] font-medium ${
                text.trim().length >= minLength ? 'text-green-700' : 'text-zinc-400'
              }`}
            >
              {text.trim().length} / {minLength} min
            </span>
          </div>
          <textarea
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            placeholder={placeholder}
            className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        </div>
        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}
      </div>
    </Modal>
  );
}

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: React.ReactNode;
  confirmLabel: string;
  destructive?: boolean;
  // When set, the user must type this exact word to enable confirm.
  typedConfirmation?: string;
  onConfirm: () => Promise<void> | void;
  onClose: () => void;
}

export function ConfirmModal({
  isOpen,
  title,
  message,
  confirmLabel,
  destructive,
  typedConfirmation,
  onConfirm,
  onClose,
}: ConfirmModalProps) {
  const [typed, setTyped] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setTyped('');
      setError(null);
      setSubmitting(false);
    }
  }, [isOpen]);

  const typedOk = !typedConfirmation || typed.trim() === typedConfirmation;

  const handleConfirm = async () => {
    if (!typedOk) return;
    setError(null);
    setSubmitting(true);
    try {
      await onConfirm();
    } catch (e: any) {
      setError(e?.message || 'The request failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={submitting ? () => {} : onClose}
      title={title}
      size="md"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-zinc-600 bg-white border border-zinc-200 rounded hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting || !typedOk}
            className={`px-4 py-2 text-sm font-semibold rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${
              destructive
                ? 'bg-red-700 text-white hover:bg-red-800'
                : 'bg-zinc-900 text-white hover:bg-zinc-800'
            }`}
          >
            {submitting ? 'Working…' : confirmLabel}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="text-sm text-zinc-700 leading-snug">{message}</div>
        {typedConfirmation && (
          <div>
            <label className="block text-xs font-semibold text-zinc-600 mb-1">
              Type <span className="font-mono text-zinc-900">{typedConfirmation}</span> to confirm
            </label>
            <input
              autoFocus
              type="text"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
            />
          </div>
        )}
        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}
      </div>
    </Modal>
  );
}
