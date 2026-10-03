/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{svelte,js,ts}'],
  theme: {
    extend: {
      colors: {
        base: '#000000',
        surface: {
          DEFAULT: '#0a0a0a',
          1: '#111111',
          2: '#1a1a1a',
          3: '#222222',
        },
        line:    '#1f1f1f',
        subtle:  '#2a2a2a',
        muted:   'rgba(255,255,255,0.35)',
        dim:     'rgba(255,255,255,0.15)',
        success: '#22c55e',
        danger:  '#ef4444',
        warn:    '#f59e0b',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.7rem',   '1rem'   ],
        'xs':  ['0.8rem',   '1.1rem' ],
        'sm':  ['0.875rem', '1.25rem'],
      },
    },
  },
  plugins: [],
}
