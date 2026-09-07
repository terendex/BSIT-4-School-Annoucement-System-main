import { useEffect, useState } from "react";
import { ApiError, acceptInvite, fetchInvite } from "../../lib/adminClient";
import { LOGO_PATH, SITE_NAME } from "../../lib/config";
import PasswordRules, { allRulesMet } from "./PasswordRules";
import { EyeIcon, EyeOffIcon, WarningIcon } from "./icons";

interface Props {
  token: string;
}

interface Invitee {
  email: string;
  full_name: string;
}

/**
 * The screen an invite link opens: choose your own password.
 *
 * This is the only moment the account gets a usable password, and it is set by
 * the person it belongs to. The admin who sent the link never sees it, and no
 * password ever travels through an inbox.
 */
export default function AcceptInvite({ token }: Props) {
  const [invitee, setInvitee] = useState<Invitee | null>(null);
  const [checking, setChecking] = useState(true);
  const [linkError, setLinkError] = useState("");

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  // Check the link before showing a form, so a spent or expired one says so
  // straight away instead of after they have chosen a password.
  useEffect(() => {
    let cancelled = false;
    fetchInvite(token)
      .then((data) => {
        if (!cancelled) setInvitee(data);
      })
      .catch((err) => {
        if (!cancelled) setLinkError((err as ApiError).message || "This link is not valid.");
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const who = { email: invitee?.email ?? "", full_name: invitee?.full_name };
  const rulesMet = allRulesMet(password, who);
  const matches = password.length > 0 && password === confirm;
  const canSubmit = rulesMet && matches && !busy;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setProblems([]);
    try {
      await acceptInvite(token, password);
      // Accepting signs them in, so go straight to the work.
      window.location.href = "/admin";
    } catch (err) {
      const apiError = err as ApiError;
      const listed = apiError.fields?.new_password ?? [];
      if (listed.length) setProblems(listed);
      else setError(apiError.message || "Could not set your password.");
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <div className="auth__panel">
        <div className="auth__brand">
          <img className="auth__seal" src={LOGO_PATH} alt="" width="46" height="46" />
          <p className="auth__site">{SITE_NAME}</p>
        </div>

        {checking ? (
          <p className="field__hint">Checking your invite...</p>
        ) : linkError ? (
          <>
            <h1 className="auth__title">This link no longer works</h1>
            <p className="alert alert--error auth__alert" role="alert">
              <WarningIcon />
              <span>{linkError}</span>
            </p>
            <div className="auth__foot">
              <p>
                Invite links can only be used once, and they expire. Ask an admin
                to send you a new one.
              </p>
            </div>
          </>
        ) : (
          <>
            <h1 className="auth__title">Choose your password</h1>
            <p className="auth__subtitle">
              Setting up <strong>{invitee?.email}</strong>. Only you will know
              this password.
            </p>

            <form onSubmit={submit} noValidate>
              {error && (
                <p className="alert alert--error auth__alert" role="alert">
                  <WarningIcon />
                  <span>{error}</span>
                </p>
              )}
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
                <span className="field__label">New password</span>
                <span className="field__with-button">
                  <input
                    className="input"
                    type={show ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="new-password"
                    autoFocus
                    required
                  />
                  <button
                    type="button"
                    className="field__reveal"
                    onClick={() => setShow((shown) => !shown)}
                    aria-label={show ? "Hide password" : "Show password"}
                    aria-pressed={show}
                    tabIndex={-1}
                  >
                    {show ? <EyeOffIcon /> : <EyeIcon />}
                  </button>
                </span>
              </label>

              <PasswordRules password={password} who={who} />

              <label className="field">
                <span className="field__label">Confirm password</span>
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

              <button type="submit" className="btn auth__submit" disabled={!canSubmit}>
                {busy ? "Saving..." : "Set password and continue"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
