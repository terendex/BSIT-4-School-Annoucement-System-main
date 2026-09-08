/** Server-side reads of the public Django API (used during SSR). */
import { API_BASE_URL } from "./config";
import type {
  Announcement,
  AnnouncementSummary,
  Paginated,
  Taxonomy,
} from "./types";

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

export interface FeedFilters {
  search?: string;
  category?: string;
  year?: string;
  section?: string;
}

export async function listAnnouncements(
  page = 1,
  filters: FeedFilters = {}
): Promise<Paginated<AnnouncementSummary>> {
  const params = new URLSearchParams({ page: String(page) });
  if (filters.search) params.set("q", filters.search);
  if (filters.category) params.set("category", filters.category);
  if (filters.year) params.set("year", filters.year);
  if (filters.section) params.set("section", filters.section);
  const data = await getJson<Paginated<AnnouncementSummary>>(
    `/api/announcements/?${params}`
  );
  return data ?? { count: 0, next: null, previous: null, results: [] };
}

export interface FeedState {
  count: number;
  last_modified: string | null;
}

/**
 * The fingerprint of one filtered slice of the feed.
 *
 * The page renders this value and AutoRefresh polls the very same endpoint
 * with the very same filters, so the two can only differ when something has
 * actually changed. Deriving it from the rendered rows instead would drift
 * the moment a search narrowed the list or the reader turned to page 2, and
 * the mismatch would reload the page on a loop.
 */
export async function getFeedState(filters: FeedFilters = {}): Promise<FeedState> {
  const params = new URLSearchParams();
  if (filters.search) params.set("q", filters.search);
  if (filters.category) params.set("category", filters.category);
  if (filters.year) params.set("year", filters.year);
  if (filters.section) params.set("section", filters.section);
  const query = params.toString();
  const data = await getJson<FeedState>(`/api/feed-state/${query ? `?${query}` : ""}`);
  return data ?? { count: 0, last_modified: null };
}

/**
 * The filter vocabulary. Empty lists simply hide the filter bar.
 *
 * Each axis is defaulted separately rather than the whole object at once: the
 * frontend and the API deploy independently, so a page can be live against an
 * API that predates one of them. A missing list should cost that one filter,
 * not throw on the first `.map` and take the page with it.
 */
export async function getTaxonomy(): Promise<Taxonomy> {
  const data = await getJson<Taxonomy>("/api/taxonomy/");
  return {
    categories: data?.categories ?? [],
    year_levels: data?.year_levels ?? [],
    sections: data?.sections ?? [],
  };
}

export async function getAnnouncement(slug: string): Promise<Announcement | null> {
  return getJson<Announcement>(`/api/announcements/${encodeURIComponent(slug)}/`);
}
