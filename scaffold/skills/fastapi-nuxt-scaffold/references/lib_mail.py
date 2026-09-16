"""Destination: api/lib/mail.py

Rendering and delivery of transactional email.

Delivery is **best-effort**: `send_mail` logs and swallows transport failures instead of
raising. That is a deliberate trade for this scaffold's two senders. An invite whose email
bounced is still a valid invite -- `POST /rest/users/invite` returns the link, so an admin can
always hand it over directly -- and a 500 on the invite endpoint because an SMTP host was
unreachable would be a worse failure than a missing email. Call it from a `BackgroundTasks`
so a slow SMTP handshake never sits inside the request either.

If a future feature genuinely needs delivery confirmation, that feature wants a queue with
retries, not an exception here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import jinja2
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from environment import settings

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
    autoescape=jinja2.select_autoescape(("html", "xml")),
    trim_blocks=True,
    lstrip_blocks=True,
    enable_async=True,
)


def _connection_config() -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        USE_CREDENTIALS=settings.MAIL_USE_CREDENTIALS,
        VALIDATE_CERTS=settings.MAIL_VALIDATE_CERTS,
        TIMEOUT=settings.MAIL_TIMEOUT,
    )


async def render_email(template_name: str, context: dict[str, Any]) -> str:
    """Render `templates/email/<template_name>` with the app-wide branding context merged in."""
    template = _jinja_env.get_template(f"email/{template_name}")
    return await template.render_async(appName=settings.APP_NAME, **context)


async def send_mail(to: str, subject: str, html_body: str) -> None:
    """Deliver one HTML email. Logs and returns on failure -- see the module docstring."""
    message = MessageSchema(recipients=[to], subject=subject, body=html_body, subtype=MessageType.html)
    try:
        await FastMail(_connection_config()).send_message(message)
    except Exception as error:  # noqa: BLE001 -- see below
        # Deliberately broad. This function's contract is that it never raises, and mail
        # fails in more ways than a socket error: `fastapi-mail` wraps transport problems in
        # its OWN `ConnectionErrors`, which no builtin except-clause catches, and DNS, TLS,
        # auth and encoding each surface differently again. Narrowing this to the exception
        # types that seem likely is how a dead SMTP host ends up 500-ing an invite that was
        # otherwise created correctly -- which is exactly the bug this module exists to avoid.
        logger.warning("Could not send %r to %s: %s", subject, to, error)
