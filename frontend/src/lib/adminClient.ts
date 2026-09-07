/**
 * Browser-side admin API client.
 *
 * The access token is kept in memory only. The refresh token goes to
 * sessionStorage so a page reload does not sign you out, but it is gone when
 * the tab closes - a deliberate trade against long-lived tokens sitting in
 * localStorage.
 */
import { API_BASE_URL } from "./config";
import type {
  Announcement,
  AdminUser,
  Attachment,
  Paginated,
  Publisher,
  Taxonomy,
} from "./types";

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
/**
 * Sign in with an email address. The API field is still called `username`
 * because the bootstrap admin account may not have an email set.
 */
export async function signIn(email: string, password: string): Promise<AdminUser> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: email, password }),
  });
  if (!response.ok) throw await parseError(response);

  const data = await response.json();
  accessToken = data.access;
  writeRefresh(data.refresh);
  return data.user as AdminUser;
}

/**
 * Replace your password - forced after an invite, optional afterwards.
 *
 * The API returns a fresh token pair, because changing the password
 * invalidates the one used to make this very call.
 */
export async function changePassword(
  currentPassword: string,
  newPassword: string
): Promise<AdminUser> {
  const data = await request<{ access: string; refresh: string; user: AdminUser }>(
    "/api/auth/change-password/",
    {
      method: "POST",
      body: { current_password: currentPassword, new_password: newPassword },
    }
  );
  accessToken = data.access;
  writeRefresh(data.refresh);
  return data.user;
}

export function signOut(): void {
  accessToken = null;
  writeRefresh(null);
}

export const fetchMe = () => request<AdminUser>("/api/auth/me/");

// --------------------------------------------------------------------------
// Invite links (unauthenticated - the token is the credential)
// --------------------------------------------------------------------------
export interface InviteDetail {
  email: string;
  full_name: string;
  expires_at: string | null;
}

/** Who an invite link belongs to, and whether it is still good. */
export async function fetchInvite(token: string): Promise<InviteDetail> {
  const response = await fetch(
    `${API_BASE_URL}/api/auth/invite/${encodeURIComponent(token)}/`,
    { headers: { Accept: "application/json" } }
  );
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as InviteDetail;
}

/**
 * Spend an invite link. The account gets its first usable password here, set
 * by its owner, and the response signs them in.
 */
export async function acceptInvite(token: string, newPassword: string): Promise<AdminUser> {
  const response = await fetch(`${API_BASE_URL}/api/auth/accept-invite/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  if (!response.ok) throw await parseError(response);

  const data = await response.json();
  accessToken = data.access;
  writeRefresh(data.refresh);
  return data.user as AdminUser;
}

// --------------------------------------------------------------------------
// Announcements
// --------------------------------------------------------------------------
export interface AdminListFilters {
  search?: string;
  category?: string;
  year?: string;
  mine?: boolean;
}

export function listAll(page = 1, filters: AdminListFilters = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (filters.search) params.set("q", filters.search);
  if (filters.category) params.set("category", filters.category);
  if (filters.year) params.set("year", filters.year);
  if (filters.mine) params.set("mine", "true");
  return request<Paginated<Announcement>>(`/api/admin/announcements/?${params}`);
}

export interface AnnouncementInput {
  title: string;
  body: string;
  published: boolean;
  category?: string;
  year_level?: string;
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

// --------------------------------------------------------------------------
// Taxonomy
// --------------------------------------------------------------------------
const EMPTY_TAXONOMY: Taxonomy = { categories: [], year_levels: [] };

/** Categories and year levels, so labels live in one place - the API. */
export async function fetchTaxonomy(): Promise<Taxonomy> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/taxonomy/`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return EMPTY_TAXONOMY;
    return (await response.json()) as Taxonomy;
  } catch {
    return EMPTY_TAXONOMY;
  }
}

// --------------------------------------------------------------------------
// Publishers (admin only)
// --------------------------------------------------------------------------
export async function listPublishers(): Promise<Publisher[]> {
  const data = await request<{ results: Publisher[] }>("/api/admin/publishers/");
  return data.results;
}

/** Create the account and mail the temporary password. */
export const invitePublisher = (email: string, fullName = "") =>
  request<Publisher>("/api/admin/publishers/", {
    method: "POST",
    body: { email, full_name: fullName },
  });

export const resendInvite = (id: number) =>
  request<Publisher>(`/api/admin/publishers/${id}/resend-invite/`, { method: "POST" });

export const updatePublisher = (
  id: number,
  data: { is_active?: boolean; full_name?: string }
) => request<Publisher>(`/api/admin/publishers/${id}/`, { method: "PATCH", body: data });

export const deletePublisher = (id: number) =>
  request<void>(`/api/admin/publishers/${id}/`, { method: "DELETE" });
