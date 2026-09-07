// @ts-check
import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import vercel from "@astrojs/vercel";

// SSR everywhere: Facebook's crawler must see the Open Graph tags in the
// server-rendered HTML, so no static pre-rendering for announcement pages.
//
// Kept deliberately plain. Two attempts to be clever here each broke the
// Vercel build, and a failed build leaves the PREVIOUS deployment serving
// while pushes still look successful - which is very hard to spot:
//   - a vite.ssr override for sanitize-html broke module resolution at runtime
//   - a second adapter referenced here (import, then top-level await) made
//     every build depend on a package Vercel does not install
// To exercise a real production build locally, use `npm run preview:bundle`;
// it runs the actual Vercel output and needs no change to this file.
export default defineConfig({
  output: "server",
  adapter: vercel({ webAnalytics: { enabled: false } }),
  site: process.env.PUBLIC_SITE_URL || "http://localhost:4321",
  integrations: [react()],
});
