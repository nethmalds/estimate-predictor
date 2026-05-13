import type { NextConfig } from "next";
import withBundleAnalyzerFactory from "@next/bundle-analyzer";

const withBundleAnalyzer = withBundleAnalyzerFactory({
  enabled: process.env.ANALYZE === "true",
});

const isDev = process.env.NODE_ENV !== "production";

// Content-Security-Policy for the Next.js frontend.
// 'unsafe-inline' and 'unsafe-eval' are required by the React Compiler in dev.
// In production these are still present because Next.js inlines critical CSS and
// the React Compiler emits eval-style calls; tighten further if a nonce-based CSP
// is introduced later.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  // In development allow HTTP to the local backend on port 8000.
  // In production the backend is accessed over HTTPS so 'https:' covers it.
  isDev
    ? "connect-src 'self' http://localhost:8000 ws://localhost:8000 https:"
    : "connect-src 'self' https:",
  "media-src 'none'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
]
  .join("; ")
  .trim();

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "geolocation=(), camera=(), microphone=()",
  },
  { key: "Content-Security-Policy", value: csp },
  // HSTS is only meaningful over HTTPS; Caddy sends it in prod, but we add it
  // here too so direct Next.js deploys (e.g. Vercel) also benefit.
  ...(!isDev
    ? [
        {
          key: "Strict-Transport-Security",
          value: "max-age=31536000; includeSubDomains",
        },
      ]
    : []),
];

const nextConfig: NextConfig = {
  output: "standalone",
  reactCompiler: true,
  async headers() {
    return [
      {
        // Apply security headers to every route
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default withBundleAnalyzer(nextConfig);
