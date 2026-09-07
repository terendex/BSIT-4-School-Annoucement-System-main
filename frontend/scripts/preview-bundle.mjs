/**
 * Serve the real Vercel build output locally.
 *
 * `astro dev` does not exercise the bundling or module resolution that the
 * deployed function uses, which is how two production-only 500s slipped
 * through. This runs .vercel/output verbatim.
 *
 * Usage:  npm run build && npm run preview:bundle
 */
import { createServer } from "node:http";

const ENTRY = "../.vercel/output/functions/_render.func/dist/server/entry.mjs";
const PORT = Number(process.env.PORT || 4700);

const { default: handler } = await import(new URL(ENTRY, import.meta.url).href);

createServer(async (req, res) => {
  const request = new Request(`http://${req.headers.host}${req.url}`, {
    method: req.method,
    headers: Object.entries(req.headers).filter(([, v]) => typeof v === "string"),
  });
  try {
    const response = await handler.fetch(request);
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(response.body ? Buffer.from(await response.arrayBuffer()) : undefined);
  } catch (error) {
    console.error("--- the function threw ---", error);
    res.writeHead(500, { "content-type": "text/plain" });
    res.end("function threw - see server output");
  }
}).listen(PORT, () =>
  console.log(`Vercel bundle serving on http://127.0.0.1:${PORT}`)
);
