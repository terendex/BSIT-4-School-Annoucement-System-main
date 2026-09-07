"""Send mail over Brevo's HTTP API instead of SMTP.

Railway - like most container hosts - blocks outbound SMTP. The symptom is
`OSError: [Errno 101] Network is unreachable` when connecting to port 587, and
no credential is going to fix it: the packets never leave the container.

This backend posts to https://api.brevo.com over 443, which is not blocked.

It needs an **API key** (starts with `xkeysib-`), from Brevo's SMTP & API page
under the *API Keys* tab. An SMTP key (`xsmtpsib-`) is a different credential
for the SMTP relay and this API rejects it with "Key not found" - and the SMTP
relay itself is unreachable from here anyway.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.brevo.com/v3/smtp/email"
TIMEOUT = 30


def _parse_address(address: str):
    """"Name <a@b.test>" -> {"name": ..., "email": ...}"""
    address = (address or "").strip()
    if "<" in address and address.endswith(">"):
        name, _, rest = address.partition("<")
        return {"name": name.strip().strip('"'), "email": rest[:-1].strip()}
    return {"email": address}


class BrevoAPIBackend(BaseEmailBackend):
    """Minimal Brevo transport - enough for the invite emails this app sends."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "BREVO_API_KEY", "")

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if self.fail_silently:
                return 0
            raise ValueError(
                "BREVO_API_KEY is not set. Get an API key (xkeysib-...) from "
                "Brevo's SMTP & API page, API Keys tab."
            )

        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    def _payload(self, message):
        html = ""
        for content, mimetype in getattr(message, "alternatives", []) or []:
            if mimetype == "text/html":
                html = content
                break

        payload = {
            "sender": _parse_address(message.from_email),
            "to": [_parse_address(address) for address in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }
        if html:
            payload["htmlContent"] = html
        if message.cc:
            payload["cc"] = [_parse_address(a) for a in message.cc]
        if message.bcc:
            payload["bcc"] = [_parse_address(a) for a in message.bcc]
        if message.reply_to:
            payload["replyTo"] = _parse_address(message.reply_to[0])
        return payload

    def _send(self, message) -> bool:
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(self._payload(message)).encode("utf-8"),
            method="POST",
        )
        request.add_header("api-key", self.api_key)
        request.add_header("content-type", "application/json")
        request.add_header("accept", "application/json")

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return 200 <= response.status < 300
        except urllib.error.HTTPError as error:
            # Brevo explains refusals in the body; that detail is what an admin
            # needs, so surface it rather than a bare 400.
            try:
                detail = json.loads(error.read().decode("utf-8")).get("message", "")
            except Exception:
                detail = ""
            logger.error("Brevo refused the message: %s %s", error.code, detail)
            if self.fail_silently:
                return False
            raise BrevoError(error.code, detail) from error
        except Exception as error:
            logger.error("Brevo request failed: %s", error)
            if self.fail_silently:
                return False
            raise


class BrevoError(Exception):
    """A refusal from the Brevo API, carrying what it actually said."""

    def __init__(self, status, detail):
        self.status = status
        self.detail = detail
        super().__init__("Brevo returned {}: {}".format(status, detail or "no detail"))
