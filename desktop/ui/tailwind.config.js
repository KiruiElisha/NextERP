/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: { 50: '#EEF3FE', 100: '#DCE6FD', 500: '#2F5FE0', 600: '#1F4FD8', 700: '#1A41B0' },
        leaf: { 500: '#22B573', 600: '#1A9A61' },
        slate: { 250: '#E4E9F0' },
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'] },
    },
  },
  plugins: [],
}
