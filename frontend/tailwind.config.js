/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#04060c',
        abyss: '#060a13',
        panel: '#0a1120',
        panel2: '#0d1526',
        edge: '#1a2a44',
        edgeSoft: '#142136',
        ink: '#e8f0fb',
        dim: '#93a7c4',
        muted: '#64788f',
        signal: '#4cc9f0',
        electric: '#3b82f6',
        plasma: '#8b5cf6',
        sun: '#fbbf24',
        earth: '#38bdf8',
        good: '#34d399',
        warn: '#f59e0b',
        bad: '#f87171',
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Code', 'Consolas', 'monospace'],
      },
      boxShadow: {
        panel: '0 18px 60px rgba(0,0,0,0.45)',
        glow: '0 0 0 1px rgba(76,201,240,0.25), 0 0 32px rgba(56,189,248,0.12)',
      },
      backgroundImage: {
        grid: 'linear-gradient(rgba(76,201,240,0.055) 1px, transparent 1px), linear-gradient(90deg, rgba(76,201,240,0.055) 1px, transparent 1px)',
        'radial-space':
          'radial-gradient(1200px 600px at 70% -10%, rgba(56,189,248,0.14), transparent 60%), radial-gradient(900px 500px at 10% 110%, rgba(139,92,246,0.10), transparent 60%)',
      },
      keyframes: {
        pulseSoft: {
          '0%,100%': { opacity: '0.45' },
          '50%': { opacity: '1' },
        },
        drift: {
          '0%': { transform: 'translate3d(0,0,0)' },
          '50%': { transform: 'translate3d(0,-8px,0)' },
          '100%': { transform: 'translate3d(0,0,0)' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(1200%)' },
        },
      },
      animation: {
        pulseSoft: 'pulseSoft 2.6s ease-in-out infinite',
        drift: 'drift 9s ease-in-out infinite',
        scan: 'scan 7s linear infinite',
      },
    },
  },
  plugins: [],
};
