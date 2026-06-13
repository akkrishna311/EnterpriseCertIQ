/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
        canvas: 'var(--canvas)',
        surface: {
          DEFAULT: 'var(--surface)',
          2: 'var(--surface-2)',
          3: 'var(--surface-3)',
        },
        line: {
          DEFAULT: 'var(--line)',
          strong: 'var(--line-strong)',
        },
        ink: {
          DEFAULT: 'var(--ink)',
          muted: 'var(--ink-muted)',
          subtle: 'var(--ink-subtle)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          2: 'var(--accent-2)',
        },
      },
      borderColor: {
        // Bare `border` (no color class) defaults to this instead of light gray-200,
        // so every panel/button border is the subtle dark line across all pages.
        DEFAULT: 'var(--line)',
      },
      boxShadow: {
        glow: '0 18px 50px -24px var(--accent-glow)',
      },
    },
  },
  plugins: [],
}
