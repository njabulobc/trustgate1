import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef6ff',
          500: '#2f6fed',
          700: '#1f4db3'
        }
      }
    }
  },
  plugins: []
} satisfies Config;
