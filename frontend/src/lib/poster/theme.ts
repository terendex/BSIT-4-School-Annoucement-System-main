/**
 * The look of a generated poster: one palette, one type scale, one page size.
 *
 * Everything a template draws is expressed in these tokens rather than raw
 * numbers, so a poster made for a suspension and one made for a meeting come
 * out of the same design - the only difference between them is the words.
 *
 * The palette is the school's, copied from global.css so a poster sitting in
 * the feed next to the site chrome reads as the same publication.
 */

export const NAVY = "#1b2560";
export const NAVY_DEEP = "#10173d";
export const INK = "#14172b";
export const MUTED = "#4a5378";
export const PAPER = "#ffffff";
export const BAND = "#eef0f7";
export const LINE = "#d7dbea";
export const GOLD = "#c9a227";

/** Tone modifiers, mirroring the taxonomy's `tone` field on each category. */
export const TONES: Record<string, string> = {
  danger: "#8f1d16",
  success: "#14603a",
  info: "#1b2560",
  warning: "#8a6410",
  accent: "#4a2a7a",
  neutral: NAVY,
};

/**
 * Posters are authored at 1200 wide. That is the width Facebook and Messenger
 * ask for, and it divides cleanly into the margins below.
 */
export const PAGE_WIDTH = 1200;

/** A square is the starting shape. Tall content grows down from here. */
export const PAGE_MIN_HEIGHT = 1200;

/** The tallest a poster may grow before the layout has to shrink type instead. */
export const PAGE_MAX_HEIGHT = 2100;

/** Height is grown in whole steps so posters do not end up at odd sizes. */
export const PAGE_HEIGHT_STEP = 100;

export const MARGIN_X = 90;
export const MARGIN_TOP = 96;
export const MARGIN_BOTTOM = 96;

/** The navy rules that frame the top and bottom edge of every poster. */
export const FRAME_TOP = 26;
export const FRAME_BOTTOM = 34;

export const CONTENT_WIDTH = PAGE_WIDTH - MARGIN_X * 2;

/**
 * Canvas takes a full CSS font shorthand, so a stack works here exactly as it
 * does in the stylesheet and the poster picks up whatever the machine has.
 */
export const FAMILY = '"Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif';

export function font(size: number, weight: number | string = 400): string {
  return `${weight} ${Math.round(size)}px ${FAMILY}`;
}

/**
 * The type scale, in authoring pixels. The layout engine multiplies these by a
 * fit factor when a poster is over-full, so treat them as the ideal size and
 * not a promise.
 */
export const TYPE = {
  banner: 74,
  hero: 150,
  headline: 62,
  section: 46,
  lead: 42,
  body: 36,
  bullet: 34,
  sub: 30,
  small: 27,
  caption: 24,
} as const;
