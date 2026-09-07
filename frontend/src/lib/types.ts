export type AttachmentKind = "image" | "file";

export interface Attachment {
  id: number;
  kind: AttachmentKind;
  url: string;
  original_filename: string;
  content_type: string;
  size: number;
  width: number | null;
  height: number | null;
  caption: string;
  order: number;
  created_at: string;
}

export type Role = "admin" | "publisher";

/** One entry of the filter vocabulary served by /api/taxonomy/. */
export interface Category {
  slug: string;
  name: string;
  short: string;
  tone: string;
  description: string;
}

export interface YearLevel {
  slug: string;
  name: string;
  short: string;
}

export interface Taxonomy {
  categories: Category[];
  year_levels: YearLevel[];
}

export interface AnnouncementSummary {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  published: boolean;
  category: string;
  category_name: string;
  year_level: string;
  year_level_name: string;
  author: number | null;
  author_name: string;
  cover_image: Attachment | null;
  image_count: number;
  file_count: number;
  source_page: string;
  source_page_name: string;
  source_url: string;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Announcement extends AnnouncementSummary {
  body: string;
  images: Attachment[];
  files: Attachment[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: Role;
  is_staff: boolean;
  must_change_password: boolean;
  last_login: string | null;
}

/** A managed account as the admin's Publishers table sees it. */
export interface Publisher {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  invite_expired: boolean;
  invited_at: string | null;
  password_changed_at: string | null;
  last_login: string | null;
  announcement_count: number;
  /** Only present on the response that created or resent the invite. */
  invite_email_sent?: boolean;
  detail?: string;
  /**
   * The setup link for an outstanding invite. Not a credential: it lets its
   * holder choose a password, works once, and expires - so an admin can pass
   * it on by hand when email is unavailable.
   */
  invite_url?: string;
}
