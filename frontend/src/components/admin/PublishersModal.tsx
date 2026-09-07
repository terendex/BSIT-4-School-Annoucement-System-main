import { useEffect, useState } from "react";
import Modal from "./Modal";
import ConfirmModal from "./ConfirmModal";
import {
  ApiError,
  deletePublisher,
  invitePublisher,
  listPublishers,
  resendInvite,
  updatePublisher,
} from "../../lib/adminClient";
import { formatDateTime } from "../../lib/format";
import type { Publisher } from "../../lib/types";

interface Props {
  /** The signed-in admin, so their own row is never offered a delete button. */
  currentUserId: number;
  onClose: () => void;
}

/**
 * Admin-only: add publishers by email, and manage the ones already added.
 *
 * Inviting creates the account and mails a temporary password; nothing here
 * ever shows or stores that password - it exists only in their inbox.
 */
export default function PublishersModal({ currentUserId, onClose }: Props) {
  const [publishers, setPublishers] = useState<Publisher[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState<Publisher | null>(null);
  const [resetting, setResetting] = useState<Publisher | null>(null);
  /** Shown only when the email failed - the way back from a dead account. */
  const [fallback, setFallback] = useState<{ email: string; password: string } | null>(
    null
  );

  const load = async () => {
    setLoading(true);
    try {
      setPublishers(await listPublishers());
      setError("");
    } catch (err) {
      setError((err as ApiError).message || "Could not load the publisher list.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const invite = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await invitePublisher(email.trim(), fullName.trim());
      setEmail("");
      setFullName("");
      await load();
      // The API reports delivery separately: the account exists either way, so
      // saying "invited" when the mail bounced would be a lie.
      if (created.invite_email_sent === false) {
        setError(
          created.detail ??
            "The account was created but the invite email could not be sent."
        );
        if (created.temporary_password) {
          setFallback({ email: created.email, password: created.temporary_password });
        }
      } else {
        setNotice(`Invite sent to ${created.email}.`);
      }
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.fields?.email?.[0] ?? apiError.message ?? "Could not invite.");
    } finally {
      setBusy(false);
    }
  };

  const act = async (action: () => Promise<Publisher | unknown>, message: string) => {
    setBusy(true);
    setError("");
    setNotice("");
    setFallback(null);
    try {
      const result = (await action()) as Publisher | undefined;
      await load();
      if (result && result.invite_email_sent === false) {
        setError(result.detail ?? "The email could not be sent.");
        if (result.temporary_password) {
          setFallback({ email: result.email, password: result.temporary_password });
        }
      } else {
        setNotice(message);
      }
    } catch (err) {
      setError((err as ApiError).message || "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  const remove = (publisher: Publisher) =>
    act(
      () => deletePublisher(publisher.id),
      `${publisher.email} removed. Their announcements are still on the board.`
    );

  return (
    <>
      <Modal
        title="Publishers"
        onClose={onClose}
        size="lg"
        busy={busy}
        footer={
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Close
          </button>
        }
      >
        <form className="upload-panel" onSubmit={invite}>
          <p className="field__label" style={{ marginTop: 0 }}>
            Add a publisher
          </p>
          <div className="upload-panel__row">
            <label className="field" style={{ flex: "2 1 240px", marginBottom: 0 }}>
              <span className="field__label">Email</span>
              <input
                className="input"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="publisher@gmail.com"
                required
              />
            </label>
            <label className="field" style={{ flex: "2 1 200px", marginBottom: 0 }}>
              <span className="field__label">Name (optional)</span>
              <input
                className="input"
                type="text"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Juan Dela Cruz"
              />
            </label>
          </div>
          <button type="submit" className="btn" disabled={busy || !email.trim()}>
            {busy ? "Sending..." : "Send invite"}
          </button>
          <p className="field__hint">
            They receive a temporary password by email and must set their own on
            first sign in. Publishers can post announcements and edit their own.
          </p>
        </form>

        {error && <p className="alert alert--error">{error}</p>}
        {notice && <p className="alert alert--success">{notice}</p>}

        {fallback && (
          <div className="alert alert--info">
            <p style={{ margin: "0 0 8px" }}>
              <strong>Give this to {fallback.email} yourself.</strong> It works
              once, and they will be asked to set their own password straight
              after. It is not shown again.
            </p>
            <input
              className="input"
              type="text"
              value={fallback.password}
              readOnly
              onFocus={(event) => event.target.select()}
              aria-label="Temporary password"
            />
          </div>
        )}

        {loading ? (
          <p className="field__hint">Loading...</p>
        ) : (
          <div className="table-scroll" style={{ marginTop: "16px" }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Status</th>
                  <th>Posts</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {publishers.map((publisher) => {
                  const isSelf = publisher.id === currentUserId;
                  const isAdmin = publisher.role === "admin";
                  return (
                    <tr key={publisher.id}>
                      <td>
                        <span className="admin-table__title">
                          {publisher.full_name || publisher.email}
                        </span>
                        <span className="field__hint">{publisher.email}</span>
                      </td>
                      <td data-label="Status">
                        <StatusTag publisher={publisher} />
                        {publisher.last_login && (
                          <span className="field__hint">
                            Last in: {formatDateTime(publisher.last_login)}
                          </span>
                        )}
                      </td>
                      <td className="admin-table__nowrap" data-label="Posts">
                        {publisher.announcement_count}
                      </td>
                      <td>
                        <div className="admin-table__actions">
                          {isAdmin || isSelf ? (
                            <span className="field__hint">
                              {isSelf ? "This is you" : "Admin account"}
                            </span>
                          ) : (
                            <>
                              {/* Always available. Before first sign-in it is a
                                  lost invite; afterwards it is the only way back
                                  in for someone who forgot their password. */}
                              <button
                                type="button"
                                className="btn btn--sm btn--ghost"
                                disabled={busy}
                                onClick={() =>
                                  publisher.must_change_password
                                    ? act(
                                        () => resendInvite(publisher.id),
                                        `New invite sent to ${publisher.email}.`
                                      )
                                    : setResetting(publisher)
                                }
                              >
                                {publisher.must_change_password
                                  ? "Resend invite"
                                  : "Reset password"}
                              </button>
                              <button
                                type="button"
                                className="btn btn--sm btn--ghost"
                                disabled={busy}
                                onClick={() =>
                                  act(
                                    () =>
                                      updatePublisher(publisher.id, {
                                        is_active: !publisher.is_active,
                                      }),
                                    publisher.is_active
                                      ? `${publisher.email} can no longer sign in.`
                                      : `${publisher.email} can sign in again.`
                                  )
                                }
                              >
                                {publisher.is_active ? "Disable" : "Enable"}
                              </button>
                              <button
                                type="button"
                                className="btn btn--sm btn--danger"
                                disabled={busy}
                                onClick={() => setConfirming(publisher)}
                              >
                                Remove
                              </button>
                            </>
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
      </Modal>

      {resetting && (
        <ConfirmModal
          title="Reset password"
          confirmLabel="Send new password"
          message={
            `Email ${resetting.email} a new temporary password? Their current ` +
            `password stops working immediately, and they will be asked to set ` +
            `a new one when they next sign in.`
          }
          onCancel={() => setResetting(null)}
          onConfirm={async () => {
            const target = resetting;
            setResetting(null);
            await act(
              () => resendInvite(target.id),
              `A new password was emailed to ${target.email}.`
            );
          }}
        />
      )}

      {confirming && (
        <ConfirmModal
          title="Remove publisher"
          message={
            `Remove ${confirming.email}? They will not be able to sign in again. ` +
            `Their ${confirming.announcement_count} announcement` +
            `${confirming.announcement_count === 1 ? "" : "s"} stay on the board.`
          }
          onCancel={() => setConfirming(null)}
          onConfirm={async () => {
            const target = confirming;
            setConfirming(null);
            await remove(target);
          }}
        />
      )}
    </>
  );
}

function StatusTag({ publisher }: { publisher: Publisher }) {
  if (!publisher.is_active) return <span className="tag tag--draft">Disabled</span>;
  if (publisher.role === "admin") return <span className="tag tag--info">Admin</span>;
  if (publisher.invite_expired) return <span className="tag tag--danger">Invite expired</span>;
  if (publisher.must_change_password) {
    return <span className="tag tag--warning">Invite sent</span>;
  }
  return <span className="tag tag--success">Active</span>;
}
