import { useEffect, useMemo, useRef, useState } from "react";
import Modal from "./Modal";
import { ApiError, uploadAttachment } from "../../lib/adminClient";
import { ScheduleField, SectionsField } from "./posterFields";
import {
  pageCaption,
  paintPage,
  planPoster,
  posterFiles,
  templatesFor,
  type Field,
  type Template,
} from "../../lib/poster";
import type { Announcement, Attachment } from "../../lib/types";

interface Props {
  /** When present, the finished poster can be attached straight to it. */
  announcement: Announcement | null;
  /** Seeds the headline when there is no announcement yet - the title being typed. */
  titleHint?: string;
  onClose: () => void;
  onAttached?: (attachments: Attachment[]) => void;
  /**
   * Hands the finished PNGs back instead of uploading them, for the new
   * announcement dialog - there is nothing to attach them to until that post
   * has been saved.
   */
  onMade?: (posters: File[]) => void;
}

/** Every template's values, kept apart so switching back does not lose them. */
type Draft = Record<string, Record<string, string>>;

/**
 * Makes the poster that goes with an announcement.
 *
 * There is nothing to drag and nothing to position: pick the kind of notice,
 * type the words, and the layout engine sizes and arranges it. Pages are the
 * shape Messenger shows a shared link at, and a poster with more on it than
 * one page holds continues onto a second image.
 */
export default function PosterModal({
  announcement,
  titleHint,
  onClose,
  onAttached,
  onMade,
}: Props) {
  const templates = useMemo(
    () => templatesFor(announcement?.category ?? "general"),
    [announcement?.category]
  );

  const [templateId, setTemplateId] = useState(templates[0].id);
  const [draft, setDraft] = useState<Draft>(() =>
    seed(templates, announcement?.title ?? titleHint ?? "")
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const template = templates.find((item) => item.id === templateId) ?? templates[0];
  const values = draft[template.id] ?? template.defaults;
  const title = announcement?.title || titleHint || template.name;

  // Laying out is a few milliseconds of measuring, so there is no need to
  // debounce the typing.
  const layout = useMemo(() => planPoster(template.id, values), [template.id, values]);

  const canvases = useRef<Array<HTMLCanvasElement | null>>([]);
  useEffect(() => {
    if (!layout) return;
    layout.pages.forEach((_, index) => {
      const canvas = canvases.current[index];
      if (canvas) paintPage(canvas, layout, index);
    });
  }, [layout]);

  const setField = (name: string, next: string) => {
    setDraft((current) => ({
      ...current,
      [template.id]: { ...(current[template.id] ?? template.defaults), [name]: next },
    }));
    setNotice("");
  };

  const pages = layout?.pages.length ?? 0;
  const sheets = pages > 1 ? "pages" : "poster";

  const download = async () => {
    if (!layout) return;
    setError("");
    try {
      const files = await posterFiles(layout, title, template.id);
      files.forEach((file, index) => {
        // Browsers throttle several downloads fired off at once.
        setTimeout(() => {
          const url = URL.createObjectURL(file);
          const link = document.createElement("a");
          link.href = url;
          link.download = file.name;
          link.click();
          URL.revokeObjectURL(url);
        }, index * 400);
      });
      setNotice(files.length > 1 ? `${files.length} pages downloaded.` : "Poster downloaded.");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handOver = async () => {
    if (!layout || !onMade) return;
    setBusy(true);
    setError("");
    try {
      onMade(await posterFiles(layout, title, template.id));
      onClose();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const attach = async () => {
    if (!layout || !announcement) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const files = await posterFiles(layout, title, template.id);
      const attached: Attachment[] = [];
      for (const [index, file] of files.entries()) {
        attached.push(
          await uploadAttachment(
            announcement.id,
            file,
            "image",
            pageCaption(template.name, index, files.length)
          )
        );
      }
      onAttached?.(attached);
      setNotice(
        announcement.image_count === 0
          ? `The ${sheets} are attached, and the first is now the Messenger preview image.`
          : `The ${sheets} are attached.`
      );
    } catch (err) {
      setError((err as ApiError).message || "The poster could not be attached.");
    } finally {
      setBusy(false);
    }
  };

  const main = template.fields.filter((field) => !field.optional);
  const extra = template.fields.filter((field) => field.optional);

  const renderFields = (fields: Field[]) =>
    pairUp(fields).map((row) =>
      row.length === 1 ? (
        <PosterField
          key={row[0].name}
          field={row[0]}
          value={values[row[0].name] ?? ""}
          disabled={busy}
          onChange={(next) => setField(row[0].name, next)}
        />
      ) : (
        <div className="poster-pair" key={row.map((field) => field.name).join("-")}>
          {row.map((field) => (
            <PosterField
              key={field.name}
              field={field}
              value={values[field.name] ?? ""}
              disabled={busy}
              onChange={(next) => setField(field.name, next)}
            />
          ))}
        </div>
      )
    );

  return (
    <Modal
      title={announcement ? `Poster - ${announcement.title}` : "Make a poster"}
      onClose={onClose}
      size="xl"
      busy={busy}
      footer={
        <>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setDraft((current) => ({ ...current, [template.id]: template.defaults }));
              setNotice("Sample text restored.");
            }}
            disabled={busy}
          >
            Reset text
          </button>
          <button type="button" className="btn btn--ghost" onClick={download} disabled={busy}>
            {pages > 1 ? `Download ${pages} images` : "Download PNG"}
          </button>
          {announcement && (
            <button type="button" className="btn" onClick={attach} disabled={busy}>
              {busy ? "Attaching..." : "Attach to announcement"}
            </button>
          )}
          {!announcement && onMade && (
            <button type="button" className="btn" onClick={handOver} disabled={busy}>
              Use this poster
            </button>
          )}
        </>
      }
    >
      {error && <p className="alert alert--error">{error}</p>}
      {notice && !error && <p className="alert alert--success">{notice}</p>}

      <div className="poster">
        <div className="poster__form">
          <label className="field">
            <span className="field__label">Template</span>
            <select
              className="select"
              value={template.id}
              onChange={(event) => {
                setTemplateId(event.target.value);
                setNotice("");
              }}
              disabled={busy}
            >
              {templates.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <span className="field__hint">{template.blurb}</span>
          </label>

          {renderFields(main)}

          {extra.length > 0 && (
            <details className="poster-more">
              <summary>More options ({extra.length})</summary>
              <div className="poster-more__body">{renderFields(extra)}</div>
            </details>
          )}
        </div>

        <div className="poster__preview">
          {layout ? (
            layout.pages.map((_, index) => (
              <figure className="poster__page" key={index}>
                <div className="poster__stage">
                  <canvas
                    className="poster__canvas"
                    ref={(element) => {
                      canvases.current[index] = element;
                    }}
                  />
                </div>
                {layout.pages.length > 1 && (
                  <figcaption className="field__hint poster__meta">
                    {index === 0
                      ? "Page 1 - the one Messenger shows on the link"
                      : `Page ${index + 1} of ${layout.pages.length}`}
                  </figcaption>
                )}
              </figure>
            ))
          ) : (
            <p className="field__hint">Rendering...</p>
          )}

          <p className="field__hint poster__meta">
            {pages > 1
              ? `${pages} images, each the size of a Messenger link preview.`
              : "Sized to fill a Messenger link preview."}
          </p>

          {layout?.overflow && (
            <p className="alert alert--error poster__meta">
              One part of this is too big for a page of its own. Shorten it.
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
}

/** Groups the short fields into pairs, so a date and a time share a row. */
function pairUp(fields: Field[]): Field[][] {
  const rows: Field[][] = [];
  for (const field of fields) {
    const last = rows[rows.length - 1];
    if (field.half && last?.length === 1 && last[0].half) last.push(field);
    else rows.push([field]);
  }
  return rows;
}

/** One field. Lists of things get their own row editors; the rest are boxes. */
function PosterField(props: {
  field: Field;
  value: string;
  disabled: boolean;
  onChange: (next: string) => void;
}) {
  if (props.field.type === "schedule") return <ScheduleField {...props} />;
  if (props.field.type === "sections") return <SectionsField {...props} />;

  const { field, value, disabled, onChange } = props;
  const multiline = field.type !== "line";
  const prose = field.type === "text";

  return (
    <label className="field">
      <span className="field__label">{field.label}</span>
      {multiline ? (
        <textarea
          className={`textarea poster__textarea${prose ? " poster__textarea--prose" : ""}`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          rows={prose ? 3 : 6}
          spellCheck
        />
      ) : (
        <input
          className="input"
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          maxLength={120}
        />
      )}
      {field.hint && <span className="field__hint">{field.hint}</span>}
    </label>
  );
}

/**
 * Starting values: each template's own sample text, with the announcement's
 * title dropped into the field that carries a sentence - never into a hero,
 * where a full title would be shrunk down to nothing.
 */
function seed(templates: Template[], title: string): Draft {
  const draft: Draft = {};
  for (const template of templates) {
    const values = { ...template.defaults };
    if (title) {
      for (const name of ["headline", "what"]) {
        if (name in values && template.fields.some((field) => field.name === name)) {
          values[name] = title;
          break;
        }
      }
    }
    draft[template.id] = values;
  }
  return draft;
}
