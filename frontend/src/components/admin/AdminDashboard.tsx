import { useCallback, useEffect, useState } from "react";
import Modal from "./Modal";
import AnnouncementModal from "./AnnouncementModal";
import AttachmentsModal from "./AttachmentsModal";
import ChangePasswordForm from "./ChangePasswordForm";
import ConfirmModal from "./ConfirmModal";
import PublishersModal from "./PublishersModal";
import {
  ApiError,
  deleteAnnouncement,
  fetchMe,
  fetchTaxonomy,
  hasSession,
  listAll,
  signOut,
  updateAnnouncement,
} from "../../lib/adminClient";
import { SITE_URL } from "../../lib/config";
import { formatDateTime } from "../../lib/format";
import type { AdminUser, Announcement, Taxonomy } from "../../lib/types";

type Dialog =
  | { type: "none" }
  | { type: "create" }
  | { type: "edit"; announcement: Announcement }
  | { type: "attachments"; announcement: Announcement }
  | { type: "delete"; announcement: Announcement }
  | { type: "share"; announcement: Announcement }
  | { type: "publishers" }
  | { type: "password" };

const EMPTY_TAXONOMY: Taxonomy = { categories: [], year_levels: [] };

/**
 * Every action happens in a modal - nothing here triggers a full page reload,
 * the list is patched in place after each request.
 *
 * What a signed-in person may do depends on their role. The buttons below
 * follow it, and the API enforces it: a publisher creates announcements and
 * edits their own, an admin edits and deletes anything and manages accounts.
 */
export default function AdminDashboard() {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [taxonomy, setTaxonomy] = useState<Taxonomy>(EMPTY_TAXONOMY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [year, setYear] = useState("");
  const [dialog, setDialog] = useState<Dialog>({ type: "none" });

  const isAdmin = user?.role === "admin";
  const close = () => setDialog({ type: "none" });

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(""), 4000);
  };

  const canEdit = (announcement: Announcement) =>
    isAdmin || announcement.author === user?.id;

  const load = useCallback(
    async (filters: { search?: string; category?: string; year?: string } = {}) => {
      setLoading(true);
      setError("");
      try {
        const data = await listAll(1, filters);
        setAnnouncements(data.results);
      } catch (err) {
        const apiError = err as ApiError;
        if (apiError.status === 401) {
          signOut();
          window.location.href = "/login";
        } else {
          setError(apiError.message || "Could not load announcements.");
        }
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Restore an existing session (refresh token in sessionStorage) on mount.
  // With no session at all, this page is not the place to be.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!hasSession()) {
        window.location.href = "/login";
        return;
      }
      try {
        const me = await fetchMe();
        if (!cancelled) setUser(me);
      } catch {
        signOut();
        window.location.href = "/login";
        return;
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    fetchTaxonomy().then(setTaxonomy).catch(() => setTaxonomy(EMPTY_TAXONOMY));
  }, []);

  // Nothing is fetched while a temporary password is still in force - the API
  // would refuse it anyway, and an error banner under the password form would
  // just be noise.
  useEffect(() => {
    if (user && !user.must_change_password) void load();
  }, [user, load]);

  const applyFilters = (next: { category?: string; year?: string }) => {
    const merged = { search, category, year, ...next };
    setCategory(merged.category);
    setYear(merged.year);
    void load(merged);
  };

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

  const leave = () => {
    signOut();
    window.location.href = "/login";
  };

  if (checking || !user) {
    return <p className="field__hint">Checking your session...</p>;
  }

  // The one thing an invited publisher can do before anything else.
  if (user.must_change_password) {
    return (
      <ChangePasswordForm
        user={user}
        forced
        onChanged={(updated) => {
          setUser(updated);
          flash("Password saved. Welcome aboard.");
        }}
      />
    );
  }

  return (
    <>
      <div className="admin-bar">
        <div>
          <p className="admin-bar__who">
            Signed in as <strong>{user.full_name || user.email || user.username}</strong>{" "}
            <span className={`tag ${isAdmin ? "tag--info" : "tag--success"}`}>
              {isAdmin ? "Admin" : "Publisher"}
            </span>
          </p>
          {user.last_login && (
            <p className="field__hint">Last sign in: {formatDateTime(user.last_login)}</p>
          )}
        </div>
        <div className="admin-bar__actions">
          <button type="button" className="btn" onClick={() => setDialog({ type: "create" })}>
            New announcement
          </button>
          {isAdmin && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setDialog({ type: "publishers" })}
            >
              Publishers
            </button>
          )}
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => setDialog({ type: "password" })}
          >
            Change password
          </button>
          <button type="button" className="btn btn--ghost" onClick={leave}>
            Sign out
          </button>
        </div>
      </div>

      {!isAdmin && (
        <p className="field__hint" style={{ marginBottom: "14px" }}>
          You can post announcements and edit your own. Ask an admin to edit
          someone else's or to delete anything.
        </p>
      )}

      {error && <p className="alert alert--error">{error}</p>}
      {notice && <p className="alert alert--success">{notice}</p>}

      <form
        className="searchbar"
        onSubmit={(event) => {
          event.preventDefault();
          void load({ search, category, year });
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
        <select
          className="select"
          value={category}
          onChange={(event) => applyFilters({ category: event.target.value })}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {taxonomy.categories.map((item) => (
            <option key={item.slug} value={item.slug}>
              {item.name}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={year}
          onChange={(event) => applyFilters({ year: event.target.value })}
          aria-label="Filter by year level"
        >
          <option value="">All year levels</option>
          {taxonomy.year_levels
            .filter((item) => item.slug !== "all")
            .map((item) => (
              <option key={item.slug} value={item.slug}>
                {item.name}
              </option>
            ))}
        </select>
        <button type="submit" className="btn btn--ghost">
          Search
        </button>
        {(search || category || year) && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setSearch("");
              setCategory("");
              setYear("");
              void load();
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
          <p>No announcements match. Create one, or clear the filters.</p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Filed under</th>
                <th>Status</th>
                <th>Posted by</th>
                <th>Updated</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {announcements.map((announcement) => {
                const mine = announcement.author === user.id;
                const editable = canEdit(announcement);
                return (
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
                      <span className="field__hint">
                        {announcement.image_count} photo
                        {announcement.image_count === 1 ? "" : "s"},{" "}
                        {announcement.file_count} file
                        {announcement.file_count === 1 ? "" : "s"}
                      </span>
                    </td>
                    <td data-label="Filed under">
                      <span className={`tag tag--${toneFor(taxonomy, announcement.category)}`}>
                        {announcement.category_name}
                      </span>
                      {announcement.year_level !== "all" && (
                        <span className="tag">{announcement.year_level_name}</span>
                      )}
                    </td>
                    <td data-label="Status">
                      {editable ? (
                        <button
                          type="button"
                          className={`tag ${announcement.published ? "" : "tag--draft"}`}
                          onClick={() => togglePublished(announcement)}
                          title="Click to toggle"
                        >
                          {announcement.published ? "Published" : "Draft"}
                        </button>
                      ) : (
                        <span className={`tag ${announcement.published ? "" : "tag--draft"}`}>
                          {announcement.published ? "Published" : "Draft"}
                        </span>
                      )}
                    </td>
                    <td className="admin-table__nowrap" data-label="Posted by">
                      {mine ? "You" : announcement.author_name || "-"}
                    </td>
                    <td className="admin-table__nowrap" data-label="Updated">
                      {formatDateTime(announcement.updated_at)}
                    </td>
                    <td>
                      <div className="admin-table__actions">
                        {editable && (
                          <>
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
                          </>
                        )}
                        <button
                          type="button"
                          className="btn btn--sm btn--ghost"
                          onClick={() => setDialog({ type: "share", announcement })}
                        >
                          Share
                        </button>
                        {isAdmin && (
                          <button
                            type="button"
                            className="btn btn--sm btn--danger"
                            onClick={() => setDialog({ type: "delete", announcement })}
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {(dialog.type === "create" || dialog.type === "edit") && (
        <AnnouncementModal
          announcement={dialog.type === "edit" ? dialog.announcement : null}
          taxonomy={taxonomy}
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

      {dialog.type === "publishers" && (
        <PublishersModal currentUserId={user.id} onClose={close} />
      )}

      {dialog.type === "password" && (
        <Modal title="Change your password" onClose={close} size="md" footer={null}>
          <ChangePasswordForm
            user={user}
            forced={false}
            onCancel={close}
            onChanged={(updated) => {
              setUser(updated);
              close();
              flash("Password changed.");
            }}
          />
        </Modal>
      )}
    </>
  );
}

/** The colour a category carries, straight from the API's own list. */
function toneFor(taxonomy: Taxonomy, slug: string): string {
  return taxonomy.categories.find((item) => item.slug === slug)?.tone ?? "neutral";
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
