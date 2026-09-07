import { useCallback, useEffect, useState } from "react";
import LoginModal from "./LoginModal";
import Modal from "./Modal";
import AnnouncementModal from "./AnnouncementModal";
import AttachmentsModal from "./AttachmentsModal";
import ConfirmModal from "./ConfirmModal";
import {
  ApiError,
  deleteAnnouncement,
  fetchMe,
  hasSession,
  listAll,
  signOut,
  updateAnnouncement,
} from "../../lib/adminClient";
import { SITE_URL } from "../../lib/config";
import { formatDateTime } from "../../lib/format";
import type { AdminUser, Announcement } from "../../lib/types";

type Dialog =
  | { type: "none" }
  | { type: "create" }
  | { type: "edit"; announcement: Announcement }
  | { type: "attachments"; announcement: Announcement }
  | { type: "delete"; announcement: Announcement }
  | { type: "share"; announcement: Announcement };

/**
 * Every admin action happens in a modal - nothing here triggers a full page
 * reload, the list is patched in place after each request.
 */
export default function AdminDashboard() {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<Dialog>({ type: "none" });

  const close = () => setDialog({ type: "none" });

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(""), 4000);
  };

  const load = useCallback(async (query = "") => {
    setLoading(true);
    setError("");
    try {
      const data = await listAll(1, query);
      setAnnouncements(data.results);
    } catch (err) {
      const apiError = err as ApiError;
      if (apiError.status === 401) {
        signOut();
        setUser(null);
      } else {
        setError(apiError.message || "Could not load announcements.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Restore an existing session (refresh token in sessionStorage) on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!hasSession()) {
        setChecking(false);
        return;
      }
      try {
        const me = await fetchMe();
        if (!cancelled) setUser(me);
      } catch {
        signOut();
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  const upsert = (saved: Announcement) => {
    setAnnouncements((current) => {
      const index = current.findIndex((item) => item.id === saved.id);
      if (index === -1) return [saved, ...current];
      const next = [...current];
      next[index] = saved;
      return next;
    });
  };

  const togglePublished = async (announcement: Announcement) => {
    try {
      const saved = await updateAnnouncement(announcement.id, {
        published: !announcement.published,
      });
      upsert(saved);
      flash(saved.published ? "Announcement published." : "Moved back to drafts.");
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  const removeAnnouncement = async (announcement: Announcement) => {
    await deleteAnnouncement(announcement.id);
    setAnnouncements((current) => current.filter((item) => item.id !== announcement.id));
    close();
    flash(`"${announcement.title}" deleted.`);
  };

  if (checking) {
    return <p className="field__hint">Checking your session...</p>;
  }

  if (!user) {
    return <LoginModal onSignedIn={setUser} />;
  }

  return (
    <>
      <div className="admin-bar">
        <div>
          <p className="admin-bar__who">
            Signed in as <strong>{user.username}</strong>
          </p>
          {user.last_login && (
            <p className="field__hint">Last sign in: {formatDateTime(user.last_login)}</p>
          )}
        </div>
        <div className="admin-bar__actions">
          <button type="button" className="btn" onClick={() => setDialog({ type: "create" })}>
            New announcement
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              signOut();
              setUser(null);
              setAnnouncements([]);
            }}
          >
            Sign out
          </button>
        </div>
      </div>

      {error && <p className="alert alert--error">{error}</p>}
      {notice && <p className="alert alert--success">{notice}</p>}

      <form
        className="searchbar"
        onSubmit={(event) => {
          event.preventDefault();
          void load(search);
        }}
        role="search"
      >
        <input
          className="input"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by title..."
          aria-label="Search announcements"
        />
        <button type="submit" className="btn btn--ghost">
          Search
        </button>
        {search && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setSearch("");
              void load("");
            }}
          >
            Clear
          </button>
        )}
      </form>

      {loading ? (
        <p className="field__hint">Loading...</p>
      ) : announcements.length === 0 ? (
        <div className="empty">
          <p>No announcements yet. Create your first one.</p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Attachments</th>
                <th>Updated</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {announcements.map((announcement) => (
                <tr key={announcement.id}>
                  <td>
                    <a
                      className="admin-table__title"
                      href={`/a/${announcement.slug}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {announcement.title}
                    </a>
                    <span className="field__hint">/a/{announcement.slug}</span>
                  </td>
                  <td data-label="Status">
                    <button
                      type="button"
                      className={`tag ${announcement.published ? "" : "tag--draft"}`}
                      onClick={() => togglePublished(announcement)}
                      title="Click to toggle"
                    >
                      {announcement.published ? "Published" : "Draft"}
                    </button>
                  </td>
                  <td className="admin-table__nowrap" data-label="Attachments">
                    {announcement.image_count} photo
                    {announcement.image_count === 1 ? "" : "s"}, {announcement.file_count} file
                    {announcement.file_count === 1 ? "" : "s"}
                  </td>
                  <td className="admin-table__nowrap" data-label="Updated">
                    {formatDateTime(announcement.updated_at)}
                  </td>
                  <td>
                    <div className="admin-table__actions">
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        onClick={() => setDialog({ type: "edit", announcement })}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        onClick={() => setDialog({ type: "attachments", announcement })}
                      >
                        Files
                      </button>
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        onClick={() => setDialog({ type: "share", announcement })}
                      >
                        Share
                      </button>
                      <button
                        type="button"
                        className="btn btn--sm btn--danger"
                        onClick={() => setDialog({ type: "delete", announcement })}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(dialog.type === "create" || dialog.type === "edit") && (
        <AnnouncementModal
          announcement={dialog.type === "edit" ? dialog.announcement : null}
          onClose={close}
          onSaved={(saved) => {
            upsert(saved);
            close();
            flash(dialog.type === "edit" ? "Changes saved." : "Announcement created.");
          }}
        />
      )}

      {dialog.type === "attachments" && (
        <AttachmentsModal
          announcement={dialog.announcement}
          onClose={close}
          onChanged={upsert}
        />
      )}

      {dialog.type === "delete" && (
        <ConfirmModal
          title="Delete announcement"
          message={`Delete "${dialog.announcement.title}"? Its photos and files are removed too, and any link you already shared will stop working.`}
          onCancel={close}
          onConfirm={() => removeAnnouncement(dialog.announcement)}
        />
      )}

      {dialog.type === "share" && (
        <ShareModal announcement={dialog.announcement} onClose={close} />
      )}
    </>
  );
}

function ShareModal({
  announcement,
  onClose,
}: {
  announcement: Announcement;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const url = `${SITE_URL}/a/${announcement.slug}`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Modal
      title="Share this announcement"
      onClose={onClose}
      size="sm"
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Close
          </button>
          <button type="button" className="btn" onClick={copy}>
            {copied ? "Copied" : "Copy link"}
          </button>
        </>
      }
    >
      <p style={{ marginTop: 0 }}>Paste this link into your Messenger group chat:</p>
      <input className="input" type="text" value={url} readOnly onFocus={(e) => e.target.select()} />
      {!announcement.published && (
        <p className="alert alert--error" style={{ marginTop: "14px" }}>
          This announcement is still a draft, so the link will show a 404 until you publish it.
        </p>
      )}
      {announcement.image_count === 0 && (
        <p className="field__hint" style={{ marginTop: "12px" }}>
          No photo attached, so Messenger will use the school seal as the preview image.
        </p>
      )}
    </Modal>
  );
}
