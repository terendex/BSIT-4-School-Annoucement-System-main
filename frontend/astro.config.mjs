// @ts-check
import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import vercel from "@astrojs/vercel";

// SSR everywhere: Facebook's crawler must see the Open Graph tags in the
// server-rendered HTML, so no static pre-rendering for announcement pages.
export default defineConfig({
  output: "server",
  adapter: vercel({
    webAnalytics: { enabled: false },
  }),
  site: process.env.PUBLIC_SITE_URL || "http://localhost:4321",
  integrations: [react()],
  vite: {
    ssr: {
      // sanitize-html is CJS and must not be bundled for the edge.
      external: ["sanitize-html"],
    },
  },
});
