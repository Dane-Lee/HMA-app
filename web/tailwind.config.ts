import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        sand: "#f5efe4",
        ink: "#19313a",
        teal: "#2d7d7f",
        clay: "#c96442",
        mist: "#e6f1ed"
      },
      boxShadow: {
        card: "0 16px 40px rgba(25, 49, 58, 0.08)"
      },
      fontFamily: {
        sans: ["Avenir Next", "Trebuchet MS", "sans-serif"]
      }
    }
  },
  plugins: []
} satisfies Config;

