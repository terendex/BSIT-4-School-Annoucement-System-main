// @ts-check
import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import vercel from "@astrojs/vercel";

// Loaded only when explicitly asked for. A top-level import would make the
// package required for every build, including Vercel's - and if it is not
// installed there the build fails, silently leaving the previous deployment
// live while pushes appear to succeed.
const nodeAdapter = async () => (await import("@astrojs/node")).default;

// SSR everywhere: Facebook's crawler must see the Open Graph tags in the
// server-rendered HTML, so no static pre-rendering for announcement pages.
export default defineConfig({
  output: "server",
  // ASTRO_ADAPTER=node builds a plain Node server, so production SSR
  // behaviour (404s, rewrites, bundling) can be tested locally. Vercel
  // deploys never set it and use the Vercel adapter as before.
  adapter:
    process.env.ASTRO_ADAPTER === "node"
      ? (await nodeAdapter())({ mode: "standalone" })
      : vercel({ webAnalytics: { enabled: false } }),
  site: process.env.PUBLIC_SITE_URL || "http://localhost:4321",
  integrations: [react()],
});
