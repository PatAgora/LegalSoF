// CDD-style inline alert. Banner-row variant — sits in-flow above
// content, not a toast. Use Modal for confirmation prompts.
import { HTMLAttributes, ReactNode } from 'react';

type Variant = 'info' | 'success' | 'warning' | 'error';

interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
  title?: string;
  onDismiss?: () => void;
  children?: ReactNode;
}

const VARIANTS: Record<Variant, { wrap: string; title: string }> = {
  info:    { wrap: 'bg-blue-50  border-blue-200  text-blue-800',   title: 'text-blue-900' },
  success: { wrap: 'bg-green-50 border-green-200 text-green-800',  title: 'text-green-900' },
  warning: { wrap: 'bg-amber-50 border-amber-200 text-amber-800',  title: 'text-amber-900' },
  error:   { wrap: 'bg-red-50   border-red-200   text-red-800',    title: 'text-red-900' },
};

export default function Alert({ variant = 'info', title, onDismiss, className = '', children, ...rest }: AlertProps) {
  const v = VARIANTS[variant];
  return (
    <div className={`rounded border px-4 py-3 text-sm flex items-start gap-3 ${v.wrap} ${className}`} {...rest}>
      <div className="flex-1 min-w-0">
        {title && <div className={`font-semibold mb-0.5 ${v.title}`}>{title}</div>}
        {children}
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="p-0.5 rounded hover:bg-black/5 transition-colors"
          aria-label="Dismiss"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}
