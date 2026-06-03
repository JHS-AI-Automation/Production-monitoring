import brand from "./src/brand";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        dgs: brand.colors,
      },
    },
  },
  plugins: [],
};
