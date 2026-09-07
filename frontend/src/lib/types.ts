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

export interface AnnouncementSummary {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  published: boolean;
  cover_image: Attachment | null;
  image_count: number;
  file_count: number;
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
  is_staff: boolean;
  last_login: string | null;
}
