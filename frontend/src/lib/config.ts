/**
 * Runtime configuration.
 *
 * The deployed URLs are baked in as defaults so the site builds correctly with
 * no dashboard configuration at all - neither value is a secret, both appear in
 * the page source and in browser JavaScript either way. Setting the matching
 * PUBLIC_* environment variable still overrides them, which is what you want
 * after moving to a custom domain.
 */

const stripSlash = (value: string) => value.replace(/\/+$/, "");

/** import.meta.env.PROD is true for `astro build`, false for `astro dev`. */
const isProduction = import.meta.env.PROD;

const DEPLOYED_API_URL = "https://announcements-api-production-58f8.up.railway.app";
const DEPLOYED_SITE_URL = "https://bsit-4-school-annoucement-system-ma.vercel.app";

/** Django REST API root. */
export const API_BASE_URL = stripSlash(
  import.meta.env.PUBLIC_API_BASE_URL ||
    (isProduction ? DEPLOYED_API_URL : "http://127.0.0.1:8000")
);

/**
 * Public origin of this site, used for canonical and Open Graph URLs. It must
 * be the real domain in production or Messenger will not render a preview.
 */
export const SITE_URL = stripSlash(
  import.meta.env.PUBLIC_SITE_URL ||
    (isProduction ? DEPLOYED_SITE_URL : "http://localhost:4321")
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
