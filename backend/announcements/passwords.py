"""Password rules, and the tokens that carry an invite.

Django's own validators already cover length, common passwords, all-numeric
passwords, and similarity to the account's own email. This adds the character
mix on top, and the disguised-common-password check that catches Password123!.

There is deliberately no temporary-password generator here. An invite is a
link, not a credential: the account has no usable password until its owner
chooses one, so there is never a password for anyone else to hold.
"""
import hashlib
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


# --------------------------------------------------------------------------
# Invite tokens
# --------------------------------------------------------------------------
# An invite is a link, not a password. Nobody - not even the admin who sent it
# - ever learns the credential the publisher ends up with, and no password
# travels through an inbox or a chat window.
#
# The token is stored as a SHA-256 digest. It is 256 bits of `secrets` output
# rather than a human-chosen phrase, so there is nothing to brute force and no
# need for a slow password hash here.
INVITE_TOKEN_BYTES = 32


def generate_invite_token() -> str:
    return secrets.token_urlsafe(INVITE_TOKEN_BYTES)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(token: str, stored_hash: str) -> bool:
    """Constant-time comparison, so a wrong token leaks nothing by timing."""
    if not token or not stored_hash:
        return False
    return secrets.compare_digest(hash_invite_token(token), stored_hash)
