/**
 * The vocabulary a poster is written in.
 *
 * A template never positions anything. It returns an ordered list of these
 * blocks and the layout engine decides where they land, how big the type is,
 * and how tall the page has to be. That is what lets one template cope with a
 * two-line notice and a twenty-subject schedule without being rewritten.
 */

export type Align = "left" | "center" | "right";

export interface BulletItem {
  text: string;
  /** 0 is a filled bullet, 1 a hollow sub-bullet, 2 a dash. */
  level: number;
}

export interface Card {
  title: string;
  lines: string[];
}

export type Block =
  /** The filled navy plate a poster is titled with (REMINDERS, NOTICE). */
  | { kind: "banner"; text: string }
  /** One enormous word or figure - the thing the poster is really about. */
  | { kind: "hero"; text: string }
  /** A large statement line, smaller than a hero but still the focus. */
  | { kind: "headline"; text: string; align?: Align; weight?: number }
  /** A banded section header with a navy rule, used to group a long poster. */
  | { kind: "section"; text: string }
  /** A wrapped paragraph. */
  | {
      kind: "text";
      text: string;
      size?: number;
      weight?: number;
      align?: Align;
      color?: string;
    }
  /** A nested bullet list. */
  | { kind: "bullets"; items: BulletItem[] }
  /** A tinted box for a tip or an aside. */
  | { kind: "note"; text: string }
  /** Label/value rows - date, time, venue. */
  | { kind: "kv"; pairs: Array<[string, string]> }
  /** A schedule grid. Splits into two columns on its own when rows pile up. */
  | { kind: "table"; head: string[]; rows: string[][] }
  /** Schedule entries as cards, for when there are only a few of them. */
  | { kind: "cards"; cards: Card[] }
  /** A hairline divider. */
  | { kind: "rule" }
  /** Deliberate breathing room, in authoring pixels. */
  | { kind: "space"; h: number };

export interface Poster {
  blocks: Block[];
  /** The colour of the bars framing the top and bottom of the page. */
  accent?: string;
}
