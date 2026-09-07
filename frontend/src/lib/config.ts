/** Runtime configuration, read from PUBLIC_* env vars at build/SSR time. */

const stripSlash = (value: string) => value.replace(/\/+$/, "");

/** Django REST API root, e.g. https://announcements-api.onrender.com */
export const API_BASE_URL = stripSlash(
  import.meta.env.PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"
);

/** Public site origin, used to build absolute canonical + OG URLs. */
export const SITE_URL = stripSlash(
  import.meta.env.PUBLIC_SITE_URL || "http://localhost:4321"
);

export const SITE_NAME =
  import.meta.env.PUBLIC_SITE_NAME || "Terendex's Announcement Services";

export const SITE_TAGLINE =
  import.meta.env.PUBLIC_SITE_TAGLINE ||
  "Announcements for BSIT 4 - Saint Louis College, City of San Fernando, La Union.";

/** Logo lives in /public and doubles as the Open Graph fallback image. */
export const LOGO_PATH = "/logo.png";
/** Keep in step with public/logo.png - sent as og:image:width/height. */
export const LOGO_WIDTH = 800;
export const LOGO_HEIGHT = 800;

export const absoluteUrl = (path: string) =>
  path.startsWith("http") ? path : `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
