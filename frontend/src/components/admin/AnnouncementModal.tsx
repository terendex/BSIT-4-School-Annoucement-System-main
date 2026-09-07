import { useEffect, useState } from "react";
import Modal from "./Modal";
import {
  ApiError,
  createAnnouncement,
  fetchSourcePages,
  updateAnnouncement,
  uploadAttachment,
} from "../../lib/adminClient";
import type { SourcePage } from "../../lib/adminClient";
import type { Announcement } from "../../lib/types";

/** The post saved but an attachment did not - a different story to a failed save. */
class PartialSaveError extends Error {
  announcement: Announcement;

  constructor(message: string, announcement: Announcement) {
    super(message);
    this.name = "PartialSaveError";
    this.announcement = announcement;
  }
}

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
  const [sourcePage, setSourcePage] = useState(announcement?.source_page ?? "");
  const [sourceUrl, setSourceUrl] = useState(announcement?.source_url ?? "");
  const [pages, setPages] = useState<SourcePage[]>([]);
  // Create mode only: the poster/photos to attach in the same step.
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchSourcePages().then(setPages).catch(() => setPages([]));
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setFieldErrors({});
    try {
      let saved = isEdit
        ? await updateAnnouncement(announcement!.id, {
            title,
            body,
            published,
            source_page: sourcePage,
            source_url: sourceUrl,
            // Only send the slug when it actually changed; the link should stay put.
            ...(slug && slug !== announcement!.slug ? { slug } : {}),
          })
        : await createAnnouncement({
            title,
            body,
            published,
            source_page: sourcePage,
            source_url: sourceUrl,
            ...(slug ? { slug } : {}),
          });

      // Upload anything picked here, so one dialog covers the whole post.
      for (const [index, file] of files.entries()) {
        setProgress(`Uploading ${index + 1} of ${files.length}...`);
        const kind = file.type.startsWith("image/") ? "image" : "file";
        let attachment;
        try {
          attachment = await uploadAttachment(saved.id, file, kind);
        } catch (uploadError) {
          // The announcement itself already saved. Say so plainly, rather than
          // showing a bare error next to a post that did in fact publish.
          const reason = (uploadError as ApiError).message || "upload failed";
          throw new PartialSaveError(
            `"${saved.title}" was saved, but ${file.name} could not be uploaded: ` +
              `${reason} Add it again from the Files dialog.`,
            saved
          );
        }
        saved = {
          ...saved,
          images: kind === "image" ? [...saved.images, attachment] : saved.images,
          files: kind === "file" ? [...saved.files, attachment] : saved.files,
          image_count: saved.image_count + (kind === "image" ? 1 : 0),
          file_count: saved.file_count + (kind === "file" ? 1 : 0),
          cover_image: saved.cover_image ?? (kind === "image" ? attachment : null),
        };
      }

      onSaved(saved);
    } catch (err) {
      if (err instanceof PartialSaveError) {
        // Keep the dialog open with the explanation, but hand the saved
        // announcement to the dashboard so the list is not left stale.
        setError(err.message);
        onSaved(err.announcement);
        return;
      }
      const apiError = err as ApiError;
      setError(apiError.message || "Could not save the announcement.");
      setFieldErrors(apiError.fields ?? {});
    } finally {
      setProgress("");
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
            {busy
              ? progress || "Saving..."
              : isEdit
                ? "Save changes"
                : "Create announcement"}
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

        <div className="field">
          <span className="field__label">Re-posted from (optional)</span>
          <select
            className="select"
            value={sourcePage}
            onChange={(event) => setSourcePage(event.target.value)}
          >
            <option value="">Not from a Facebook page</option>
            {pages.map((page) => (
              <option key={page.slug} value={page.slug}>
                {page.name}
              </option>
            ))}
          </select>
          {fieldError("source_page") && (
            <span className="field__error">{fieldError("source_page")}</span>
          )}
        </div>

        <label className="field">
          <span className="field__label">Link to the original post (optional)</span>
          <input
            className="input"
            type="url"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            placeholder="https://www.facebook.com/sits.slclu/posts/..."
            maxLength={500}
          />
          <span className="field__hint">
            Shown as a "Re-posted from" credit under the title.
          </span>
          {fieldError("source_url") && (
            <span className="field__error">{fieldError("source_url")}</span>
          )}
        </label>

        <label className="checkbox">
          <input
            type="checkbox"
            checked={published}
            onChange={(event) => setPublished(event.target.checked)}
          />
          <span>Published (visible to classmates)</span>
        </label>

        {isEdit ? (
          <p className="field__hint" style={{ marginTop: "14px" }}>
            Photos and files are managed from the Attachments dialog on the dashboard.
          </p>
        ) : (
          <label className="field" style={{ marginTop: "18px" }}>
            <span className="field__label">Poster and attachments (optional)</span>
            <input
              className="input"
              type="file"
              multiple
              accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip"
              onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
              disabled={busy}
            />
            <span className="field__hint">
              Uploaded as soon as the announcement is created. The first photo becomes
              the Messenger preview image.
              {files.length > 0 && ` ${files.length} selected.`}
            </span>
          </label>
        )}
      </form>
    </Modal>
  );
}
