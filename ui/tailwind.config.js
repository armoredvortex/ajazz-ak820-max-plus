/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{svelte,js,ts}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0f0f14',
          1: '#16161f',
          2: '#1e1e2a',
          3: '#26263a',
          4: '#2e2e45',
        },
        accent: {
          DEFAULT: '#7c6bff',
          hover: '#9d8fff',
          dim: '#3d366b',
        },
        success: '#34d399',
        danger:  '#f87171',
        warn:    '#fbbf24',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
