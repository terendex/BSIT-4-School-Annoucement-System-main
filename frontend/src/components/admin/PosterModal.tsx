import { useEffect, useMemo, useRef, useState } from "react";
import Modal from "./Modal";
import { ApiError, uploadAttachment } from "../../lib/adminClient";
import {
  canvasToFile,
  posterFilename,
  postersFrom,
  renderPoster,
  templatesFor,
  type Field,
  type Fitted,
  type Template,
} from "../../lib/poster";
import type { Announcement, Attachment } from "../../lib/types";

interface Props {
  /** When present, the finished poster can be attached straight to it. */
  announcement: Announcement | null;
  /** Seeds the headline when there is no announcement yet - the title being typed. */
  titleHint?: string;
  onClose: () => void;
  onAttached?: (attachment: Attachment) => void;
  /**
   * Hands the finished PNG back instead of uploading it, for the new
   * announcement dialog - there is nothing to attach it to until that post
   * has been saved.
   */
  onMade?: (poster: File) => void;
}

/** Every template's values, kept apart so switching back does not lose them. */
type Draft = Record<string, Record<string, string>>;

/**
 * Makes the poster that goes with an announcement.
 *
 * There is nothing to drag and nothing to position: pick the kind of notice,
 * type the words, and the layout engine sizes and arranges it. A long class
 * schedule and a one-line notice go through the same editor and come out
 * looking like the same publication.
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
  const [fitted, setFitted] = useState<Fitted | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const template = templates.find((item) => item.id === templateId) ?? templates[0];
  const values = draft[template.id] ?? template.defaults;

  // Redraw whenever the words change. Rendering is a few milliseconds of
  // canvas work, so there is no need to debounce the typing.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setFitted(renderPoster(canvas, postersFrom(template.id, values)));
  }, [template.id, values]);

  const setField = (name: string, next: string) => {
    setDraft((current) => ({
      ...current,
      [template.id]: { ...(current[template.id] ?? template.defaults), [name]: next },
    }));
    setNotice("");
  };

  const filename = posterFilename(
    template.id,
    announcement?.title || titleHint || template.name
  );

  const download = async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setError("");
    try {
      const file = await canvasToFile(canvas, filename);
      const url = URL.createObjectURL(file);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
      setNotice("Poster downloaded.");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handOver = async () => {
    const canvas = canvasRef.current;
    if (!canvas || !onMade) return;
    setBusy(true);
    setError("");
    try {
      onMade(await canvasToFile(canvas, filename));
      onClose();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const attach = async () => {
    const canvas = canvasRef.current;
    if (!canvas || !announcement) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const file = await canvasToFile(canvas, filename);
      const attachment = await uploadAttachment(announcement.id, file, "image", template.name);
      onAttached?.(attachment);
      setNotice(
        announcement.image_count === 0
          ? "Poster attached. It is now the Messenger preview image."
          : "Poster attached."
      );
    } catch (err) {
      setError((err as ApiError).message || "The poster could not be attached.");
    } finally {
      setBusy(false);
    }
  };

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
            Download PNG
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

          {template.fields.map((field) => (
            <PosterField
              key={field.name}
              field={field}
              value={values[field.name] ?? ""}
              disabled={busy}
              onChange={(next) => setField(field.name, next)}
            />
          ))}
        </div>

        <div className="poster__preview">
          <div className="poster__stage">
            <canvas ref={canvasRef} className="poster__canvas" />
          </div>
          <p className="field__hint poster__meta">
            {fitted
              ? `${fitted.width} x ${fitted.height} px${
                  fitted.scale < 1 ? ` - type reduced to ${Math.round(fitted.scale * 100)}%` : ""
                }`
              : "Rendering..."}
          </p>
          {fitted?.overflow && (
            <p className="alert alert--error poster__meta">
              There is more text here than fits on one poster. Shorten it, or split it across
              two.
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
}

/** One field, rendered as an input or a textarea depending on its type. */
function PosterField({
  field,
  value,
  disabled,
  onChange,
}: {
  field: Field;
  value: string;
  disabled: boolean;
  onChange: (next: string) => void;
}) {
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
          rows={prose ? 3 : field.type === "list" ? 6 : 10}
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
