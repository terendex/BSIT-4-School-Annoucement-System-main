"""Outgoing mail - currently just the publisher invite.

Sent through Gmail's SMTP with an App Password (see EMAIL_* in settings). When
mail is not configured the console backend prints the message instead, so local
development works without credentials and nothing silently pretends to send.
"""
import logging
import smtplib
import socket

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape

logger = logging.getLogger(__name__)

SUBJECT = "You have been added as a publisher on {site}"

_TEXT_BODY = """Hi{greeting_name},

{inviter} added you as a publisher on {site}, so you can post announcements.

Open this link to choose your password and finish setting up:

{link}

The link works once and expires on {expires}. Nobody else - including the admin
who invited you - can see the password you choose.

Please do not forward this email. If you were not expecting it you can ignore
it; the account cannot be used until someone opens the link above.

- {site}
"""

# A 600px table that collapses to full width on a phone, inline styles only,
# and a tap target comfortably over the 44px minimum. The raw link is repeated
# below the button with word-break, because plenty of clients strip buttons -
# and an unbreakable 80-character URL is what blows out an email on a phone.
_HTML_BODY = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#f6f7fb;
  -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%">

<!-- Preview text: what shows in the inbox list before opening. -->
<div style="display:none;max-height:0;overflow:hidden;opacity:0">
  Choose your password to finish setting up your {site} account.
</div>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
  style="background:#f6f7fb;padding:16px 12px">
<tr><td align="center">

  <table role="presentation" cellpadding="0" cellspacing="0" border="0"
    style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;
    border:1px solid #dcdfee;font-family:'Segoe UI',system-ui,-apple-system,
    Helvetica,Arial,sans-serif;color:#14172b">

    <tr><td style="height:4px;background:#1f2a6b;border-radius:12px 12px 0 0;
      font-size:0;line-height:0">&nbsp;</td></tr>

    <tr><td style="padding:26px 24px 8px">
      <p style="margin:0 0 4px;font-size:12px;letter-spacing:.06em;
        text-transform:uppercase;font-weight:700;color:#5a6080">{site}</p>
      <h1 style="margin:0;font-size:22px;line-height:1.25;color:#10173d">
        You can post announcements</h1>
    </td></tr>

    <tr><td style="padding:14px 24px 0;font-size:16px;line-height:1.6">
      <p style="margin:0 0 14px">Hi{greeting_name},</p>
      <p style="margin:0"><strong>{inviter}</strong> added you as a publisher on
      {site}. Choose a password and you are in.</p>
    </td></tr>

    <tr><td style="padding:24px 24px 6px">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
      <tr><td align="center" bgcolor="#1f2a6b" style="border-radius:8px">
        <a href="{link}" style="display:block;padding:15px 24px;font-size:16px;
          font-weight:600;color:#ffffff;text-decoration:none;border-radius:8px">
          Choose your password</a>
      </td></tr>
      </table>
    </td></tr>

    <tr><td style="padding:14px 24px 0;font-size:13px;line-height:1.6;color:#5a6080">
      <p style="margin:0 0 6px">Or paste this into your browser:</p>
      <p style="margin:0;word-break:break-all;overflow-wrap:break-word">
        <a href="{link}" style="color:#2b3888">{link}</a></p>
    </td></tr>

    <tr><td style="padding:20px 24px 0;font-size:14px;line-height:1.6">
      <p style="margin:0">The link works once and expires on
      <strong>{expires}</strong>. Nobody else - including the admin who invited
      you - can see the password you choose.</p>
    </td></tr>

    <tr><td style="padding:18px 24px 26px">
      <p style="margin:0;padding-top:16px;border-top:1px solid #dcdfee;
        font-size:12px;line-height:1.6;color:#5a6080">
        Please do not forward this email. If you were not expecting it you can
        ignore it - the account cannot be used until someone opens the link.
      </p>
    </td></tr>

  </table>

</td></tr>
</table>
</body>
</html>
"""


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
    unreachable = isinstance(error, OSError) and not isinstance(
        error, smtplib.SMTPException
    )
    if name in {"SMTPServerDisconnected", "SMTPConnectError"} or unreachable:
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


def send_invite_email(*, email, link, expires_at, inviter=None, full_name=""):
    """Mail one publisher the link that lets them set their own password.

    Returns (delivered, reason). The reason is empty on success and, on
    failure, says what an admin should go and change - a bare "could not be
    sent" leaves them with nothing to do but guess.

    The invite itself is already saved either way, so a failure means resend,
    not a lost account.
    """
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
        "subject": SUBJECT.format(site=settings.SITE_NAME),
        "link": link,
        "expires": expires_at.strftime("%d %b %Y, %I:%M %p"),
    }
    html_fields = {key: escape(str(value)) for key, value in fields.items()}
    # The href is built from our own FRONTEND_ORIGIN plus a token we generated,
    # so it is safe unescaped; everything else - the invitee's own name most of
    # all - is not.
    html_fields["link"] = link

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
        # The body carries a live invite link; it must never reach a log line.
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
