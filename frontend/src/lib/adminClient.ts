/**
 * Browser-side admin API client.
 *
 * The access token is kept in memory only. The refresh token goes to
 * sessionStorage so a page reload does not sign you out, but it is gone when
 * the tab closes - a deliberate trade against long-lived tokens sitting in
 * localStorage.
 */
import { API_BASE_URL } from "./config";
import type { Announcement, AdminUser, Attachment, Paginated } from "./types";

const REFRESH_KEY = "slc.admin.refresh";

let accessToken: string | null = null;

export class ApiError extends Error {
  status: number;
  fields: Record<string, string[]>;

  constructor(message: string, status: number, fields: Record<string, string[]> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

const readRefresh = (): string | null => {
  try {
    return sessionStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
};

const writeRefresh = (token: string | null) => {
  try {
    if (token) sessionStorage.setItem(REFRESH_KEY, token);
    else sessionStorage.removeItem(REFRESH_KEY);
  } catch {
    /* private-mode browsers: stay signed in for this page view only */
  }
};

export const hasSession = () => Boolean(accessToken || readRefresh());

async function parseError(response: Response): Promise<ApiError> {
  let detail = `Request failed (${response.status})`;
  let fields: Record<string, string[]> = {};
  try {
    const data = await response.json();
    if (data?.detail) detail = String(data.detail);
    if (data?.errors && typeof data.errors === "object") {
      fields = Object.fromEntries(
        Object.entries(data.errors).map(([key, value]) => [
          key,
          Array.isArray(value) ? value.map(String) : [String(value)],
        ])
      );
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(detail, response.status, fields);
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh = readRefresh();
  if (!refresh) return false;

  const response = await fetch(`${API_BASE_URL}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) {
    signOut();
    return false;
  }
  const data = await response.json();
  accessToken = data.access;
  if (data.refresh) writeRefresh(data.refresh); // rotation is on server-side
  return true;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Set for multipart uploads - the browser supplies the boundary itself. */
  formData?: FormData;
  retry?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, formData, retry = true } = options;

  if (!accessToken && readRefresh()) {
    await refreshAccessToken();
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });

  if (response.status === 401 && retry) {
    if (await refreshAccessToken()) {
      return request<T>(path, { ...options, retry: false });
    }
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --------------------------------------------------------------------------
// Auth
// --------------------------------------------------------------------------
export async function signIn(username: string, password: string): Promise<AdminUser> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw await parseError(response);

  const data = await response.json();
  accessToken = data.access;
  writeRefresh(data.refresh);
  return data.user as AdminUser;
}

export function signOut(): void {
  accessToken = null;
  writeRefresh(null);
}

export const fetchMe = () => request<AdminUser>("/api/auth/me/");

// --------------------------------------------------------------------------
// Announcements
// --------------------------------------------------------------------------
export function listAll(page = 1, search = "") {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (search) params.set("q", search);
  return request<Paginated<Announcement>>(`/api/admin/announcements/?${params}`);
}

export interface AnnouncementInput {
  title: string;
  body: string;
  published: boolean;
  slug?: string;
  source_page?: string;
  source_url?: string;
}

export interface SourcePage {
  slug: string;
  name: string;
  url: string;
}

/** The watched Facebook pages, served by the API so the list has one home. */
export async function fetchSourcePages(): Promise<SourcePage[]> {
  const response = await fetch(`${API_BASE_URL}/api/source-pages/`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) return [];
  const data = await response.json();
  return (data.results ?? []) as SourcePage[];
}

export const createAnnouncement = (input: AnnouncementInput) =>
  request<Announcement>("/api/admin/announcements/", { method: "POST", body: input });

export const updateAnnouncement = (id: number, input: Partial<AnnouncementInput>) =>
  request<Announcement>(`/api/admin/announcements/${id}/`, {
    method: "PATCH",
    body: input,
  });

export const deleteAnnouncement = (id: number) =>
  request<void>(`/api/admin/announcements/${id}/`, { method: "DELETE" });

// --------------------------------------------------------------------------
// Attachments
// --------------------------------------------------------------------------
export function uploadAttachment(
  announcementId: number,
  file: File,
  kind: "image" | "file",
  caption = ""
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("kind", kind);
  if (caption) formData.append("caption", caption);
  return request<Attachment>(`/api/admin/announcements/${announcementId}/attachments/`, {
    method: "POST",
    formData,
  });
}

export const deleteAttachment = (id: number) =>
  request<void>(`/api/admin/attachments/${id}/`, { method: "DELETE" });

export const updateAttachment = (id: number, data: { caption?: string; order?: number }) =>
  request<Attachment>(`/api/admin/attachments/${id}/`, { method: "PATCH", body: data });
