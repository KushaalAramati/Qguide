import type { Config } from "tailwindcss";

// Redesigned theme (Feature 9): minimal, professional, restrained.
// Cool graphite canvas (not predominantly white), crisp white cards, strong dark
// slate text, one restrained indigo accent + muted status colors.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#1b2231",        // primary text — near-black slate
        muted: "#647087",      // secondary text
        bg: "#e9edf3",         // app canvas — cool light gray (darker than white)
        surface: "#ffffff",    // cards / inputs
        border: "#d7dde8",     // subtle borders
        brand: { DEFAULT: "#4b54c9", dark: "#373fa6", light: "#c4c9f4" }, // restrained indigo
        accent: { DEFAULT: "#0f9488", light: "#5eead4" },                 // muted teal
        sidebar: "#151a26",    // graphite near-black sidebar
        good: "#0f9d74",       // emerald
        warn: "#c07c1e",       // amber
        bad: "#d5495f",        // rose
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["'Plus Jakarta Sans'", "Inter", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(20,26,40,0.04), 0 1px 3px rgba(20,26,40,0.06)",
      },
    },
  },
  plugins: [],
};
export default config;
