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
  const [showPassword, setShowPassword] = useState(false);
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
          <span className="field__with-button">
            <input
              className="input"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
            <button
              type="button"
              className="field__reveal"
              onClick={() => setShowPassword((shown) => !shown)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              title={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </span>
        </label>

        <p className="field__hint">
          Only the class admin can sign in. Classmates read announcements without an account.
        </p>
      </form>
    </Modal>
  );
}


/* Inline SVGs rather than an icon dependency - two shapes do not justify one. */
function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}
