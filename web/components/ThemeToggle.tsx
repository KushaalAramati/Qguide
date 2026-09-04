"use client";
import { useEffect, useState } from "react";

type Theme = "light" | "dark";

/**
 * Light ("Stone") / dark ("Charcoal") switch. The initial value is applied by the
 * bootstrap script in app/layout.tsx before first paint; this component only
 * reads what is already on <html> so the two can never disagree.
 */
export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    setTheme(current === "dark" ? "dark" : "light");
  }, []);

  function apply(next: Theme) {
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("qg-theme", next);
    } catch {
      /* private mode — the choice just does not persist */
    }
  }

  const label = theme === "dark" ? "dark" : "light";

  if (compact) {
    return (
      <button
        onClick={() => apply(theme === "dark" ? "light" : "dark")}
        title={`Theme: ${label} — click to switch`}
        aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        className="w-7 h-7 grid place-items-center text-faint hover:text-brand transition-colors"
      >
        {theme === "dark" ? "◑" : "◐"}
      </button>
    );
  }

  return (
    <div className="seg" role="group" aria-label="Theme">
      <button className={theme === "light" ? "on" : ""} onClick={() => apply("light")}>light</button>
      <button className={theme === "dark" ? "on" : ""} onClick={() => apply("dark")}>dark</button>
    </div>
  );
}
