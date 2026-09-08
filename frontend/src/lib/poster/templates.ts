/**
 * The posters a publisher can make, one per kind of announcement.
 *
 * A template is a list of fields and a function that turns their values into
 * blocks. It never decides a size or a position - that is the layout engine's
 * job - so every template here is only ever about *what* is said, which is the
 * whole point: to make a new poster you change the words, nothing else.
 *
 * Every category in the taxonomy has at least one template pointed at it, and
 * `templatesFor` puts those first when the editor is opened from an
 * announcement already filed under that category.
 */

import type { Block, Poster } from "./blocks";
import { MUTED, TONES, TYPE } from "./theme";
import {
  dayRank,
  findDayColumn,
  normaliseDay,
  parseList,
  parseSchedule,
  parseSections,
  scheduleCards,
  type Schedule,
} from "./parse";

export type FieldType = "line" | "text" | "list" | "schedule" | "sections";

export interface Field {
  name: string;
  label: string;
  type: FieldType;
  hint?: string;
  placeholder?: string;
}

export interface Template {
  id: string;
  name: string;
  blurb: string;
  /** Taxonomy category slugs this template suits. */
  categories: string[];
  fields: Field[];
  /** Prefilled so a newly opened editor already shows a finished poster. */
  defaults: Record<string, string>;
  /**
   * The poster these words make. A template may return several arrangements
   * of the same content, best first, and the layout engine keeps whichever
   * fits well enough - that is how a schedule decides between one long table
   * and a group per day.
   */
  build: (values: Record<string, string>) => Poster | Poster[];
}

/** Reads a field, trimmed, with empty strings treated as absent. */
function value(values: Record<string, string>, name: string): string {
  return (values[name] ?? "").trim();
}

/** Drops the blocks whose text the publisher left blank. */
function compact(blocks: Array<Block | null>): Block[] {
  return blocks.filter((block): block is Block => block !== null);
}

function textBlock(
  text: string,
  options: Partial<Extract<Block, { kind: "text" }>> = {}
): Block | null {
  return text ? { kind: "text", text, ...options } : null;
}

function bulletBlock(raw: string): Block | null {
  const items = parseList(raw);
  return items.length ? { kind: "bullets", items } : null;
}

function noteBlock(text: string): Block | null {
  return text ? { kind: "note", text } : null;
}

function heroBlock(text: string): Block | null {
  return text ? { kind: "hero", text } : null;
}

/** Label/value rows, keeping only the pairs that were filled in. */
function detailBlock(pairs: Array<[string, string]>): Block | null {
  const filled = pairs.filter(([, detail]) => detail.length > 0);
  return filled.length ? { kind: "kv", pairs: filled } : null;
}

// --------------------------------------------------------------------------
// Schedules
// --------------------------------------------------------------------------

/** Up to this many entries read better as cards than as a grid. */
const CARD_LIMIT = 4;
/** Below this, a day heading per subject is mostly headings. */
const GROUP_MIN_ROWS = 8;
/** A day only earns its heading if it has this many subjects under it. */
const GROUP_MIN_PER_DAY = 2.5;
/** More day groups than this and the poster is mostly headings. */
const GROUP_MAX_DAYS = 7;

/**
 * Decides how a schedule should be presented, which is the one thing a
 * publisher should not have to think about.
 *
 * A handful of entries want the room to breathe, so they get cards. Beyond
 * that this returns the arrangements worth considering, best first: grouped
 * under a heading per day, which is what a reader of a weekly schedule scans
 * for, and the same entries as one long table. The layout engine picks
 * between them by which one it can set at a readable size - so a full week
 * stays grouped, and a list long enough that grouping would shrink the type
 * falls back to the table, which can be set in two columns side by side.
 *
 * How *big* it ends up is the layout engine's call too: it grows the page,
 * splits a long table into two columns, then shrinks the type, in that order.
 */
export function scheduleArrangements(schedule: Schedule): Block[][] {
  const { head, rows } = schedule;
  if (rows.length === 0) return [[]];

  if (rows.length <= CARD_LIMIT) {
    return [[{ kind: "cards", cards: scheduleCards(schedule) }]];
  }

  const flat: Block[] = [{ kind: "table", head, rows }];
  const grouped = groupedByDay(schedule);
  return grouped ? [grouped, flat] : [flat];
}

/**
 * The schedule broken up under a heading per day, or null when the days do
 * not divide it usefully - no day column, only one day, a day for nearly
 * every subject, or so many days that the poster is mostly headings.
 */
function groupedByDay(schedule: Schedule): Block[] | null {
  const { head, rows } = schedule;
  const dayColumn = findDayColumn(schedule);
  if (dayColumn === -1 || rows.length < GROUP_MIN_ROWS) return null;

  const groups = new Map<string, string[][]>();
  for (const row of rows) {
    const day = normaliseDay(row[dayColumn] ?? "");
    const group = groups.get(day);
    // Everything but the day itself - the section heading carries that.
    const rest = row.filter((_, index) => index !== dayColumn);
    if (group) group.push(rest);
    else groups.set(day, [rest]);
  }

  if (
    groups.size < 2 ||
    groups.size > GROUP_MAX_DAYS ||
    rows.length / groups.size < GROUP_MIN_PER_DAY
  ) {
    return null;
  }

  const restHead = head.filter((_, index) => index !== dayColumn);
  return [...groups.entries()]
    .sort((a, b) => dayRank(a[0]) - dayRank(b[0]))
    .flatMap(([day, dayRows], index): Block[] => [
      { kind: "section", text: day },
      // Only the first day names the columns. Repeating identical headers
      // under every heading is noise, and on a full week it is a whole extra
      // inch of poster.
      { kind: "table", head: index === 0 ? restHead : [], rows: dayRows },
    ]);
}

/** One poster per schedule arrangement, with the same words around it. */
function scheduleVariants(
  before: Array<Block | null>,
  schedule: Schedule,
  after: Array<Block | null>
): Poster[] {
  return scheduleArrangements(schedule).map((blocks) => ({
    blocks: compact([...before, ...blocks, ...after]),
  }));
}

// --------------------------------------------------------------------------
// Shared field definitions
// --------------------------------------------------------------------------

const BANNER_FIELD: Field = {
  name: "banner",
  label: "Banner",
  type: "line",
  hint: "The plate across the top.",
};

const FOOTNOTE_FIELD: Field = {
  name: "footnote",
  label: "Closing line",
  type: "line",
  hint: "Optional. Sits under a divider at the foot of the poster.",
};

const SCHEDULE_FIELD: Field = {
  name: "schedule",
  label: "Entries",
  type: "schedule",
  hint:
    "One per line, columns separated by | - for example: IT 123 | Mon | 8:00-10:00 AM | B03. " +
    "Start a line with # to name the columns yourself.",
};

/** The divider-and-closing-line ending most of these posters share. */
function footer(footnote: string): Block[] {
  if (!footnote) return [];
  return [
    { kind: "rule" },
    { kind: "text", text: footnote, size: TYPE.body, weight: 700, align: "center" },
  ];
}

// --------------------------------------------------------------------------
// The templates
// --------------------------------------------------------------------------

export const TEMPLATES: Template[] = [
  {
    id: "notice",
    name: "Notice",
    blurb: "A short notice built around one figure or phrase.",
    categories: ["general", "enrollment"],
    fields: [
      BANNER_FIELD,
      { name: "lead", label: "Line above", type: "line" },
      { name: "hero", label: "The figure", type: "line", hint: "Kept to one line and sized to fit." },
      { name: "trail", label: "Line below", type: "text" },
      FOOTNOTE_FIELD,
    ],
    defaults: {
      banner: "NOTICE",
      lead: "A collection of",
      hero: "₱100",
      trail: "will be made once the go signal is given.",
      footnote: "Please stay tuned for further updates.",
    },
    build: (values) => ({
      blocks: compact([
        { kind: "banner", text: value(values, "banner") || "NOTICE" },
        { kind: "space", h: 40 },
        textBlock(value(values, "lead"), { size: TYPE.lead, align: "center", color: MUTED }),
        heroBlock(value(values, "hero")),
        textBlock(value(values, "trail"), { size: TYPE.lead, align: "center" }),
        ...footer(value(values, "footnote")),
      ]),
    }),
  },

  {
    id: "meeting",
    name: "Meeting",
    blurb: "Date, time and room for a meeting or a call.",
    categories: ["general", "event"],
    fields: [
      BANNER_FIELD,
      { name: "lead", label: "Line above", type: "text" },
      { name: "hero", label: "What it is", type: "line" },
      { name: "date", label: "Date", type: "line" },
      { name: "time", label: "Time", type: "line" },
      { name: "place", label: "Where", type: "line" },
      FOOTNOTE_FIELD,
    ],
    defaults: {
      banner: "REMINDER",
      lead: "Please be advised that we will have a",
      hero: "MEETING",
      date: "Tuesday, September 8",
      time: "10:30 AM",
      place: "Room B03",
      footnote: "Thank you for your cooperation.",
    },
    build: (values) => ({
      blocks: compact([
        { kind: "banner", text: value(values, "banner") || "REMINDER" },
        { kind: "space", h: 40 },
        textBlock(value(values, "lead"), { size: TYPE.lead, align: "center", color: MUTED }),
        heroBlock(value(values, "hero")),
        textBlock(value(values, "date"), { size: TYPE.lead, weight: 700, align: "center" }),
        textBlock(value(values, "time"), { size: TYPE.headline, weight: 700, align: "center" }),
        textBlock(value(values, "place"), { size: TYPE.body, weight: 600, align: "center" }),
        ...footer(value(values, "footnote")),
      ]),
    }),
  },

  {
    id: "reminders",
    name: "Reminders",
    blurb: "Grouped reminders - a heading per subject, bullets underneath.",
    categories: ["general", "exam"],
    fields: [
      BANNER_FIELD,
      {
        name: "body",
        label: "Sections",
        type: "sections",
        hint:
          "End a line with a colon to start a section. Indent a line (tab or two spaces) " +
          "to make it a sub-bullet.",
      },
      { name: "tip", label: "Tip box", type: "text", hint: "Optional. Tinted box at the foot." },
    ],
    defaults: {
      banner: "REMINDERS",
      body: [
        "IT 123:",
        "Quiz 1 on Tuesday",
        "  Bring your own formatted flashdrive (labeled with your name)",
        "  It is hands-on",
        "Practice core command line basics:",
        "  Path finding",
        "  Creating folders",
        "  Copy folders and files",
        "IT 124:",
        "Prepare your system and papers for pilot testing",
        "  Do this as soon as possible to gain leverage",
        "System checking: ask Sir Jake for a schedule",
      ].join("\n"),
      tip:
        "Use && to run multiple commands at once. Press the up arrow to reuse previous commands.",
    },
    build: (values) => {
      const sections = parseSections(value(values, "body"));
      return {
        blocks: compact([
          { kind: "banner", text: value(values, "banner") || "REMINDERS" },
          ...sections.flatMap((section): Array<Block | null> => [
            section.heading ? { kind: "section", text: section.heading } : null,
            section.items.length ? { kind: "bullets", items: section.items } : null,
          ]),
          noteBlock(value(values, "tip")),
        ]),
      };
    },
  },

  {
    id: "class-schedule",
    name: "Class schedule",
    blurb: "Subjects, days, times and rooms. Arranges itself as the list grows.",
    categories: ["general", "enrollment"],
    fields: [
      BANNER_FIELD,
      { name: "subtitle", label: "Line under the banner", type: "line" },
      SCHEDULE_FIELD,
      { name: "note", label: "Note", type: "text", hint: "Optional. Tinted box at the foot." },
    ],
    defaults: {
      banner: "CLASS SCHEDULE",
      subtitle: "BSIT 4 - First Semester",
      schedule: [
        "IT 123 - Systems Administration | Mon | 8:00 - 10:00 AM | B03",
        "IT 124 - Capstone 2 | Mon | 1:00 - 4:00 PM | Lab 2",
        "CFE 6A | Tue | 9:00 - 10:30 AM | A11",
        "IT 125 - Networking | Tue | 1:00 - 4:00 PM | Lab 1",
        "IT 123 - Systems Administration | Wed | 8:00 - 10:00 AM | B03",
        "PE 4 | Wed | 3:00 - 5:00 PM | Gym",
        "IT 124 - Capstone 2 | Thu | 8:00 - 11:00 AM | Lab 2",
        "IT 126 - Elective | Thu | 1:00 - 3:00 PM | B05",
        "CFE 6A | Fri | 9:00 - 10:30 AM | A11",
        "IT 125 - Networking | Fri | 1:00 - 4:00 PM | Lab 1",
      ].join("\n"),
      note: "",
    },
    build: (values) =>
      scheduleVariants(
        [
          { kind: "banner", text: value(values, "banner") || "CLASS SCHEDULE" },
          textBlock(value(values, "subtitle"), {
            size: TYPE.body,
            weight: 600,
            align: "center",
            color: MUTED,
          }),
        ],
        parseSchedule(value(values, "schedule")),
        [noteBlock(value(values, "note"))]
      ),
  },

  {
    id: "exam",
    name: "Exam schedule",
    blurb: "Exam dates per subject, with a permit or coverage note.",
    categories: ["exam"],
    fields: [
      BANNER_FIELD,
      { name: "subtitle", label: "Line under the banner", type: "line" },
      {
        ...SCHEDULE_FIELD,
        hint:
          "One per line: Subject | Date | Time | Room. Start a line with # to name the " +
          "columns yourself.",
      },
      { name: "note", label: "Note", type: "text" },
      FOOTNOTE_FIELD,
    ],
    defaults: {
      banner: "MIDTERM EXAMS",
      subtitle: "BSIT 4 - September 15 to 19",
      schedule: [
        "# Subject | Date | Time | Room",
        "IT 123 | Sept 15 | 8:00 - 10:00 AM | B03",
        "IT 124 | Sept 16 | 8:00 - 10:00 AM | Lab 2",
        "IT 125 | Sept 17 | 1:00 - 3:00 PM | Lab 1",
        "CFE 6A | Sept 18 | 9:00 - 11:00 AM | A11",
        "IT 126 | Sept 19 | 8:00 - 10:00 AM | B05",
      ].join("\n"),
      note: "No permit, no exam. Claim your permit at the Registrar before your first schedule.",
      footnote: "Good luck, everyone.",
    },
    build: (values) =>
      scheduleVariants(
        [
          { kind: "banner", text: value(values, "banner") || "EXAM SCHEDULE" },
          textBlock(value(values, "subtitle"), {
            size: TYPE.body,
            weight: 600,
            align: "center",
            color: MUTED,
          }),
        ],
        parseSchedule(value(values, "schedule")),
        [noteBlock(value(values, "note")), ...footer(value(values, "footnote"))]
      ),
  },

  {
    id: "suspension",
    name: "Class suspension",
    blurb: "No classes - weather, calamity, or an ordered suspension.",
    categories: ["suspension"],
    fields: [
      BANNER_FIELD,
      { name: "hero", label: "The call", type: "line" },
      { name: "scope", label: "Who it covers", type: "line" },
      { name: "when", label: "When", type: "line" },
      { name: "reason", label: "Reason", type: "text" },
      { name: "note", label: "What happens next", type: "text" },
      FOOTNOTE_FIELD,
    ],
    defaults: {
      banner: "CLASS SUSPENSION",
      hero: "NO CLASSES",
      scope: "All year levels",
      when: "Monday, September 8",
      reason: "Following the suspension ordered by the local government due to Typhoon signal no. 2.",
      note: "Online submissions already due today still stand. Watch this page for the resumption of classes.",
      footnote: "Stay safe.",
    },
    build: (values) => ({
      accent: TONES.danger,
      blocks: compact([
        { kind: "banner", text: value(values, "banner") || "CLASS SUSPENSION" },
        { kind: "space", h: 30 },
        heroBlock(value(values, "hero")),
        detailBlock([
          ["For", value(values, "scope")],
          ["When", value(values, "when")],
        ]),
        textBlock(value(values, "reason"), { size: TYPE.body, align: "center" }),
        noteBlock(value(values, "note")),
        ...footer(value(values, "footnote")),
      ]),
    }),
  },

  {
    id: "holiday",
    name: "Holiday",
    blurb: "A declared holiday or non-working day.",
    categories: ["holiday"],
    fields: [
      BANNER_FIELD,
      { name: "hero", label: "The holiday", type: "line" },
      { name: "when", label: "Date", type: "line" },
      { name: "detail", label: "Detail", type: "text" },
      { name: "resume", label: "Classes resume", type: "line" },
      FOOTNOTE_FIELD,
    ],
    defaults: {
      banner: "HOLIDAY",
      hero: "NO CLASSES",
      when: "Monday, September 8",
      detail: "In observance of the declared special non-working holiday.",
      resume: "Tuesday, September 9",
      footnote: "",
    },
    build: (values) => ({
      blocks: compact([
        { kind: "banner", text: value(values, "banner") || "HOLIDAY" },
        { kind: "space", h: 30 },
        heroBlock(value(values, "hero")),
        textBlock(value(values, "detail"), { size: TYPE.lead, align: "center" }),
        detailBlock([
          ["Date", value(values, "when")],
          ["Classes resume", value(values, "resume")],
        ]),
        ...footer(value(values, "footnote")),
      ]),
    }),
  },

  {
    id: "enrollment",
    name: "Enrollment",
    blurb: "Enrollment or clearance window, with the steps to follow.",
    categories: ["enrollment"],
    fields: [
      BANNER_FIELD,
      { name: "subtitle", label: "Line under the banner", type: "line" },
      { name: "when", label: "Window", type: "line" },
      { name: "where", label: "Where", type: "line" },
      { name: "who", label: "Who", type: "line" },
      { name: "steps", label: "Steps", type: "list", hint: "One per line. Indent to nest." },
      { name: "note", label: "Note", type: "text" },
    ],
    defaults: {
      banner: "ENROLLMENT",
      subtitle: "Second Semester, A.Y. 2025-2026",
      when: "September 15 - 26",
      where: "Registrar's Office / Student Portal",
      who: "All year levels",
      steps: [
        "Settle any remaining balance at the Cashier",
        "Secure your clearance from your adviser",
        "Encode your subjects in the Student Portal",
        "  Screenshot the confirmation page",
        "Have your load approved by the Program Head",
      ].join("\n"),
      note: "Late enrollment is subject to a surcharge. Bring a valid ID for every transaction.",
    },
    build: (values) => ({
      blocks: compact([
        { kind: "banner", text: value(values, "banner") || "ENROLLMENT" },
        textBlock(value(values, "subtitle"), {
          size: TYPE.body,
          weight: 600,
          align: "center",
          color: MUTED,
        }),
        detailBlock([
          ["When", value(values, "when")],
          ["Where", value(values, "where")],
          ["Who", value(values, "who")],
        ]),
        bulletBlock(value(values, "steps")),
        noteBlock(value(values, "note")),
      ]),
    }),
  },

  {
    id: "event",
    name: "Event",
    blurb: "A seminar, mass, org activity or school event.",
    categories: ["event"],
    fields: [
      BANNER_FIELD,
      { name: "hero", label: "Event name", type: "line" },
      { name: "tagline", label: "Tagline", type: "text" },
      { name: "when", label: "Date", type: "line" },
      { name: "time", label: "Time", type: "line" },
      { name: "place", label: "Venue", type: "line" },
      { name: "who", label: "Who should attend", type: "line" },
      { name: "details", label: "Details", type: "list" },
      FOOTNOTE_FIELD,
    ],
    defaults: {
      banner: "EVENT",
      hero: "IT WEEK 2026",
      tagline: "Three days of talks, competitions and demos.",
      when: "September 22 - 24",
      time: "8:00 AM onwards",
      place: "College Gymnasium",
      who: "All BSIT students",
      details: [
        "Wear your prescribed uniform on opening day",
        "Register at the booth beside the main entrance",
        "Attendance is credited per session",
      ].join("\n"),
      footnote: "See you there.",
    },
    build: (values) => ({
      blocks: compact([
        { kind: "banner", text: value(values, "banner") || "EVENT" },
        { kind: "space", h: 20 },
        heroBlock(value(values, "hero")),
        textBlock(value(values, "tagline"), { size: TYPE.lead, align: "center", color: MUTED }),
        detailBlock([
          ["Date", value(values, "when")],
          ["Time", value(values, "time")],
          ["Venue", value(values, "place")],
          ["For", value(values, "who")],
        ]),
        bulletBlock(value(values, "details")),
        ...footer(value(values, "footnote")),
      ]),
    }),
  },

  {
    id: "deadline",
    name: "Deadline",
    blurb: "A submission or payment deadline and what to hand in.",
    categories: ["general", "enrollment", "exam"],
    fields: [
      BANNER_FIELD,
      { name: "what", label: "What is due", type: "line" },
      { name: "hero", label: "Deadline", type: "line", hint: "The date, set large." },
      { name: "time", label: "Cut-off time", type: "line" },
      { name: "where", label: "Where to submit", type: "line" },
      { name: "requirements", label: "What to submit", type: "list" },
      { name: "note", label: "Note", type: "text" },
    ],
    defaults: {
      banner: "DEADLINE",
      what: "Capstone 2 pilot testing papers",
      hero: "SEPTEMBER 19",
      time: "5:00 PM",
      where: "Submit to Sir Jake, Faculty Room 2",
      requirements: [
        "Printed and signed test plan",
        "Respondent consent forms",
        "  One per respondent",
        "System walkthrough script",
      ].join("\n"),
      note: "Late submissions will not be accepted. Have your adviser sign before you print.",
    },
    build: (values) => ({
      blocks: compact([
        { kind: "banner", text: value(values, "banner") || "DEADLINE" },
        textBlock(value(values, "what"), { size: TYPE.lead, align: "center", color: MUTED }),
        heroBlock(value(values, "hero")),
        detailBlock([
          ["Cut-off", value(values, "time")],
          ["Where", value(values, "where")],
        ]),
        bulletBlock(value(values, "requirements")),
        noteBlock(value(values, "note")),
      ]),
    }),
  },

  {
    id: "general",
    name: "General announcement",
    blurb: "A headline, a paragraph and a list - for anything else.",
    categories: ["general", "suspension", "holiday", "exam", "enrollment", "event"],
    fields: [
      BANNER_FIELD,
      { name: "headline", label: "Headline", type: "line" },
      { name: "body", label: "Body", type: "text" },
      { name: "points", label: "Points", type: "list", hint: "One per line. Indent to nest." },
      { name: "note", label: "Note", type: "text" },
      FOOTNOTE_FIELD,
    ],
    defaults: {
      banner: "ANNOUNCEMENT",
      headline: "System checking this week",
      body:
        "All groups are asked to prepare their systems and papers ahead of the scheduled " +
        "checking. Coordinate with your adviser for your slot.",
      points: [
        "Bring a working build, not a mockup",
        "Prepare your test data beforehand",
        "  At least ten sample records",
      ].join("\n"),
      note: "",
      footnote: "",
    },
    build: (values) => ({
      blocks: compact([
        { kind: "banner", text: value(values, "banner") || "ANNOUNCEMENT" },
        { kind: "space", h: 20 },
        value(values, "headline")
          ? { kind: "headline", text: value(values, "headline") }
          : null,
        textBlock(value(values, "body"), { size: TYPE.body, align: "center" }),
        bulletBlock(value(values, "points")),
        noteBlock(value(values, "note")),
        ...footer(value(values, "footnote")),
      ]),
    }),
  },
];

export const TEMPLATE_BY_ID = new Map(TEMPLATES.map((template) => [template.id, template]));

/**
 * The templates, with the ones that suit this announcement's category first.
 * Nothing is hidden - a publisher filing under "general" may still want the
 * exam schedule layout.
 */
export function templatesFor(category: string): Template[] {
  const suited = TEMPLATES.filter((template) => template.categories.includes(category));
  const rest = TEMPLATES.filter((template) => !template.categories.includes(category));
  return [...suited, ...rest];
}
