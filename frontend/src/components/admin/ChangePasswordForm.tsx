import { useMemo, useState } from "react";
import { ApiError, changePassword } from "../../lib/adminClient";
import type { AdminUser } from "../../lib/types";
import { LOGO_PATH, SITE_NAME } from "../../lib/config";
import PasswordRules, { allRulesMet } from "./PasswordRules";
import { EyeIcon, EyeOffIcon } from "./icons";

interface Props {
  user: AdminUser;
  /** True when this is the forced change right after an invite. */
  forced: boolean;
  onChanged: (user: AdminUser) => void;
  onCancel?: () => void;
}

export default function ChangePasswordForm({ user, forced, onChanged, onCancel }: Props) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const who = useMemo(
    () => ({ email: user.email, username: user.username, full_name: user.full_name }),
    [user]
  );
  const matches = next.length > 0 && next === confirm;
  const canSubmit = Boolean(current) && allRulesMet(next, who) && matches && !busy;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setProblems([]);
    try {
      onChanged(await changePassword(current, next));
    } catch (err) {
      const apiError = err as ApiError;
      // The server may reject for reasons the checklist cannot know - a common
      // password in disguise, most of all. Show exactly what it said.
      const listed = [
        ...(apiError.fields?.new_password ?? []),
        ...(apiError.fields?.current_password ?? []),
      ];
      if (listed.length) setProblems(listed);
      else setError(apiError.message || "Could not change your password.");
      setBusy(false);
    }
  };

  const body = (
    <div className="auth-card">
      {forced && (
        <div className="alert alert--info">
          The password from your invite email is temporary and works only once.
        </div>
      )}

      <form onSubmit={submit} noValidate>
        {error && <p className="alert alert--error">{error}</p>}
        {problems.length > 0 && (
          <div className="alert alert--error">
            <ul className="plain-list">
              {problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          </div>
        )}

        <label className="field">
          <span className="field__label">
            {forced ? "Temporary password from your email" : "Current password"}
          </span>
          <input
            className="input"
            type="password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            autoComplete="current-password"
            autoFocus
            required
          />
        </label>

        <label className="field">
          <span className="field__label">New password</span>
          <span className="field__with-button">
            <input
              className="input"
              type={show ? "text" : "password"}
              value={next}
              onChange={(event) => setNext(event.target.value)}
              autoComplete="new-password"
              required
            />
            <button
              type="button"
              className="field__reveal"
              onClick={() => setShow((shown) => !shown)}
              aria-label={show ? "Hide password" : "Show password"}
              aria-pressed={show}
            >
              {show ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </span>
        </label>

        <PasswordRules password={next} who={who} />

        <label className="field">
          <span className="field__label">Confirm new password</span>
          <input
            className="input"
            type="password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            autoComplete="new-password"
            required
          />
          {confirm.length > 0 && !matches && (
            <span className="field__error">Both passwords must match.</span>
          )}
        </label>

        {forced ? (
          <button type="submit" className="btn auth__submit" disabled={!canSubmit}>
            {busy ? "Saving..." : "Save password and continue"}
          </button>
        ) : (
          <div className="auth-card__actions">
            {onCancel ? (
              <button type="button" className="btn btn--ghost" onClick={onCancel}>
                Cancel
              </button>
            ) : (
              <span />
            )}
            <button type="submit" className="btn" disabled={!canSubmit}>
              {busy ? "Saving..." : "Save password"}
            </button>
          </div>
        )}
      </form>
    </div>
  );

  if (!forced) return body;

  return (
    <div className="auth">
      <div className="auth__panel">
        <div className="auth__brand">
          <img className="auth__logo" src={LOGO_PATH} alt="" width="46" height="46" />
          <p className="auth__site">{SITE_NAME}</p>
        </div>

        <h1 className="auth__title">Set your password</h1>
        <p className="auth__subtitle">
          One step left, {user.full_name?.split(" ")[0] || "then you are in"}.
        </p>

        {body}
      </div>
    </div>
  );
}
