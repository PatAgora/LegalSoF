/** @type {import('tailwindcss').Config} */
//
// Pure black & white palette aligned with the CDD app.
//
// The legacy custom names (`primary`, `accent`, `brand-*`, `status-*`)
// are KEPT as aliases pointing at neutral Tailwind values so existing
// components continue to compile and render in the new B&W scheme
// without a per-file migration. The Phase B / C work then replaces the
// legacy classes with the new ui/ primitives.
//
// The only colour anywhere in the design is in status chips
// (success / warning / danger / info) and chart fills, where colour
// carries semantic meaning (severity / outcome). Everything else is
// zinc.
//
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        'page-title':    ['1.75rem',   { lineHeight: '2.25rem', fontWeight: '600', letterSpacing: '-0.025em' }],
        'section-title': ['1.125rem',  { lineHeight: '1.75rem', fontWeight: '600', letterSpacing: '-0.01em' }],
        'body':          ['0.875rem',  { lineHeight: '1.5rem',  fontWeight: '400' }],
        'caption':       ['0.75rem',   { lineHeight: '1.125rem', fontWeight: '500' }],
        'overline':      ['0.6875rem', { lineHeight: '1rem',    fontWeight: '600', letterSpacing: '0.05em' }],
      },
      colors: {
        // ------------------------------------------------------------
        // Legacy aliases — point at zinc so the WHOLE app shifts to B&W
        // with no per-component changes. Removed once Phase B migration
        // sweeps the call sites onto the new primitives.
        // ------------------------------------------------------------
        primary: {
          50:  '#fafafa',  // zinc-50
          100: '#f4f4f5',  // zinc-100
          200: '#e4e4e7',  // zinc-200
          300: '#d4d4d8',  // zinc-300
          400: '#a1a1aa',  // zinc-400
          500: '#71717a',  // zinc-500
          600: '#52525b',  // zinc-600
          700: '#3f3f46',  // zinc-700
          800: '#27272a',  // zinc-800
          900: '#18181b',  // zinc-900
        },
        accent: {
          // The old gold accent is gone — alias to zinc so any
          // surviving `bg-accent-*` class renders as a neutral surface
          // rather than a screaming warm tone.
          50:  '#fafafa',
          100: '#f4f4f5',
          200: '#e4e4e7',
          300: '#d4d4d8',
          400: '#a1a1aa',
          500: '#27272a',
          600: '#18181b',
          700: '#09090b',
          800: '#000000',
          900: '#000000',
        },

        // ------------------------------------------------------------
        // Brand aliases — same idea, all mapped to neutral zinc.
        // ------------------------------------------------------------
        brand: {
          dark: '#18181b',           // zinc-900
          surface: '#f8fafc',        // slate-50 — body bg
          'surface-alt': '#f4f4f5',  // zinc-100
          panel: '#ffffff',
          muted: '#e4e4e7',          // zinc-200
          ink: '#18181b',            // zinc-900 — body text
          'ink-secondary': '#52525b',// zinc-600
          'ink-tertiary': '#a1a1aa', // zinc-400
        },

        // ------------------------------------------------------------
        // Status palette — the ONLY colour in the system. Keyed off
        // Tailwind's stock green / amber / red / blue scales so chips
        // match CDD's `bg-X-50 text-X-700 ring-X-200/80` formula 1:1.
        // ------------------------------------------------------------
        status: {
          success: {
            50:  '#f0fdf4', // green-50
            100: '#dcfce7', // green-100
            200: '#bbf7d0', // green-200
            400: '#4ade80', // green-400
            500: '#22c55e', // green-500
            700: '#15803d', // green-700
            900: '#14532d', // green-900
          },
          warning: {
            50:  '#fffbeb', // amber-50
            100: '#fef3c7', // amber-100
            200: '#fde68a', // amber-200
            500: '#f59e0b', // amber-500
            700: '#b45309', // amber-700
            900: '#78350f', // amber-900
          },
          danger: {
            50:  '#fef2f2', // red-50
            100: '#fee2e2', // red-100
            200: '#fecaca', // red-200
            500: '#ef4444', // red-500
            700: '#b91c1c', // red-700
            900: '#7f1d1d', // red-900
          },
          info: {
            50:  '#eff6ff', // blue-50
            100: '#dbeafe', // blue-100
            200: '#bfdbfe', // blue-200
            500: '#3b82f6', // blue-500
            700: '#1d4ed8', // blue-700
            900: '#1e3a8a', // blue-900
          },
        },
      },
      borderRadius: {
        // Custom names kept for the existing call sites; the new ui/
        // primitives prefer the stock `rounded-md` (which is 6 px).
        card: '0.375rem',    // 6 px — same as rounded-md
        button: '0.25rem',   // 4 px — same as rounded
        badge: '0.25rem',
        input: '0.25rem',
      },
      boxShadow: {
        card: 'none',
        elevated: '0 1px 3px 0 rgb(0 0 0 / 0.04)',
        dropdown: '0 4px 12px -2px rgb(0 0 0 / 0.08)',
      },
    },
  },
  plugins: [],
}
