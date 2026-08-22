"use client";
import { useEffect, useState } from "react";

/**
 * Reads the live theme tokens out of CSS so canvas/SVG libraries (recharts,
 * three.js) can use the same palette as the rest of the interface. Re-reads
 * when the theme switches, which CSS variables alone cannot do for values
 * passed to a library as plain strings.
 */
const TOKENS = {
  accent: "--qg-accent",
  series: "--qg-series",
  warn: "--qg-warn",
  bad: "--qg-bad",
  alt: "--qg-alt",
  ink: "--qg-txt",
  muted: "--qg-dim",
  faint: "--qg-faint",
  line: "--qg-line",
  track: "--qg-meter",
  surface: "--qg-panel",
} as const;

export type ThemeColors = Record<keyof typeof TOKENS, string>;

// Stone (light) values, used for the first server render and as a fallback.
const FALLBACK: ThemeColors = {
  accent: "rgb(60 90 100)", series: "rgb(95 107 117)", warn: "rgb(119 103 63)",
  bad: "rgb(125 80 73)", alt: "rgb(105 101 122)", ink: "rgb(38 37 31)",
  muted: "rgb(85 83 76)", faint: "rgb(120 117 108)", line: "rgb(176 172 161)",
  track: "rgb(196 192 181)", surface: "rgb(226 223 216)",
};

function read(): ThemeColors {
  if (typeof window === "undefined") return FALLBACK;
  const cs = getComputedStyle(document.documentElement);
  const out = {} as ThemeColors;
  (Object.keys(TOKENS) as (keyof typeof TOKENS)[]).forEach((k) => {
    const raw = cs.getPropertyValue(TOKENS[k]).trim();
    out[k] = raw ? `rgb(${raw})` : FALLBACK[k];
  });
  return out;
}

export function useThemeColors(): ThemeColors {
  const [colors, setColors] = useState<ThemeColors>(FALLBACK);

  useEffect(() => {
    setColors(read());
    const obs = new MutationObserver(() => setColors(read()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setColors(read());
    mq.addEventListener?.("change", onChange);
    return () => { obs.disconnect(); mq.removeEventListener?.("change", onChange); };
  }, []);

  return colors;
}
