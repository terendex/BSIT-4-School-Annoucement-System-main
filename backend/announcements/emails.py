"""Outgoing mail - currently just the publisher invite.

Sent through Gmail's SMTP with an App Password (see EMAIL_* in settings). When
mail is not configured the console backend prints the message instead, so local
development works without credentials and nothing silently pretends to send.
"""
import logging
import socket

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


# Turns the exception a mail server raises into something an admin can act on.
# The distinction that matters most: credentials rejected (fixable by changing a
# variable) versus the connection never opening at all (the host is blocking
# outbound SMTP, and no amount of fiddling with the password will help).
#
# Order matters here. smtplib.SMTPException subclasses OSError, so the
# connection case has to be tested last or it swallows every other SMTP error.
def _explain(error) -> str:
    name = type(error).__name__
    detail = str(error).strip()

    if name == "SMTPAuthenticationError":
        return (
            "Gmail rejected the credentials. EMAIL_HOST_PASSWORD must be a "
            "16-character Google App Password with no spaces, generated for the "
            "account named in EMAIL_HOST_USER."
        )
    if name == "SMTPRecipientsRefused":
        return "The mail server refused that recipient address."
    if name == "SMTPSenderRefused":
        return (
            "The mail server refused the sender address. DEFAULT_FROM_EMAIL has "
            "to be the same account as EMAIL_HOST_USER."
        )
    if name in {"SMTPServerDisconnected", "SMTPConnectError"} or isinstance(
        error, (TimeoutError, ConnectionRefusedError, socket.gaierror, socket.timeout)
    ):
        return (
            "Could not reach {}:{} at all ({}). That is usually the host "
            "blocking outbound SMTP rather than anything wrong with your "
            "credentials - Railway and similar platforms block those ports by "
            "default. An HTTP email API (Resend, Brevo, SendGrid) is the way "
            "around it, since those send over HTTPS.".format(
                settings.EMAIL_HOST, settings.EMAIL_PORT, name
            )
        )
    return "{}: {}".format(name, detail[:200]) if detail else name


def send_invite_email(*, email, password, expires_at, inviter=None, full_name=""):
    """Mail one publisher their temporary password.

    Returns (delivered, reason). The reason is empty on success and, on
    failure, says what an admin should go and change - a bare "could not be
    sent" leaves them with nothing to do but guess.

    The invite itself is already saved either way, so a failure means resend,
    not a lost account.
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

    if "console" in settings.EMAIL_BACKEND:
        # The console backend would "succeed" while printing the password to
        # the deploy log and delivering nothing.
        logger.error("Invite for %s not sent: email is not configured", email)
        return False, (
            "Email is not configured on the server. Set EMAIL_HOST_USER and "
            "EMAIL_HOST_PASSWORD, then redeploy."
        )

    try:
        # The password is in the body; it must never reach a log line.
        sent = message.send(fail_silently=False)
    except Exception as error:
        reason = _explain(error)
        # exc_info, not the message - the body must stay out of the log.
        logger.error("Invite email to %s failed: %s", email, reason, exc_info=True)
        return False, reason

    if not sent:
        logger.error("Invite email to %s was not accepted by the mail server", email)
        return False, "The mail server accepted the connection but sent nothing."

    return True, ""
