/**
 * The look of a generated poster: one palette, one type scale, one page size.
 *
 * Everything a template draws is expressed in these tokens rather than raw
 * numbers, so a poster made for a suspension and one made for a meeting come
 * out of the same design - the only difference between them is the words.
 *
 * The palette is the Terendex logo's, copied from global.css so a poster sitting in
 * the feed next to the site chrome reads as the same publication.
 */

export const PURPLE = "#4c2a7b";
export const PURPLE_DEEP = "#23103d";
export const INK = "#1e142b";
export const MUTED = "#6a5a80";
export const PAPER = "#ffffff";
export const BAND = "#f2eef7";
export const LINE = "#dfd7ea";
export const GOLD = "#c9a227";

/** Tone modifiers, mirroring the taxonomy's `tone` field on each category. */
export const TONES: Record<string, string> = {
  danger: "#8f1d16",
  success: "#14603a",
  info: "#5b1f8f",
  warning: "#8a6410",
  accent: "#8c306a",
  neutral: PURPLE,
};

/**
 * The page is the size Messenger renders a shared link at.
 *
 * Facebook's large link card is 1.91:1 and it scales whatever it is given to
 * fit that, so a square poster arrives at barely half the width - every word
 * on it half the size it could have been. Authoring at the card's own shape
 * means nothing is scaled down on the way, which is the whole reason the
 * poster exists: to be readable in the chat without opening anything.
 *
 * Nothing grows. Content that does not fit continues onto a second page,
 * which is posted as a second image.
 */
export const PAGE_WIDTH = 1200;
export const PAGE_HEIGHT = 630;

export const MARGIN_X = 74;
export const MARGIN_TOP = 40;
export const MARGIN_BOTTOM = 48;

/** The purple rules that frame the top and bottom edge of every poster. */
export const FRAME_TOP = 14;
export const FRAME_BOTTOM = 18;

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
  banner: 52,
  hero: 104,
  headline: 44,
  section: 32,
  lead: 32,
  body: 27,
  bullet: 26,
  sub: 22,
  small: 20,
  caption: 17,
} as const;

/** The room a page has for content, once the margins are taken off. */
export const CONTENT_HEIGHT = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM;
