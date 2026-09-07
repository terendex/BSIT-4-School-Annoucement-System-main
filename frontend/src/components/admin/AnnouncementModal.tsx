import { useState } from "react";
import Modal from "./Modal";
import {
  ApiError,
  createAnnouncement,
  updateAnnouncement,
} from "../../lib/adminClient";
import type { Announcement } from "../../lib/types";

interface Props {
  /** Omit to create a new announcement. */
  announcement?: Announcement | null;
  onClose: () => void;
  onSaved: (saved: Announcement) => void;
}

export default function AnnouncementModal({ announcement, onClose, onSaved }: Props) {
  const isEdit = Boolean(announcement);
  const [title, setTitle] = useState(announcement?.title ?? "");
  const [body, setBody] = useState(announcement?.body ?? "");
  const [slug, setSlug] = useState(announcement?.slug ?? "");
  const [published, setPublished] = useState(announcement?.published ?? true);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setFieldErrors({});
    try {
      const saved = isEdit
        ? await updateAnnouncement(announcement!.id, {
            title,
            body,
            published,
            // Only send the slug when it actually changed; the link should stay put.
            ...(slug && slug !== announcement!.slug ? { slug } : {}),
          })
        : await createAnnouncement({ title, body, published, ...(slug ? { slug } : {}) });
      onSaved(saved);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || "Could not save the announcement.");
      setFieldErrors(apiError.fields ?? {});
    } finally {
      setBusy(false);
    }
  };

  const fieldError = (name: string) => fieldErrors[name]?.[0];

  return (
    <Modal
      title={isEdit ? "Edit announcement" : "New announcement"}
      onClose={onClose}
      size="lg"
      busy={busy}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" form="announcement-form" className="btn" disabled={busy}>
            {busy ? "Saving..." : isEdit ? "Save changes" : "Create announcement"}
          </button>
        </>
      }
    >
      <form id="announcement-form" onSubmit={submit} noValidate>
        {error && <p className="alert alert--error">{error}</p>}

        <label className="field">
          <span className="field__label">Title</span>
          <input
            className="input"
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={200}
            required
          />
          {fieldError("title") && <span className="field__error">{fieldError("title")}</span>}
        </label>

        <label className="field">
          <span className="field__label">Link slug</span>
          <input
            className="input"
            type="text"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            placeholder={isEdit ? "" : "Left blank: generated from the title"}
            maxLength={80}
          />
          <span className="field__hint">
            The shareable link is <code>/a/{slug || "your-title-here"}</code>. Changing it
            breaks links you already sent.
          </span>
          {fieldError("slug") && <span className="field__error">{fieldError("slug")}</span>}
        </label>

        <label className="field">
          <span className="field__label">Body (Markdown)</span>
          <textarea
            className="textarea"
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder={"**Bold**, *italic*, - bullet lists, [links](https://example.com)"}
          />
          <span className="field__hint">
            Markdown is rendered and sanitised on the server, so it is safe to paste from chat.
          </span>
          {fieldError("body") && <span className="field__error">{fieldError("body")}</span>}
        </label>

        <label className="checkbox">
          <input
            type="checkbox"
            checked={published}
            onChange={(event) => setPublished(event.target.checked)}
          />
          <span>Published (visible to classmates)</span>
        </label>

        {isEdit && (
          <p className="field__hint" style={{ marginTop: "14px" }}>
            Photos and files are managed from the Attachments dialog on the dashboard.
          </p>
        )}
      </form>
    </Modal>
  );
}
