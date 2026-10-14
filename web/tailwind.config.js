/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        'sans': ['Inter', 'sans-serif'],
        'fredoka': ['Fredoka', 'sans-serif'],
        'poppins': ['Poppins', 'sans-serif'],
      },
      colors: {
        'brand-orange': '#E86521',
        'brand-black': '#0B0B0B',
        'brand-dark': '#121212',
        'brand-red': '#FF3B3B',
        'brand-white': '#EAEAEA',
        'brand-muted': '#888888',
      },
    },
  },
  plugins: [],
}
