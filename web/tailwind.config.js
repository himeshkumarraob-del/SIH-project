/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f3f8',
          100: '#d9e0ed',
          200: '#b3c1db',
          300: '#8da2c9',
          400: '#6783b7',
          500: '#4164a5',
          600: '#345084',
          700: '#273c63',
          800: '#1a2842',
          900: '#0d1421',
          950: '#060a10',
        },
        status: {
          high: '#dc2626',
          'high-bg': '#fef2f2',
          elevated: '#d97706',
          'elevated-bg': '#fffbeb',
          low: '#16a34a',
          'low-bg': '#f0fdf4',
        },
      },
    },
  },
  plugins: [],
}
