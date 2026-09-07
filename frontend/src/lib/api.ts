/** Server-side reads of the public Django API (used during SSR). */
import { API_BASE_URL } from "./config";
import type { Announcement, AnnouncementSummary, Paginated } from "./types";

const TIMEOUT_MS = 10_000;

async function getJson<T>(path: string): Promise<T | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (response.status === 404) return null;
    if (!response.ok) {
      console.error(`API ${path} responded ${response.status}`);
      return null;
    }
    return (await response.json()) as T;
  } catch (error) {
    // A cold Render service or a network blip must not blank the whole page.
    console.error(`API ${path} failed`, error);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function listAnnouncements(
  page = 1,
  search = ""
): Promise<Paginated<AnnouncementSummary>> {
  const params = new URLSearchParams({ page: String(page) });
  if (search) params.set("q", search);
  const data = await getJson<Paginated<AnnouncementSummary>>(
    `/api/announcements/?${params}`
  );
  return data ?? { count: 0, next: null, previous: null, results: [] };
}

export async function getAnnouncement(slug: string): Promise<Announcement | null> {
  return getJson<Announcement>(`/api/announcements/${encodeURIComponent(slug)}/`);
}
