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
  // Without a CSS target the minifier assumes a modern browser and rewrites
  // "(max-width: 700px)" into Media Queries Level 4 range syntax,
  // "(width <= 700px)". Safari only understands that from 16.4, so every
  // mobile rule would be skipped on an older phone - the layout would fall
  // back to the desktop table on exactly the devices that need it least.
  // This is a CSS-output setting only; it does not touch module resolution.
  vite: { build: { cssTarget: ["chrome87", "safari13", "firefox78", "edge88"] } },
  adapter: vercel({ webAnalytics: { enabled: false } }),
  site: process.env.PUBLIC_SITE_URL || "http://localhost:4321",
  integrations: [react()],
});
