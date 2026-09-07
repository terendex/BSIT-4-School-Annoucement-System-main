"""Outgoing mail - currently just the publisher invite.

Sent through Gmail's SMTP with an App Password (see EMAIL_* in settings). When
mail is not configured the console backend prints the message instead, so local
development works without credentials and nothing silently pretends to send.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape

logger = logging.getLogger(__name__)

SUBJECT = "You have been added as a publisher on {site}"

_TEXT_BODY = """Hi{greeting_name},

{inviter} added you as a publisher on {site}, so you can post announcements.

    Sign in at: {login_url}
    Email:      {email}
    Temporary password: {password}

This temporary password works once and expires on {expires}. You will be asked
to set your own password as soon as you sign in.

Please do not forward this email. If you were not expecting it, you can ignore
it - the account cannot be used until someone signs in with the password above.

- {site}
"""

_HTML_BODY = """\
<p>Hi{greeting_name},</p>
<p><strong>{inviter}</strong> added you as a publisher on {site}, so you can post
announcements.</p>
<table cellpadding="8" style="border-collapse:collapse;background:#f4f6fb;border-radius:8px">
  <tr><td>Sign in at</td><td><a href="{login_url}">{login_url}</a></td></tr>
  <tr><td>Email</td><td><code>{email}</code></td></tr>
  <tr><td>Temporary password</td>
      <td><code style="font-size:1.1em"><strong>{password}</strong></code></td></tr>
</table>
<p>This temporary password works once and expires on <strong>{expires}</strong>.
You will be asked to set your own password as soon as you sign in.</p>
<p style="color:#666;font-size:.9em">Please do not forward this email. If you were
not expecting it you can ignore it - the account cannot be used until someone
signs in with the password above.</p>
<p style="color:#666;font-size:.9em">- {site}</p>
"""


def send_invite_email(*, email, password, expires_at, inviter=None, full_name="") -> bool:
    """Mail one publisher their temporary password. True when it was accepted.

    The caller decides what a False means; the invite itself is already saved,
    so an admin can resend rather than the account being lost.
    """
    login_url = "{}/login".format(settings.FRONTEND_ORIGIN.rstrip("/"))
    inviter_label = "An admin"
    if inviter is not None:
        inviter_label = (
            getattr(inviter, "get_full_name", lambda: "")()
            or inviter.email
            or inviter.username
        )

    fields = {
        "greeting_name": " " + full_name.split()[0] if full_name.strip() else "",
        "inviter": inviter_label,
        "site": settings.SITE_NAME,
        "login_url": login_url,
        "email": email,
        "password": password,
        "expires": expires_at.strftime("%d %b %Y, %I:%M %p"),
    }
    html_fields = {key: escape(str(value)) for key, value in fields.items()}
    # The href is built from our own FRONTEND_ORIGIN, so it is safe unescaped;
    # everything else - including the invitee's own name - is not.
    html_fields["login_url"] = login_url

    message = EmailMultiAlternatives(
        subject=SUBJECT.format(site=settings.SITE_NAME),
        body=_TEXT_BODY.format(**fields),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    message.attach_alternative(_HTML_BODY.format(**html_fields), "text/html")

    try:
        # The password is in the body; it must never reach a log line.
        sent = message.send(fail_silently=False)
    except Exception:
        logger.exception("Invite email to %s could not be sent", email)
        return False
    if not sent:
        logger.error("Invite email to %s was not accepted by the mail server", email)
    return bool(sent)
