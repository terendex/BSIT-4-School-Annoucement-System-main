import { useCallback, useEffect, useRef } from "react";
import { API_BASE_URL } from "../lib/config";

interface Props {
  /** Fingerprint rendered with the page, from the server. */
  initial: string;
  /** Announcement slug on a detail page; omit on list pages. */
  slug?: string;
  /**
   * The list page's active filters as a query string ("category=exam&year=4").
   * feed-state has to be asked the same question the page was, or a filtered
   * view would compare its own count against the whole board and reload for
   * ever.
   */
  query?: string;
  /** Seconds between checks. */
  intervalSeconds?: number;
}

const endpointFor = (slug?: string, query?: string) =>
  slug
    ? `${API_BASE_URL}/api/announcements/${encodeURIComponent(slug)}/`
    : `${API_BASE_URL}/api/feed-state/${query ? `?${query}` : ""}`;

const signatureOf = (data: any, slug?: string): string =>
  slug ? String(data?.updated_at ?? "") : `${data?.count ?? ""}:${data?.last_modified ?? ""}`;

/**
 * Keeps the page current without any visible chrome.
 *
 * Renders nothing. When the announcements change it reloads quietly, and only
 * at a moment where a reload cannot lose anything or interrupt reading:
 *  - never while a dialog is open or a form has been typed into
 *  - never while the tab is hidden (polling stops there too, to spare battery
 *    and mobile data)
 *  - on a long page, not while scrolled down mid-article
 * If the moment is wrong it simply waits and checks again.
 */
export default function AutoRefresh({
  initial,
  slug,
  query,
  intervalSeconds = 60,
}: Props) {
  const initialRef = useRef(initial);

  const changed = useCallback(async () => {
    try {
      const response = await fetch(endpointFor(slug, query), {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      // A deleted or unpublished post is a change worth picking up: reloading
      // lands the reader on the "no longer available" page instead of a stale one.
      if (response.status === 404 && slug) return true;
      if (!response.ok) return false;
      return signatureOf(await response.json(), slug) !== initialRef.current;
    } catch {
      // Offline, or the API is asleep. Stay quiet and try again next tick.
      return false;
    }
  }, [slug, query]);

  useEffect(() => {
    let timer: number | undefined;
    let stopped = false;

    const tick = async () => {
      if (stopped || document.hidden) return;
      if ((await changed()) && safeToReload()) {
        window.location.reload();
        return;
      }
      schedule();
    };

    const schedule = () => {
      window.clearTimeout(timer);
      if (stopped || document.hidden) return;
      timer = window.setTimeout(tick, Math.max(15, intervalSeconds) * 1000);
    };

    const onVisibility = () => {
      window.clearTimeout(timer);
      // Returning to the tab is the natural moment to pick up what was missed.
      if (!document.hidden) void tick();
    };

    schedule();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [changed, intervalSeconds]);

  return null;
}

/** False whenever reloading would lose work or yank the page away mid-read. */
function safeToReload(): boolean {
  if (document.querySelector(".modal")) return false;

  const active = document.activeElement;
  if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) {
    return false;
  }

  const typed = Array.from(document.querySelectorAll("input, textarea")).some(
    (el) => (el as HTMLInputElement | HTMLTextAreaElement).value.trim().length > 0
  );
  if (typed) return false;

  // Reading something further down the page: leave them alone.
  const scrollable = document.documentElement.scrollHeight - window.innerHeight;
  return scrollable <= 200 || window.scrollY <= 200;
}
