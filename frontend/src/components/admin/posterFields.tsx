/**
 * The two poster fields that are a list of things rather than a sentence:
 * a schedule (one row per subject) and per-subject sections (a heading and
 * the points under it).
 *
 * Both are edited as labelled boxes - a row of them per subject, the way the
 * announcement form itself is laid out - rather than as one blob of text with
 * bars and indents in it. What gets stored is still that text, so the two
 * views are interchangeable: paste a list in from a group chat, switch back,
 * and it is a set of rows.
 */

import { useState } from "react";
import {
  parseSchedule,
  parseSections,
  serialiseSchedule,
  serialiseSections,
} from "../../lib/poster/parse";
import type { Field } from "../../lib/poster";

interface FieldProps {
  field: Field;
  value: string;
  disabled: boolean;
  onChange: (next: string) => void;
}

/**
 * Keeps what is being typed as the editor's own state, and rebuilds it from
 * the stored text only when that text changed somewhere else - Reset text, or
 * the raw view.
 *
 * Editing the parsed text directly would mean re-parsing on every keystroke,
 * and the round trip tidies as it goes: the space just typed at the end of a
 * word is trimmed off before the next letter arrives. Holding the draft here
 * keeps the boxes exactly as typed.
 */
function useDraft<T>(
  value: string,
  parse: (text: string) => T,
  serialise: (draft: T) => string,
  onChange: (next: string) => void
) {
  const [draft, setDraft] = useState<T>(() => parse(value));
  const [mirror, setMirror] = useState(value);

  if (value !== mirror) {
    setMirror(value);
    setDraft(parse(value));
  }

  const update = (next: T) => {
    const text = serialise(next);
    setDraft(next);
    setMirror(text);
    onChange(text);
  };

  return [draft, update] as const;
}

/** Days offered in the dropdown, including the pairings a timetable uses. */
const DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
  "Mon / Wed",
  "Tue / Thu",
  "Mon / Wed / Fri",
];

/** A column holds days when it is named for them. */
const isDayColumn = (label: string) => /^day/i.test(label.trim());

/** The columns a schedule falls back to when the text names none of its own. */
const FALLBACK_HEAD = ["Subject", "Day", "Time", "Room"];

/** The bar separates columns, so it cannot also sit inside one. */
const cleanCell = (text: string) => text.replace(/[|\r\n]/g, " ");

function RawToggle({
  raw,
  onToggle,
  disabled,
}: {
  raw: boolean;
  onToggle: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      className="btn btn--sm btn--ghost poster-rows__toggle"
      onClick={onToggle}
      disabled={disabled}
    >
      {raw ? "Back to boxes" : "Edit as text"}
    </button>
  );
}

interface ScheduleDraft {
  head: string[];
  rows: string[][];
}

function toScheduleDraft(value: string): ScheduleDraft {
  const parsed = parseSchedule(value);
  const head = parsed.head.length ? parsed.head : FALLBACK_HEAD;
  return {
    head,
    rows: parsed.rows.length
      ? parsed.rows.map((row) => head.map((_, column) => row[column] ?? ""))
      : [head.map(() => "")],
  };
}

/** One row of boxes per subject, with a dropdown for the day. */
export function ScheduleField({ field, value, disabled, onChange }: FieldProps) {
  const [raw, setRaw] = useState(false);
  const [draft, update] = useDraft(
    value,
    toScheduleDraft,
    (next) => serialiseSchedule(next.head, next.rows),
    onChange
  );
  const { head, rows } = draft;

  // The subject column carries the longest text, so it gets the extra room.
  // Built from the head rather than fixed in CSS, because a template may name
  // three columns or five.
  const columns = {
    gridTemplateColumns: `2fr ${head.slice(1).map(() => "1fr").join(" ")} 34px`,
  };

  const setCell = (rowIndex: number, column: number, cell: string) =>
    update({
      head,
      rows: rows.map((row, index) =>
        index === rowIndex ? row.map((old, i) => (i === column ? cell : old)) : row
      ),
    });

  return (
    <div className="field">
      <span className="field__label">
        {field.label}
        <RawToggle raw={raw} onToggle={() => setRaw(!raw)} disabled={disabled} />
      </span>

      {raw ? (
        <textarea
          className="textarea poster__textarea"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          rows={10}
        />
      ) : (
        <>
          <div className="poster-rows">
            <div className="poster-rows__head" style={columns} aria-hidden="true">
              {head.map((label) => (
                <span key={label}>{label}</span>
              ))}
              <span />
            </div>

            {rows.map((row, rowIndex) => (
              <div className="poster-rows__row" style={columns} key={rowIndex}>
                {head.map((label, column) => (
                  <label key={label} className="poster-rows__cell">
                    <span className="poster-rows__label">{label}</span>
                    {isDayColumn(label) ? (
                      <select
                        className="select"
                        value={row[column] ?? ""}
                        onChange={(event) => setCell(rowIndex, column, event.target.value)}
                        disabled={disabled}
                        aria-label={`${label}, row ${rowIndex + 1}`}
                      >
                        <option value="">--</option>
                        {/* Whatever is already there, even if it is not on the list. */}
                        {row[column] && !DAYS.includes(row[column]) && (
                          <option value={row[column]}>{row[column]}</option>
                        )}
                        {DAYS.map((day) => (
                          <option key={day} value={day}>
                            {day}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="input"
                        type="text"
                        value={row[column] ?? ""}
                        onChange={(event) =>
                          setCell(rowIndex, column, cleanCell(event.target.value))
                        }
                        disabled={disabled}
                        aria-label={`${label}, row ${rowIndex + 1}`}
                      />
                    )}
                  </label>
                ))}

                <button
                  type="button"
                  className="btn btn--sm btn--ghost poster-rows__remove"
                  onClick={() =>
                    update({ head, rows: rows.filter((_, index) => index !== rowIndex) })
                  }
                  disabled={disabled || rows.length === 1}
                  aria-label={`Remove row ${rowIndex + 1}`}
                  title="Remove this row"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>

          <button
            type="button"
            className="btn btn--sm"
            onClick={() => update({ head, rows: [...rows, head.map(() => "")] })}
            disabled={disabled}
          >
            Add row
          </button>
        </>
      )}

      <span className="field__hint poster-rows__hint">
        {raw
          ? field.hint
          : "One row per subject. Leave a box empty if it does not apply - the poster " +
            "arranges itself around what is filled in."}
      </span>
    </div>
  );
}

interface Group {
  heading: string;
  body: string;
}

function toGroups(value: string): Group[] {
  const parsed = parseSections(value).map((section) => ({
    heading: section.heading,
    body: section.items.map((item) => `${"  ".repeat(item.level)}${item.text}`).join("\n"),
  }));
  return parsed.length ? parsed : [{ heading: "", body: "" }];
}

/** A heading and its points, one block per subject. */
export function SectionsField({ field, value, disabled, onChange }: FieldProps) {
  const [raw, setRaw] = useState(false);
  const [groups, update] = useDraft(value, toGroups, serialiseSections, onChange);

  const replace = (index: number, group: Group) =>
    update(groups.map((old, i) => (i === index ? group : old)));

  return (
    <div className="field">
      <span className="field__label">
        {field.label}
        <RawToggle raw={raw} onToggle={() => setRaw(!raw)} disabled={disabled} />
      </span>

      {raw ? (
        <textarea
          className="textarea poster__textarea"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          rows={12}
        />
      ) : (
        <>
          {groups.map((group, index) => (
            <div className="poster-group" key={index}>
              <div className="poster-group__head">
                <input
                  className="input"
                  type="text"
                  value={group.heading}
                  placeholder="Subject, e.g. IT 123"
                  onChange={(event) =>
                    replace(index, { ...group, heading: event.target.value.replace(/\n/g, " ") })
                  }
                  disabled={disabled}
                  aria-label={`Subject ${index + 1}`}
                />
                <button
                  type="button"
                  className="btn btn--sm btn--ghost poster-rows__remove"
                  onClick={() => update(groups.filter((_, i) => i !== index))}
                  disabled={disabled || groups.length === 1}
                  aria-label={`Remove ${group.heading || `subject ${index + 1}`}`}
                  title="Remove this subject and its points"
                >
                  &times;
                </button>
              </div>

              <textarea
                className="textarea poster__textarea"
                value={group.body}
                placeholder="One point per line. Indent a line to nest it."
                onChange={(event) => replace(index, { ...group, body: event.target.value })}
                disabled={disabled}
                rows={4}
                aria-label={`Points for ${group.heading || `subject ${index + 1}`}`}
              />
            </div>
          ))}

          <button
            type="button"
            className="btn btn--sm"
            onClick={() => update([...groups, { heading: "", body: "" }])}
            disabled={disabled}
          >
            Add subject
          </button>
        </>
      )}

      <span className="field__hint poster-rows__hint">
        {raw
          ? field.hint
          : "One block per subject. Indent a line in the points box to nest it under the one above."}
      </span>
    </div>
  );
}
