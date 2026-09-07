import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "../lib/config";

interface Props {
  /** Fingerprint rendered with the page, from the server. */
  initial: string;
  /** Announcement slug on a detail page; omit on list pages. */
  slug?: string;
  /** Seconds between checks. */
  intervalSeconds?: number;
}

const endpointFor = (slug?: string) =>
  slug
    ? `${API_BASE_URL}/api/announcements/${encodeURIComponent(slug)}/`
    : `${API_BASE_URL}/api/feed-state/`;

const signatureOf = (data: any, slug?: string): string =>
  slug ? String(data?.updated_at ?? "") : `${data?.count ?? ""}:${data?.last_modified ?? ""}`;

/**
 * Watches for new or edited announcements and offers a refresh.
 *
 * Deliberately does not reload the page out from under you: the banner waits
 * for a click, and the only automatic reload happens when you return to a tab
 * that has gone stale, which is the moment you expect fresh content anyway.
 */
export default function AutoRefresh({ initial, slug, intervalSeconds = 60 }: Props) {
  const [stale, setStale] = useState(false);
  const [gone, setGone] = useState(false);
  const initialRef = useRef(initial);

  const check = useCallback(async () => {
    try {
      const response = await fetch(endpointFor(slug), {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (response.status === 404 && slug) {
        // The announcement was unpublished or deleted while open.
        setGone(true);
        return false;
      }
      if (!response.ok) return false;
      const changed = signatureOf(await response.json(), slug) !== initialRef.current;
      if (changed) setStale(true);
      return changed;
    } catch {
      // Offline or the API is asleep - stay quiet and try again next tick.
      return false;
    }
  }, [slug]);

  useEffect(() => {
    let timer: number | undefined;

    const schedule = () => {
      window.clearTimeout(timer);
      // Polling a hidden tab wastes battery and mobile data.
      if (document.hidden) return;
      timer = window.setTimeout(async () => {
        await check();
        schedule();
      }, Math.max(15, intervalSeconds) * 1000);
    };

    const onVisibility = async () => {
      if (document.hidden) {
        window.clearTimeout(timer);
        return;
      }
      // Coming back to the tab is the one safe moment to reload outright.
      if (await check()) {
        if (!isBusy()) {
          window.location.reload();
          return;
        }
      }
      schedule();
    };

    schedule();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [check, intervalSeconds]);

  if (gone) {
    return (
      <div className="refresh-bar refresh-bar--gone" role="status">
        <span>This announcement is no longer available.</span>
        <a className="btn btn--sm" href="/">
          All announcements
        </a>
      </div>
    );
  }

  if (!stale) return null;

  return (
    <div className="refresh-bar" role="status" aria-live="polite">
      <span>{slug ? "This announcement was updated." : "New announcements posted."}</span>
      <button type="button" className="btn btn--sm" onClick={() => window.location.reload()}>
        Refresh
      </button>
    </div>
  );
}

/** True while something would be lost by reloading - an open dialog or a filled field. */
function isBusy(): boolean {
  if (document.querySelector(".modal")) return true;
  const active = document.activeElement;
  if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) {
    return true;
  }
  return Array.from(document.querySelectorAll("input, textarea")).some(
    (el) => (el as HTMLInputElement | HTMLTextAreaElement).value.trim().length > 0
  );
}
