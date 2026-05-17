// CDD-style badge / pill. Same shape as the status chips but
// general-purpose (no required dot, no severity semantics). Use
// StatusChip for verdicts; use Badge for everything else.
import { HTMLAttributes, ReactNode } from 'react';

type Variant = 'default' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
  mono?: boolean;
  children: ReactNode;
}

const VARIANTS: Record<Variant, string> = {
  default: 'bg-zinc-50  text-zinc-700  ring-zinc-200/80',
  success: 'bg-green-50 text-green-700 ring-green-200/80',
  warning: 'bg-amber-50 text-amber-700 ring-amber-200/80',
  danger:  'bg-red-50   text-red-700   ring-red-200/80',
  info:    'bg-blue-50  text-blue-700  ring-blue-200/80',
};

export default function Badge({ variant = 'default', mono, className = '', children, ...rest }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold tracking-wide ring-1 ring-inset ${VARIANTS[variant]} ${mono ? 'font-mono' : ''} ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
}
