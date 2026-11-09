/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  darkMode: 'class',
  theme: {
    extend: {
      // The JEMKAS desktop app's look (Frappe UI's palette): neutral greys and a green accent. The
      // names stay brand/slate so every screen picks it up; greys keep Tailwind's lightness per step
      // (text-slate-400 stays readable) without its blue tint, and the green sits a step darker than
      // Frappe UI's so white text on it and green links on white stay legible.
      colors: {
        brand: {
          50: '#F2FDF4', 100: '#E4FAEB', 200: '#D4F6DE', 300: '#B9EECC', 400: '#7FD1A5',
          500: '#30A66D', 600: '#278F5E', 700: '#16794C', 800: '#12613D', 900: '#173B2C', 950: '#0E2A1E',
        },
        slate: {
          50: '#F8F8F8', 100: '#F3F3F3', 200: '#E6E6E6', 250: '#EBEBEB', 300: '#D1D1D1', 400: '#9C9C9C',
          500: '#6E6E6E', 600: '#525252', 700: '#383838', 800: '#262626', 900: '#171717', 950: '#0F0F0F',
        },
        leaf: { 500: '#22B573', 600: '#1A9A61' },
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'] },
    },
  },
  plugins: [],
}
