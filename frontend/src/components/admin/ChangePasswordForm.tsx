import { useMemo, useState } from "react";
import { ApiError, changePassword } from "../../lib/adminClient";
import type { AdminUser } from "../../lib/types";
import { CheckIcon, DotIcon, EyeIcon, EyeOffIcon } from "./icons";

interface Props {
  user: AdminUser;
  /** True when this is the forced change right after an invite. */
  forced: boolean;
  onChanged: (user: AdminUser) => void;
  onCancel?: () => void;
}

/**
 * The rules, mirrored from the server so they can be shown as you type.
 *
 * The server is still the authority - announcements/passwords.py and Django's
 * own validators decide - but a checklist that fills in beats submitting three
 * times to discover the rules one error at a time.
 */
const RULES: { label: string; test: (value: string, user: AdminUser) => boolean }[] = [
  { label: "At least 10 characters", test: (value) => value.length >= 10 },
  { label: "An uppercase letter", test: (value) => /[A-Z]/.test(value) },
  { label: "A lowercase letter", test: (value) => /[a-z]/.test(value) },
  { label: "A number", test: (value) => /[0-9]/.test(value) },
  {
    label: "A symbol, for example ! ? # @",
    test: (value) => /[^A-Za-z0-9]/.test(value),
  },
  {
    label: "Not your name or email",
    test: (value, user) => {
      if (value.length < 4) return false;
      const lowered = value.toLowerCase();
      const parts = [user.email.split("@")[0], user.username, user.full_name]
        .filter(Boolean)
        .map((part) => part.toLowerCase())
        .filter((part) => part.length >= 4);
      return !parts.some((part) => lowered.includes(part));
    },
  },
];

export default function ChangePasswordForm({ user, forced, onChanged, onCancel }: Props) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const results = useMemo(
    () => RULES.map((rule) => ({ label: rule.label, ok: rule.test(next, user) })),
    [next, user]
  );
  const allRulesMet = results.every((rule) => rule.ok);
  const matches = next.length > 0 && next === confirm;
  const canSubmit = Boolean(current) && allRulesMet && matches && !busy;

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

  return (
    <div className="auth-card">
      {forced && (
        <div className="alert alert--info">
          <strong>Set your own password to continue.</strong>
          <br />
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

        <ul className="rule-list" aria-label="Password requirements">
          {results.map((rule) => (
            <li
              key={rule.label}
              className={rule.ok ? "rule-list__item rule-list__item--ok" : "rule-list__item"}
            >
              <span className="rule-list__icon">{rule.ok ? <CheckIcon /> : <DotIcon />}</span>
              {rule.label}
            </li>
          ))}
        </ul>

        <label className="field">
          <span className="field__label">Confirm new password</span>
          <input
            className="input"
            type={show ? "text" : "password"}
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            autoComplete="new-password"
            required
          />
          {confirm.length > 0 && !matches && (
            <span className="field__error">Both passwords must match.</span>
          )}
        </label>

        <div className="auth-card__actions">
          {onCancel && !forced ? (
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
      </form>
    </div>
  );
}
