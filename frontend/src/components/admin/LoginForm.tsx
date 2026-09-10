import { useState } from "react";
import { ApiError, signIn } from "../../lib/adminClient";
import { LOGO_PATH, SITE_NAME } from "../../lib/config";
import { EyeIcon, EyeOffIcon, WarningIcon } from "./icons";

/**
 * The sign-in screen for /login.
 *
 * A page rather than a modal: it is its own destination now that publishers
 * arrive here from a link in an invite email, and a dialog floating over a
 * dimmed dashboard is a strange thing to land on from your inbox.
 *
 * The logo and the school name sit at the top on purpose - someone following a
 * link from an email should be able to tell at a glance that they are typing
 * their password into the right site.
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
      // The dashboard reads the session back on mount and decides for itself
      // whether a forced password change comes first.
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
    <div className="auth">
      <div className="auth__panel">
        <div className="auth__brand">
          <img className="auth__logo" src={LOGO_PATH} alt="" width="46" height="46" />
          <p className="auth__site">{SITE_NAME}</p>
        </div>

        <h1 className="auth__title">Log in</h1>
        <p className="auth__subtitle">To post and manage announcements.</p>

        <form onSubmit={submit} noValidate>
          {error && (
            <p className="alert alert--error auth__alert" role="alert">
              <WarningIcon />
              <span>{error}</span>
            </p>
          )}

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
              disabled={busy}
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
                disabled={busy}
              />
              <button
                type="button"
                className="field__reveal"
                onClick={() => setShowPassword((shown) => !shown)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                tabIndex={-1}
              >
                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </span>
          </label>

          <button type="submit" className="btn auth__submit" disabled={busy}>
            {busy ? "Signing in..." : "Log in"}
          </button>
        </form>

        <div className="auth__foot">
          <p>
            Invited by email? Use the temporary password from that message - you
            will be asked to set your own straight after.
          </p>
          <p>Forgot your password, or your invite expired? Ask an admin to send a new one.</p>
        </div>
      </div>

      <p className="auth__aside">
        Only admins and publishers sign in.{" "}
        <a href="/">Read the announcements</a> without an account.
      </p>
    </div>
  );
}
