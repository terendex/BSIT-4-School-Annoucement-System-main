import { useRef, useState } from "react";
import Modal from "./Modal";
import {
  ApiError,
  deleteAttachment,
  uploadAttachment,
} from "../../lib/adminClient";
import { formatBytes } from "../../lib/format";
import type { Announcement, Attachment } from "../../lib/types";

interface Props {
  announcement: Announcement;
  onClose: () => void;
  onChanged: (updated: Announcement) => void;
}

const IMAGE_ACCEPT = ".jpg,.jpeg,.png,.gif,.webp";
const FILE_ACCEPT = ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip";

/** Upload and remove the photos and files attached to one announcement. */
export default function AttachmentsModal({ announcement, onClose, onChanged }: Props) {
  const [current, setCurrent] = useState(announcement);
  const [kind, setKind] = useState<"image" | "file">("image");
  const [caption, setCaption] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const apply = (next: Announcement) => {
    setCurrent(next);
    onChanged(next);
  };

  const addToState = (attachment: Attachment) => {
    const next: Announcement = {
      ...current,
      images:
        attachment.kind === "image" ? [...current.images, attachment] : current.images,
      files: attachment.kind === "file" ? [...current.files, attachment] : current.files,
      image_count: current.image_count + (attachment.kind === "image" ? 1 : 0),
      file_count: current.file_count + (attachment.kind === "file" ? 1 : 0),
      cover_image:
        current.cover_image ?? (attachment.kind === "image" ? attachment : null),
    };
    apply(next);
  };

  const removeFromState = (attachment: Attachment) => {
    const images = current.images.filter((item) => item.id !== attachment.id);
    apply({
      ...current,
      images,
      files: current.files.filter((item) => item.id !== attachment.id),
      image_count: images.length,
      file_count: current.files.filter((item) => item.id !== attachment.id).length,
      cover_image: images[0] ?? null,
    });
  };

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError("");
    setNotice("");

    let uploaded = 0;
    for (const file of Array.from(files)) {
      try {
        addToState(await uploadAttachment(current.id, file, kind, caption));
        uploaded += 1;
      } catch (err) {
        // Report the first failure but keep whatever already uploaded.
        setError(`${file.name}: ${(err as ApiError).message}`);
        break;
      }
    }

    if (uploaded > 0) {
      setNotice(`${uploaded} ${uploaded === 1 ? "attachment" : "attachments"} uploaded.`);
      setCaption("");
    }
    if (inputRef.current) inputRef.current.value = "";
    setBusy(false);
  };

  const confirmRemove = async (attachment: Attachment) => {
    setBusy(true);
    setError("");
    try {
      await deleteAttachment(attachment.id);
      removeFromState(attachment);
      setNotice("Attachment removed.");
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setPendingDelete(null);
      setBusy(false);
    }
  };

  const all: Attachment[] = [...current.images, ...current.files];

  return (
    <Modal
      title={`Attachments - ${current.title}`}
      onClose={onClose}
      size="lg"
      busy={busy}
      footer={
        <button type="button" className="btn" onClick={onClose} disabled={busy}>
          Done
        </button>
      }
    >
      {error && <p className="alert alert--error">{error}</p>}
      {notice && !error && <p className="alert alert--success">{notice}</p>}

      <div className="upload-panel">
        <div className="upload-panel__row">
          <label className="field" style={{ margin: 0 }}>
            <span className="field__label">Type</span>
            <select
              className="select"
              value={kind}
              onChange={(event) => setKind(event.target.value as "image" | "file")}
              disabled={busy}
            >
              <option value="image">Photo (shown in the gallery)</option>
              <option value="file">File (download link)</option>
            </select>
          </label>

          <label className="field" style={{ margin: 0, flex: 1 }}>
            <span className="field__label">Caption (optional)</span>
            <input
              className="input"
              type="text"
              value={caption}
              onChange={(event) => setCaption(event.target.value)}
              maxLength={255}
              disabled={busy}
            />
          </label>
        </div>

        <label className="field" style={{ marginBottom: 0 }}>
          <span className="field__label">Choose files</span>
          <input
            ref={inputRef}
            className="input"
            type="file"
            multiple
            accept={kind === "image" ? IMAGE_ACCEPT : FILE_ACCEPT}
            onChange={(event) => upload(event.target.files)}
            disabled={busy}
          />
          <span className="field__hint">
            {kind === "image"
              ? "JPG, PNG, GIF or WebP, up to 5 MB each. The first photo becomes the Messenger preview image."
              : "PDF, Office documents, TXT, CSV or ZIP, up to 10 MB each."}
          </span>
        </label>
      </div>

      <h3 className="section-title" style={{ marginTop: "24px" }}>
        Attached ({all.length})
      </h3>

      {all.length === 0 ? (
        <p className="field__hint">Nothing attached yet.</p>
      ) : (
        <ul className="attachment-list">
          {all.map((attachment) => (
            <li key={attachment.id} className="attachment">
              {attachment.kind === "image" ? (
                <img className="attachment__thumb" src={attachment.url} alt="" />
              ) : (
                <span className="attachment__thumb attachment__thumb--file">FILE</span>
              )}

              <div className="attachment__info">
                <a href={attachment.url} target="_blank" rel="noopener noreferrer">
                  {attachment.original_filename}
                </a>
                <span className="field__hint">
                  {attachment.caption ? `${attachment.caption} - ` : ""}
                  {formatBytes(attachment.size)}
                  {attachment.width ? ` - ${attachment.width}x${attachment.height}` : ""}
                </span>
              </div>

              {pendingDelete === attachment.id ? (
                <span className="attachment__confirm">
                  <button
                    type="button"
                    className="btn btn--sm btn--danger"
                    onClick={() => confirmRemove(attachment)}
                    disabled={busy}
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    className="btn btn--sm btn--ghost"
                    onClick={() => setPendingDelete(null)}
                    disabled={busy}
                  >
                    Keep
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  className="btn btn--sm btn--ghost"
                  onClick={() => setPendingDelete(attachment.id)}
                  disabled={busy}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
