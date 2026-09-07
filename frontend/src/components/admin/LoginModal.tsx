import { useState } from "react";
import Modal from "./Modal";
import { ApiError, signIn } from "../../lib/adminClient";
import type { AdminUser } from "../../lib/types";

interface Props {
  onSignedIn: (user: AdminUser) => void;
}

export default function LoginModal({ onSignedIn }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSignedIn(await signIn(username, password));
    } catch (err) {
      const apiError = err as ApiError;
      setError(
        apiError.status === 429
          ? "Too many attempts. Wait a minute and try again."
          : apiError.message || "Could not sign in."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title="Admin sign in"
      onClose={() => {
        window.location.href = "/";
      }}
      size="sm"
      busy={busy}
      footer={
        <>
          <a className="btn btn--ghost" href="/">
            Back to site
          </a>
          <button type="submit" form="login-form" className="btn" disabled={busy}>
            {busy ? "Signing in..." : "Sign in"}
          </button>
        </>
      }
    >
      <form id="login-form" onSubmit={submit} noValidate>
        {error && <p className="alert alert--error">{error}</p>}

        <label className="field">
          <span className="field__label">Username</span>
          <input
            className="input"
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />
        </label>

        <label className="field">
          <span className="field__label">Password</span>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        <p className="field__hint">
          Only the class admin can sign in. Classmates read announcements without an account.
        </p>
      </form>
    </Modal>
  );
}
