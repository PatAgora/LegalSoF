// CDD-style button. Variants:
//   primary   — solid black (zinc-900) on white, used for the main
//               action of a screen.
//   secondary — white with zinc border, used for cancel / dismiss /
//               secondary actions sitting next to a primary.
//   danger    — solid red, used for destructive actions only.
//   ghost     — transparent, hover zinc-50. Used for icon-only or
//               inline-link-style buttons.
//
// Sizes: sm | md (default) | lg.
import { ButtonHTMLAttributes, forwardRef, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
}

// Quieter than a SaaS button. Primary is still solid black, but
// font-weight is medium (500) rather than semibold so it doesn't shout.
// Secondary uses a slightly darker border (zinc-300) so it reads
// confidently against the warm stone-50 page background.
const VARIANTS: Record<Variant, string> = {
  primary:   'bg-zinc-900 text-white hover:bg-zinc-800 focus-visible:ring-zinc-700',
  secondary: 'bg-white text-zinc-700 hover:bg-zinc-50 border border-zinc-300 focus-visible:ring-zinc-400',
  danger:    'bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500',
  ghost:     'bg-transparent text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 focus-visible:ring-zinc-300',
};

const SIZES: Record<Size, string> = {
  sm: 'text-xs px-3 py-1.5 gap-1.5 rounded',
  md: 'text-[13px] px-4 py-2 gap-2 rounded',
  lg: 'text-sm px-5 py-2.5 gap-2 rounded-md',
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'sm', loading, leadingIcon, trailingIcon, className = '', children, disabled, ...rest }, ref) => {
    const base =
      'inline-flex items-center justify-center font-medium transition-colors ' +
      'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ' +
      'disabled:opacity-50 disabled:cursor-not-allowed';
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={`${base} ${VARIANTS[variant]} ${SIZES[size]} ${loading ? 'cursor-wait' : ''} ${className}`}
        {...rest}
      >
        {loading ? (
          <svg className="animate-spin h-4 w-4 text-current" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
            <path className="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z" />
          </svg>
        ) : leadingIcon}
        {children}
        {!loading && trailingIcon}
      </button>
    );
  }
);
Button.displayName = 'Button';

export default Button;
