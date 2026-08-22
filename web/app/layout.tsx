import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

// Mono-first interface. IBM Plex Mono is the UI face, not just the code face —
// sequences, scores and positions all have to align vertically to be scannable.
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

// Reserved for long-form prose (help text, docs) where mono hurts reading.
const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "QGuide — Explainable CRISPR guide-RNA design",
  description: "Context-aware, explainable CRISPR guide RNA recommendation.",
};

// Applied before first paint so the theme never flashes. Falls back to the OS
// preference when the user has not chosen; the toggle writes qg-theme.
const themeBootstrap = `
(function () {
  try {
    var stored = localStorage.getItem('qg-theme');
    var theme = stored === 'light' || stored === 'dark' ? stored
      : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${plexMono.variable} ${plexSans.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
