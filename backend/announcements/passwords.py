"""Password rules and the one-time password handed out with an invite.

Django's own validators already cover length, common passwords, all-numeric
passwords, and similarity to the account's own email. This adds the character
mix on top, and generates the temporary password an invited publisher receives.

The temporary password is never stored in the clear and never returned by the
API - it exists only inside the invite email. The account carries it hashed,
like any other password, plus a must_change_password flag that the API enforces
until the publisher picks their own.
"""
import re
import secrets

from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Ambiguous glyphs are left out: a password read off a phone screen and typed on
# a laptop should not hinge on telling 0 from O or 1 from l.
_UNAMBIGUOUS_LOWER = "abcdefghijkmnopqrstuvwxyz"      # no l
_UNAMBIGUOUS_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"       # no I, no O
_UNAMBIGUOUS_DIGITS = "23456789"                       # no 0, no 1
_UNAMBIGUOUS_SYMBOLS = "!@#$%*?-+"

TEMP_PASSWORD_LENGTH = 14


class ComplexityValidator:
    """Require a mix of character classes, not just length.

    Length alone lets "aaaaaaaaaa" through. Requiring all four classes on a
    10-character minimum puts a publisher account well past what a credential
    stuffing list will contain.
    """

    CLASSES = (
        ("a lowercase letter", str.islower),
        ("an uppercase letter", str.isupper),
        ("a number", str.isdigit),
    )

    def validate(self, password, user=None):
        missing = [
            label
            for label, test in self.CLASSES
            if not any(test(character) for character in password)
        ]
        if not any(not character.isalnum() for character in password):
            missing.append("a symbol (for example ! ? # @)")

        if missing:
            raise ValidationError(
                _("Password must contain %(missing)s.")
                % {"missing": ", ".join(missing)},
                code="password_not_complex",
            )

        if password != password.strip():
            raise ValidationError(
                _("Password cannot start or end with a space."),
                code="password_whitespace",
            )

    def get_help_text(self):
        return _(
            "Use at least one uppercase letter, one lowercase letter, one number "
            "and one symbol."
        )


# Digits and symbols people swap in for letters when told to "add a number".
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
                       "@": "a", "$": "s", "!": "i"})


def _variations(password: str):
    """The password stripped of the decorations that hide a common word.

    "Password123!" is a dictionary word with a capital, a number and a symbol
    bolted on - it satisfies every mechanical rule while being one of the first
    guesses any attacker makes.
    """
    lowered = password.lower().strip()
    yield lowered

    alnum_only = re.sub(r"[^a-z0-9]", "", lowered)
    yield alnum_only
    yield re.sub(r"\d+$", "", alnum_only)          # trailing year or counter
    yield re.sub(r"^\d+", "", alnum_only)          # leading one

    decoded = lowered.translate(_LEET)
    yield re.sub(r"[^a-z]", "", decoded)


class CommonPasswordVariationValidator(CommonPasswordValidator):
    """Reject common passwords wearing a disguise.

    Django's own CommonPasswordValidator compares the password as typed, so
    "Password123!" sails past a list that contains "password". This strips the
    decorations first and checks each variation against that same list.
    """

    def validate(self, password, user=None):
        for candidate in _variations(password):
            if candidate and candidate in self.passwords:
                raise ValidationError(
                    _("This password is too easy to guess - it is a common "
                      "password with a few characters added."),
                    code="password_too_common",
                )

    def get_help_text(self):
        return _(
            "Avoid common words with numbers or symbols tacked on, such as "
            "Password123!."
        )


def generate_temp_password(length: int = TEMP_PASSWORD_LENGTH) -> str:
    """A random password that satisfies every rule above on the first try.

    One character is drawn from each required class before the rest is filled
    in, so a generated password is never rejected by our own validators - an
    invite that cannot be used is worse than no invite.
    """
    alphabet = (
        _UNAMBIGUOUS_LOWER
        + _UNAMBIGUOUS_UPPER
        + _UNAMBIGUOUS_DIGITS
        + _UNAMBIGUOUS_SYMBOLS
    )
    required = [
        secrets.choice(_UNAMBIGUOUS_LOWER),
        secrets.choice(_UNAMBIGUOUS_UPPER),
        secrets.choice(_UNAMBIGUOUS_DIGITS),
        secrets.choice(_UNAMBIGUOUS_SYMBOLS),
    ]
    filler = [secrets.choice(alphabet) for _unused in range(max(0, length - len(required)))]

    characters = required + filler
    # secrets.SystemRandom().shuffle, so the required characters do not always
    # sit in the first four positions.
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)
