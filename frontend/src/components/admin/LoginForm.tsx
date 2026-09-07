import { useState } from "react";
import { ApiError, signIn } from "../../lib/adminClient";
import { EyeIcon, EyeOffIcon } from "./icons";

/**
 * The sign-in form for /login.
 *
 * A page rather than a modal: it is its own destination now that publishers
 * arrive here from a link in an invite email, and a modal over a dimmed
 * dashboard is a strange thing to land on from your inbox.
 */
export default function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await signIn(email.trim(), password);
      // The dashboard reads the session from sessionStorage on mount, and
      // decides for itself whether a forced password change comes first.
      window.location.href = "/admin";
    } catch (err) {
      const apiError = err as ApiError;
      if (apiError.status === 429) {
        setError("Too many attempts. Wait a minute and try again.");
      } else {
        setError(apiError.message || "Could not sign in.");
      }
      setBusy(false);
    }
  };

  return (
    <div className="auth-card">
      <form onSubmit={submit} noValidate>
        {error && <p className="alert alert--error">{error}</p>}

        <label className="field">
          <span className="field__label">Email</span>
          <input
            className="input"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            autoFocus
            required
            placeholder="you@gmail.com"
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
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </span>
        </label>

        <div className="auth-card__actions">
          <a className="btn btn--ghost" href="/">
            Back to announcements
          </a>
          <button type="submit" className="btn" disabled={busy}>
            {busy ? "Signing in..." : "Log in"}
          </button>
        </div>
      </form>

      <p className="field__hint auth-card__note">
        Only admins and publishers sign in. Classmates read every announcement
        without an account. If you were invited, use the temporary password from
        your email - you will be asked to set your own straight after.
        <br />
        <br />
        Forgot your password, or your invite expired? Ask an admin to send you a
        new one from the Publishers list.
      </p>
    </div>
  );
}
