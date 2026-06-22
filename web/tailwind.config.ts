import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#2C1A3D",
        muted: "#6E5B7B",
        bg: "#F1E9F7",
        surface: "#FFFFFF",
        border: "#E4D6F0",
        brand: { DEFAULT: "#7A33A6", dark: "#5E2585", light: "#C49AE0" },
        sidebar: "#2A1340",
        good: "#7A33A6",
        warn: "#C9892F",
        bad: "#C2566B",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["'Plus Jakarta Sans'", "Inter", "sans-serif"],
      },
      boxShadow: {
        card: "0 10px 26px rgba(40,18,60,0.06)",
      },
    },
  },
  plugins: [],
};
export default config;
