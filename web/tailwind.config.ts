import type { Config } from "tailwindcss";

/**
 * QGuide — terminal design system.
 *
 * Colour VALUES live in app/globals.css as CSS variables (space-separated RGB
 * channels so Tailwind opacity modifiers like `bg-brand/10` keep working).
 * Light mode is "Stone", dark mode is "Charcoal"; both drive the same class
 * surface, so components never branch on theme and never hardcode a hex.
 *
 * Three rules this direction depends on:
 *   1. Monospace everywhere — sequences, scores and positions must align.
 *   2. Borders, never shadows. Square corners. Depth comes from surface value.
 *   3. Colour is reserved: accent / series / warn / bad. Everything else neutral.
 */
const c = (v: string) => `rgb(var(${v}) / <alpha-value>)`;

const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ---- surfaces (depth is value, not shadow) ----
        bg: c("--qg-bg"),              // app ground
        surface: c("--qg-panel"),      // panel / card
        raised: c("--qg-panel2"),      // panel header, table head
        chrome: c("--qg-deep"),        // rail + status bar
        sidebar: c("--qg-deep"),       // legacy alias for chrome
        well: c("--qg-input"),         // inputs, code wells

        // ---- lines ----
        border: c("--qg-line"),        // panel borders, header rules
        divider: c("--qg-line2"),      // row dividers

        // ---- text ----
        ink: c("--qg-txt"),            // primary
        cell: c("--qg-td"),            // table cell
        title: c("--qg-h1"),           // page title
        muted: c("--qg-dim"),          // secondary
        faint: c("--qg-faint"),        // labels, tertiary
        seq: c("--qg-locus"),          // sequence text

        // ---- mark tracks ----
        track: c("--qg-meter"),
        track2: c("--qg-be2"),

        // ---- semantic (only four carry meaning) ----
        // accent  : selection, healthy state, headline value
        // series  : neutral quantitative bars
        // warn    : provisional model, medium risk
        // bad     : high risk, failure
        brand: {
          DEFAULT: c("--qg-accent"),
          dark: c("--qg-accent"),
          light: c("--qg-accent-soft"),
        },
        accent: { DEFAULT: c("--qg-accent"), light: c("--qg-accent-soft") },
        series: c("--qg-series"),
        good: c("--qg-accent"),
        warn: c("--qg-warn"),
        bad: c("--qg-bad"),
        alt: c("--qg-alt"),
      },
      fontFamily: {
        // Mono-first. IBM Plex Mono is the interface face, not just the code face.
        mono: ["var(--font-plex-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        sans: ["var(--font-plex-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        display: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
        // Reserved for long-form prose (docs, help panels) where mono hurts reading.
        prose: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        none: "0px", sm: "0px", DEFAULT: "0px", md: "0px",
        lg: "0px", xl: "0px", "2xl": "0px", "3xl": "0px",
        full: "9999px", // kept for avatars / status dots only
      },
      boxShadow: { card: "none", none: "none" },
      letterSpacing: { tightest: "-0.03em" },
    },
  },
  plugins: [],
};
export default config;
