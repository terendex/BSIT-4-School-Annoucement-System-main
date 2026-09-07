const DATE_FORMAT = new Intl.DateTimeFormat("en-PH", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Manila",
});

const DATE_ONLY = new Intl.DateTimeFormat("en-PH", {
  dateStyle: "medium",
  timeZone: "Asia/Manila",
});

export function formatDateTime(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : DATE_FORMAT.format(date);
}

// Table columns: the year is noise for anything posted this year, and it was
// costing the title column roughly 40px of width per row.
const COMPACT_THIS_YEAR = new Intl.DateTimeFormat("en-PH", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Manila",
});

const COMPACT_OTHER_YEAR = new Intl.DateTimeFormat("en-PH", {
  year: "numeric",
  month: "short",
  day: "numeric",
  timeZone: "Asia/Manila",
});

/** "Sep 8, 5:06 AM" this year, "Sep 8, 2025" for anything older. */
export function formatCompact(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return (sameYear ? COMPACT_THIS_YEAR : COMPACT_OTHER_YEAR).format(date);
}

export function formatDate(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : DATE_ONLY.format(date);
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );
  const value = bytes / 1024 ** exponent;
  return `${value >= 10 || exponent === 0 ? Math.round(value) : value.toFixed(1)} ${units[exponent]}`;
}

const FILE_ICONS: Record<string, string> = {
  pdf: "PDF",
  doc: "DOC",
  docx: "DOC",
  xls: "XLS",
  xlsx: "XLS",
  ppt: "PPT",
  pptx: "PPT",
  txt: "TXT",
  csv: "CSV",
  zip: "ZIP",
};

export function fileLabel(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return FILE_ICONS[ext] ?? "FILE";
}
