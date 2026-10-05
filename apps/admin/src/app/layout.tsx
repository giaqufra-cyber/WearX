import { colors } from "@wearx/design-tokens";
import type { Metadata } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";

import { Providers } from "./Providers";
import "./globals.css";

const ui = localFont({
  src: [
    { path: "./fonts/Archivo_400Regular.ttf", weight: "400" },
    { path: "./fonts/Archivo_600SemiBold.ttf", weight: "600" },
    { path: "./fonts/Archivo_700Bold.ttf", weight: "700" },
    { path: "./fonts/Archivo_800ExtraBold.ttf", weight: "800" },
  ],
  variable: "--font-ui",
});
const display = localFont({ src: "./fonts/BodoniModa_500Medium.ttf", variable: "--font-display" });
const mono = localFont({ src: "./fonts/JetBrainsMono_400Regular.ttf", variable: "--font-mono" });
const numeric = localFont({ src: "./fonts/ArchivoExpanded-800.ttf", variable: "--font-numeric" });

export const metadata: Metadata = {
  title: "WearX · Staff",
  robots: { index: false, follow: false },
};

// Colori dal pacchetto condiviso: un solo posto per l'app e il pannello.
const palette = `:root{--bg:${colors.background};--surface:${colors.surface};--surface-raised:${colors.surfaceRaised};--border:${colors.border};--border-subtle:${colors.borderSubtle};--text:${colors.text};--text-secondary:${colors.textSecondary};--text-tertiary:${colors.textTertiary};--text-muted:${colors.textMuted};--accent:${colors.accent};--on-accent:${colors.onAccent};--inverse:${colors.inverse};--danger:${colors.danger};--danger-strong:${colors.dangerStrong};--warning:${colors.warning};}`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="it" className={`${ui.variable} ${display.variable} ${mono.variable} ${numeric.variable}`}>
      <head>
        <style>{palette}</style>
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
