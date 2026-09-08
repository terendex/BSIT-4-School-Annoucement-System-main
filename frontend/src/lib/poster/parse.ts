/**
 * Turns what a publisher types into structured content.
 *
 * The editor deliberately has no row-adding buttons or drag handles. People
 * writing these are copying from a group chat or a memo, so every list is one
 * plain textarea and the parsing here is forgiving: pipes, dashes or runs of
 * spaces all separate columns, and indentation - tabs or spaces - is what
 * makes a sub-bullet.
 */

import type { BulletItem, Card } from "./blocks";

/** Strips the bullet characters people paste in from Word and Messenger. */
const LEADING_MARKER = /^[-*•●○▪·]\s*/;

export interface Section {
  heading: string;
  items: BulletItem[];
}

/** How far a line is indented, in columns, with a tab counting as four. */
function indentWidth(line: string): number {
  const leading = line.match(/^[\t ]*/)?.[0] ?? "";
  let width = 0;
  for (const char of leading) width += char === "\t" ? 4 : 1;
  return width;
}

/**
 * Nesting is read from how the indents in a list *compare*, not from how many
 * spaces each one is. Someone who indents with a tab, someone who uses two
 * spaces and someone who uses four all get the same levels out - which is
 * what each of them meant.
 */
function levelsByIndent(lines: string[]): Map<number, number> {
  const distinct = [...new Set(lines.map(indentWidth))].sort((a, b) => a - b);
  return new Map(distinct.map((width, rank) => [width, Math.min(2, rank)]));
}

function bulletFrom(line: string, levels: Map<number, number>): BulletItem | null {
  const text = line.trim().replace(LEADING_MARKER, "").trim();
  if (!text) return null;
  return { level: levels.get(indentWidth(line)) ?? 0, text };
}

/**
 * A bullet list. Indent a line to nest it under the line above; indent it
 * further again for a third level.
 */
export function parseList(raw: string): BulletItem[] {
  const lines = raw.split("\n").filter((line) => line.trim().length > 0);
  const levels = levelsByIndent(lines);
  return lines
    .map((line) => bulletFrom(line, levels))
    .filter((item): item is BulletItem => item !== null);
}

/**
 * Sections of bullets. A line ending in a colon, or prefixed with `#`, starts
 * a new section; everything under it is that section's list. Text before the
 * first heading becomes an unheaded section.
 */
export function parseSections(raw: string): Section[] {
  const lines = raw.split("\n").filter((line) => line.trim().length > 0);

  const isHeading = (line: string) =>
    line.startsWith("#") ||
    (indentWidth(line) === 0 && /:\s*$/.test(line) && line.trim().length <= 60);

  // Indents are ranked across the whole poster rather than per section, so a
  // sub-bullet under the first heading sits level with one under the last.
  const levels = levelsByIndent(lines.filter((line) => !isHeading(line)));

  const sections: Section[] = [];
  let current: Section | null = null;

  for (const line of lines) {
    if (isHeading(line)) {
      current = {
        heading: line.replace(/^#+\s*/, "").replace(/:\s*$/, "").trim(),
        items: [],
      };
      sections.push(current);
      continue;
    }

    if (!current) {
      current = { heading: "", items: [] };
      sections.push(current);
    }
    const item = bulletFrom(line, levels);
    if (item) current.items.push(item);
  }

  return sections.filter((section) => section.heading || section.items.length);
}

/**
 * Splits one schedule line into its columns.
 *
 * Bars are positional: `IT 123 | Mon | | B03` means the time is blank, not
 * that the room slides left into the time column, so empty cells are kept.
 * The looser separators are what someone types by hand, where a double space
 * is a separator rather than a blank column, so there the empties go.
 */
function splitColumns(line: string): string[] {
  const source = line.trim().replace(LEADING_MARKER, "");
  if (source.includes("|")) {
    return source.split(/\s*\|\s*/).map((cell) => cell.trim());
  }
  return source
    .split(/\s+[-–—]\s+|\s{2,}|\s*,\s*/)
    .map((cell) => cell.trim())
    .filter((cell) => cell.length > 0);
}

export interface Schedule {
  head: string[];
  rows: string[][];
}

/** Column names used when the publisher does not supply a header line. */
const DEFAULT_HEADS: Record<number, string[]> = {
  1: ["Subject"],
  2: ["Subject", "Schedule"],
  3: ["Subject", "Day", "Time"],
  4: ["Subject", "Day", "Time", "Room"],
  5: ["Subject", "Day", "Time", "Room", "Instructor"],
};

/**
 * A schedule. Every line is one entry:
 *
 *     IT 123 | Mon | 8:00-10:00 AM | B03
 *
 * Prefix a line with `#` to name the columns yourself. Rows are padded to the
 * widest one so a line missing its room does not shear the table.
 */
export function parseSchedule(raw: string): Schedule {
  const lines = raw.split("\n").filter((line) => line.trim().length > 0);
  if (lines.length === 0) return { head: [], rows: [] };

  let head: string[] = [];
  let body = lines;
  if (lines[0].trim().startsWith("#")) {
    head = splitColumns(lines[0].replace(/^#+\s*/, ""));
    body = lines.slice(1);
  }

  const rows = body
    .map(splitColumns)
    .filter((row) => row.some((cell) => cell.length > 0));
  if (rows.length === 0) return { head, rows };

  const columns = Math.max(head.length, ...rows.map((row) => row.length));
  if (head.length < columns) {
    head = DEFAULT_HEADS[columns] ?? DEFAULT_HEADS[5];
  }

  return {
    head: head.slice(0, columns),
    rows: rows.map((row) => {
      const padded = row.slice(0, columns);
      while (padded.length < columns) padded.push("");
      return padded;
    }),
  };
}

/**
 * Writes a schedule back out in the format `parseSchedule` reads.
 *
 * The editor shows a row of labelled boxes per subject, but what is stored is
 * still the plain text - so someone can switch to the text view, paste a list
 * in from a group chat, and switch back without anything being lost. The
 * column names are written out as a `#` line so the labels survive the trip.
 */
export function serialiseSchedule(head: string[], rows: string[][]): string {
  const lines = [`# ${head.join(" | ")}`];
  for (const row of rows) {
    // A row with nothing in it at all is left out rather than written as bars.
    if (row.every((cell) => cell.trim() === "")) continue;
    // Cells are written as typed. Trimming here would fight the editor: the
    // space someone just typed at the end of a word would be taken back off
    // before they could type the next letter.
    lines.push(head.map((_, column) => row[column] ?? "").join(" | "));
  }
  return lines.join("\n");
}

/**
 * Writes headed groups of points back out in the format `parseSections`
 * reads.
 *
 * `body` is the points exactly as typed, one per line, with the writer's own
 * indentation kept - nesting is ranked against the other lines, so their two
 * spaces or four both work. Every point gets an extra two spaces on top, so
 * one that happens to end in a colon ("Bring these:") cannot be read back as
 * a heading of its own.
 */
export function serialiseSections(groups: Array<{ heading: string; body: string }>): string {
  const lines: string[] = [];
  for (const group of groups) {
    const heading = group.heading.trim();
    const points = group.body.split("\n").filter((line) => line.trim() !== "");
    if (!heading && points.length === 0) continue;
    if (heading) lines.push(`${heading}:`);
    for (const point of points) lines.push(`  ${point}`);
  }
  return lines.join("\n");
}

const DAY_ORDER = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

/** Short forms people actually type, mapped to the full day name. */
const DAY_ALIASES: Record<string, string> = {
  m: "Monday",
  mon: "Monday",
  monday: "Monday",
  t: "Tuesday",
  tue: "Tuesday",
  tues: "Tuesday",
  tuesday: "Tuesday",
  w: "Wednesday",
  wed: "Wednesday",
  wednesday: "Wednesday",
  th: "Thursday",
  thu: "Thursday",
  thurs: "Thursday",
  thursday: "Thursday",
  f: "Friday",
  fri: "Friday",
  friday: "Friday",
  s: "Saturday",
  sat: "Saturday",
  saturday: "Saturday",
  sun: "Sunday",
  sunday: "Sunday",
  mw: "Mon / Wed",
  mwf: "Mon / Wed / Fri",
  tth: "Tue / Thu",
  tts: "Tue / Thu",
};

export function normaliseDay(value: string): string {
  const key = value.trim().toLowerCase().replace(/[.\s-]/g, "");
  return DAY_ALIASES[key] ?? value.trim();
}

/** Where a day sits in the week, for sorting groups. Unknown days go last. */
export function dayRank(value: string): number {
  const index = DAY_ORDER.indexOf(normaliseDay(value).toLowerCase());
  if (index !== -1) return index;
  // Combined days ("Mon / Wed") sort by their first day.
  const first = normaliseDay(value).split("/")[0].trim().toLowerCase();
  const combined = DAY_ORDER.indexOf(first);
  return combined === -1 ? DAY_ORDER.length : combined;
}

/**
 * Finds the column holding days of the week, if there is one. A column counts
 * when most of its cells are recognisable days - that is more reliable than
 * trusting a header the publisher may not have written.
 */
export function findDayColumn(schedule: Schedule): number {
  const { head, rows } = schedule;
  if (rows.length === 0) return -1;

  for (let column = 0; column < head.length; column += 1) {
    // The first column is the subject even when a subject is called "Friday".
    if (column === 0) continue;
    const hits = rows.filter((row) => {
      const key = (row[column] ?? "").trim().toLowerCase().replace(/[.\s-]/g, "");
      return key in DAY_ALIASES;
    }).length;
    if (hits >= Math.ceil(rows.length * 0.6)) return column;
  }
  return -1;
}

/** A handful of entries reads better as cards than as a table. */
export function scheduleCards(schedule: Schedule): Card[] {
  return schedule.rows.map((row) => ({
    title: row[0] ?? "",
    lines: [
      row
        .slice(1)
        .map((cell, index) => (schedule.head[index + 1] === "Day" ? normaliseDay(cell) : cell))
        .filter(Boolean)
        .join("  ·  "),
    ],
  }));
}
