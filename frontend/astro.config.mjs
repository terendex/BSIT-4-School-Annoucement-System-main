// @ts-check
import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import vercel from "@astrojs/vercel";
import node from "@astrojs/node";

// SSR everywhere: Facebook's crawler must see the Open Graph tags in the
// server-rendered HTML, so no static pre-rendering for announcement pages.
export default defineConfig({
  output: "server",
  // ASTRO_ADAPTER=node builds a plain Node server, so production SSR
  // behaviour (404s, rewrites, bundling) can be tested locally. Vercel
  // deploys never set it and use the Vercel adapter as before.
  adapter:
    process.env.ASTRO_ADAPTER === "node"
      ? node({ mode: "standalone" })
      : vercel({ webAnalytics: { enabled: false } }),
  site: process.env.PUBLIC_SITE_URL || "http://localhost:4321",
  integrations: [react()],
  vite: {
    ssr: {
      // sanitize-html must be BUNDLED, not left external. Marked external, the
      // adapter's file tracing missed its transitive deps (htmlparser2,
      // escape-string-regexp), so rendering a Markdown body threw
      // "Cannot find module" at runtime and every announcement page 500'd.
      noExternal: ["sanitize-html"],
    },
  },
});
