import path from "node:path";

import type { NextConfig } from "next";

/**
 * Pannello dello staff. Nessun dato sul server Next: le pagine girano nel browser e parlano
 * con l'API usando il token Supabase dello staff (con secondo fattore).
 * Intestazioni di sicurezza strette: niente iframe, niente referrer, nessuna indicizzazione.
 */
const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const supabase = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "https://alcpqfphwygpktrcyauu.supabase.co";
const dev = process.env.NODE_ENV !== "production";

const csp = [
  "default-src 'self'",
  // Next in sviluppo usa eval per il ricaricamento a caldo.
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  // Foto dei fit: URL firmati dell'archivio (in locale localhost:9000).
  `img-src 'self' data: blob: https:${dev ? " http://localhost:9000" : ""}`,
  "font-src 'self'",
  `connect-src 'self' ${api} ${supabase}${dev ? " ws:" : ""}`,
  "frame-ancestors 'none'",
  "base-uri 'none'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  // Server autonomo per il container (seduta 23); la radice del monorepo per i pacchetti comuni.
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../.."),
  transpilePackages: ["@wearx/design-tokens", "@wearx/api-types"],
  poweredByHeader: false,
  devIndicators: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
