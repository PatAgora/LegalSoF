// CDD-style modal. Thin headless wrapper around @headlessui/react's
// Dialog with the right shape:
//   - bg-black/50 overlay
//   - white panel, rounded, shadow-lg, border zinc-200
//   - banded header (px-5 py-3, border-b) and footer (border-t, bg-zinc-50/60)
//   - body padded px-5 py-4, scrollable
//
// Sizes: xs | sm | md | lg | xl. Default md.
import { Dialog } from '@headlessui/react';
import { ReactNode } from 'react';

type Size = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'full';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: ReactNode;
  size?: Size;
  // Optional footer row — buttons live here.
  footer?: ReactNode;
  // Hide the X close button in the header (rare).
  hideCloseButton?: boolean;
  children: ReactNode;
}

const SIZES: Record<Size, string> = {
  xs:   'max-w-xs',
  sm:   'max-w-sm',
  md:   'max-w-md',
  lg:   'max-w-lg',
  xl:   'max-w-xl',
  full: 'max-w-7xl w-[95vw] h-[90vh]',
};

export default function Modal({ isOpen, onClose, title, size = 'md', footer, hideCloseButton, children }: ModalProps) {
  return (
    <Dialog open={isOpen} onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel
          className={`w-full ${SIZES[size]} bg-white rounded-md border border-zinc-200 shadow-lg flex flex-col overflow-hidden`}
        >
          {(title || !hideCloseButton) && (
            <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-200">
              {title && (
                <Dialog.Title className="text-sm font-semibold text-zinc-900">
                  {title}
                </Dialog.Title>
              )}
              {!hideCloseButton && (
                <button
                  onClick={onClose}
                  className="p-1 rounded text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
                  aria-label="Close"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          )}
          <div className="px-5 py-4 overflow-y-auto flex-1 text-sm text-zinc-700">
            {children}
          </div>
          {footer && (
            <div className="px-5 py-3 border-t border-zinc-100 bg-zinc-50/60 flex gap-3 justify-end">
              {footer}
            </div>
          )}
        </Dialog.Panel>
      </div>
    </Dialog>
  );
}
