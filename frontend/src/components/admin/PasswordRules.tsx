import { CheckIcon, DotIcon } from "./icons";

/**
 * The password rules, mirrored from the server so they can fill in as you type.
 *
 * The server is still the authority - announcements/passwords.py and Django's
 * own validators decide - but a checklist beats submitting three times to
 * discover the rules one error message at a time.
 *
 * Shared by the invite screen and the change-password screen, so the two can
 * never drift apart.
 */
export interface RuleSubject {
  email: string;
  username?: string;
  full_name?: string;
}

const RULES: { label: string; test: (value: string, who: RuleSubject) => boolean }[] = [
  { label: "At least 10 characters", test: (value) => value.length >= 10 },
  { label: "An uppercase letter", test: (value) => /[A-Z]/.test(value) },
  { label: "A lowercase letter", test: (value) => /[a-z]/.test(value) },
  { label: "A number", test: (value) => /[0-9]/.test(value) },
  { label: "A symbol, for example ! ? # @", test: (value) => /[^A-Za-z0-9]/.test(value) },
  {
    label: "Not your name or email",
    test: (value, who) => {
      if (value.length < 4) return false;
      const lowered = value.toLowerCase();
      const parts = [who.email.split("@")[0], who.username, who.full_name]
        .filter(Boolean)
        .map((part) => String(part).toLowerCase())
        .filter((part) => part.length >= 4);
      return !parts.some((part) => lowered.includes(part));
    },
  },
];

export function checkRules(password: string, who: RuleSubject) {
  return RULES.map((rule) => ({ label: rule.label, ok: rule.test(password, who) }));
}

export function allRulesMet(password: string, who: RuleSubject) {
  return checkRules(password, who).every((rule) => rule.ok);
}

export default function PasswordRules({
  password,
  who,
}: {
  password: string;
  who: RuleSubject;
}) {
  return (
    <ul className="rule-list" aria-label="Password requirements">
      {checkRules(password, who).map((rule) => (
        <li
          key={rule.label}
          className={rule.ok ? "rule-list__item rule-list__item--ok" : "rule-list__item"}
        >
          <span className="rule-list__icon">{rule.ok ? <CheckIcon /> : <DotIcon />}</span>
          {rule.label}
        </li>
      ))}
    </ul>
  );
}
