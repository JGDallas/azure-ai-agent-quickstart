/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f7f7f8",
          100: "#ececee",
          200: "#d1d1d6",
          300: "#a3a3ab",
          400: "#6e6e76",
          500: "#3f3f47",
          600: "#2a2a31",
          700: "#1d1d22",
          800: "#121216",
          900: "#0a0a0c",
        },
      },
    },
  },
  plugins: [],
};
